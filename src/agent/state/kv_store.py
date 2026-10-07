"""Cloudflare KV durable state store implementation using the REST API."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from agent.errors import ConfigError, StateStoreError
from agent.models import (
    ActiveThreadRecord,
    ConnectionRequestAction,
    DailyCounters,
    HistoryEntry,
    PendingAction,
    PostRecord,
    ScheduledPost,
)
from agent.state.base import BaseStateStore

logger = logging.getLogger("agent.state.kv_store")


class CloudflareKVStateStore(BaseStateStore):
    """Cloudflare Workers KV state persistence backend using the Cloudflare v4 REST API."""

    def __init__(
        self,
        account_id: str,
        namespace_id: str,
        api_token: SecretStr | str,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        if not account_id:
            raise ConfigError("CloudflareKVStateStore requires a non-empty account_id")
        if not namespace_id:
            raise ConfigError("CloudflareKVStateStore requires a non-empty namespace_id")

        token_str = api_token.get_secret_value() if isinstance(api_token, SecretStr) else api_token
        if not token_str:
            raise ConfigError("CloudflareKVStateStore requires a non-empty api_token")

        self.account_id = account_id
        self.namespace_id = namespace_id
        self._api_token = token_str
        self.timeout = timeout

        self.base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}"
            f"/storage/kv/namespaces/{self.namespace_id}"
        )
        self._headers = {
            "Authorization": f"Bearer {self._api_token}",
            "User-Agent": "LinkedIn-Agent-KV/1.0",
        }

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self.timeout,
            )
            self._owns_client = True

    def close(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> CloudflareKVStateStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # -------------------------------------------------------------------------
    # Internal KV REST Helpers
    # -------------------------------------------------------------------------

    def _get_value(self, key: str) -> str | None:
        """Fetch raw string value for key. Returns None if key not found (404)."""
        safe_key = quote(key, safe=":")
        try:
            resp = self._client.get(f"/values/{safe_key}")
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise StateStoreError(
                    f"Cloudflare KV GET '{key}' failed with status {resp.status_code}: {resp.text}"
                )
            return resp.text
        except httpx.HTTPError as err:
            raise StateStoreError(f"HTTP error reading KV key '{key}': {err}") from err

    def _put_value(self, key: str, value: str) -> None:
        """Store string value for key."""
        safe_key = quote(key, safe=":")
        try:
            resp = self._client.put(
                f"/values/{safe_key}",
                content=value,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                raise StateStoreError(
                    f"Cloudflare KV PUT '{key}' failed with status {resp.status_code}: {resp.text}"
                )
        except httpx.HTTPError as err:
            raise StateStoreError(f"HTTP error writing KV key '{key}': {err}") from err

    def _delete_key(self, key: str) -> bool:
        """Delete key from KV. Returns True if successfully deleted."""
        safe_key = quote(key, safe=":")
        try:
            resp = self._client.delete(f"/values/{safe_key}")
            if resp.status_code in (200, 404):
                return True
            raise StateStoreError(
                f"Cloudflare KV DELETE '{key}' failed with status {resp.status_code}: {resp.text}"
            )
        except httpx.HTTPError as err:
            raise StateStoreError(f"HTTP error deleting KV key '{key}': {err}") from err

    def _list_keys(self, prefix: str) -> list[str]:
        """List all key names matching prefix with pagination support."""
        keys: list[str] = []
        cursor: str | None = None
        while True:
            params: dict[str, str] = {"prefix": prefix, "limit": "1000"}
            if cursor:
                params["cursor"] = cursor
            try:
                resp = self._client.get("/keys", params=params)
                if resp.status_code >= 400:
                    raise StateStoreError(
                        f"Cloudflare KV list keys failed with status {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
            except httpx.HTTPError as err:
                raise StateStoreError(
                    f"HTTP error listing KV keys with prefix '{prefix}': {err}"
                ) from err
            except json.JSONDecodeError as err:
                raise StateStoreError(f"Malformed JSON listing KV keys: {err}") from err

            if not data.get("success", False):
                raise StateStoreError(f"Cloudflare KV list keys unsuccessful: {data.get('errors')}")

            result = data.get("result", [])
            for item in result:
                name = item.get("name")
                if name:
                    keys.append(name)

            result_info = data.get("result_info", {})
            cursor = result_info.get("cursor")
            if not cursor:
                break
        return keys

    # -------------------------------------------------------------------------
    # Pending Actions
    # -------------------------------------------------------------------------

    def write_pending(self, item: PendingAction) -> str:
        """Write a pending action to key pending:{item_id} and index by telegram_message_id."""
        key = f"pending:{item.item_id}"
        payload = item.model_dump_json(indent=2)
        self._put_value(key, payload)
        tg_msg_id = getattr(item, "telegram_message_id", None)
        if tg_msg_id and int(tg_msg_id) > 0:
            self._put_value(f"msg_id:{tg_msg_id}", item.item_id)
        return key

    def find_pending_by_message_id(self, message_id: int) -> PendingAction | None:
        """Find a pending action by its telegram_message_id in O(1) via secondary index."""
        indexed_item_id = self._get_value(f"msg_id:{message_id}")
        if indexed_item_id:
            item = self.read_pending(indexed_item_id.strip())
            if item is not None and item.telegram_message_id == message_id:
                return item
        return super().find_pending_by_message_id(message_id)

    def read_pending(self, item_id: str) -> PendingAction | None:
        """Read a pending action by item_id. Returns None if not found."""
        raw = self._get_value(f"pending:{item_id}")
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return PendingAction.model_validate(data)
        except Exception as err:
            raise StateStoreError(f"Failed to parse pending action {item_id}: {err}") from err

    def delete_pending(self, item_id: str) -> bool:
        """Delete a pending action key and its secondary index. Returns True if deleted, False if not found."""
        key = f"pending:{item_id}"
        raw = self._get_value(key)
        if raw is None:
            return False
        try:
            data = json.loads(raw)
            tg_msg_id = data.get("telegram_message_id")
            if tg_msg_id and int(tg_msg_id) > 0:
                self._delete_key(f"msg_id:{tg_msg_id}")
        except Exception:
            pass
        return self._delete_key(key)

    def list_pending(self) -> list[PendingAction]:
        """List all current pending actions sorted by creation time."""
        keys = self._list_keys(prefix="pending:")
        results: list[PendingAction] = []
        for key in keys:
            item_id = key.removeprefix("pending:")
            item = self.read_pending(item_id)
            if item is not None:
                results.append(item)

        results.sort(key=lambda x: x.created_at)
        return results

    # -------------------------------------------------------------------------
    # History (Audit Log)
    # -------------------------------------------------------------------------

    def append_history(self, entry: HistoryEntry) -> None:
        """Append an outcome entry to KV key history."""
        raw = self._get_value("history")
        history_list: list[dict[str, Any]] = []
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    history_list = parsed
            except Exception:
                history_list = []

        history_list.append(entry.model_dump(mode="json"))
        self._put_value("history", json.dumps(history_list, default=str))

    def read_history(self, limit: int | None = None) -> list[HistoryEntry]:
        """Read history entries from KV key history."""
        raw = self._get_value("history")
        if not raw:
            return []

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                return []
        except Exception:
            return []

        entries: list[HistoryEntry] = []
        for item in parsed:
            try:
                entries.append(HistoryEntry.model_validate(item))
            except Exception:
                continue

        if limit is not None and limit > 0:
            return entries[-limit:]
        return entries

    # -------------------------------------------------------------------------
    # Seen Posts Hashes
    # -------------------------------------------------------------------------

    def load_seen_hashes(self, ttl_days: int = 30) -> set[str]:
        """Load and prune seen post content hashes from KV key seen_posts."""
        raw = self._get_value("seen_posts")
        if not raw:
            return set()

        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                return set()
        except Exception:
            return set()

        now = datetime.now(UTC)
        valid_hashes: dict[str, str] = {}
        result_set: set[str] = set()

        for content_hash, timestamp_str in data.items():
            try:
                ts = datetime.fromisoformat(timestamp_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if (now - ts).total_seconds() <= (ttl_days * 86400):
                    valid_hashes[content_hash] = timestamp_str
                    result_set.add(content_hash)
            except Exception:
                continue

        if len(valid_hashes) != len(data):
            self.save_seen_hashes(valid_hashes)

        return result_set

    def save_seen_hashes(self, hashes: dict[str, str]) -> None:
        """Save a dictionary of content_hash -> iso_timestamp to seen_posts."""
        self._put_value("seen_posts", json.dumps(hashes))

    def record_seen_posts(self, posts: list[PostRecord]) -> set[str]:
        """Record newly seen posts with current timestamp and return updated hash set."""
        seen_map: dict[str, str] = {}
        raw = self._get_value("seen_posts")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    seen_map = parsed
            except Exception:
                pass

        now_iso = datetime.now(UTC).isoformat()
        for p in posts:
            seen_map[p.content_hash] = now_iso

        self.save_seen_hashes(seen_map)
        return set(seen_map.keys())

    # -------------------------------------------------------------------------
    # Daily Counters
    # -------------------------------------------------------------------------

    def load_daily_counters(self, today: date | None = None) -> DailyCounters:
        """Load daily counters from KV, automatically rolling over to 0 if stored date != today."""
        target_date = today or datetime.now(UTC).date()
        target_date_str = target_date.isoformat()

        raw = self._get_value("daily_counters")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("date") == target_date_str:
                    return DailyCounters.model_validate(parsed)
            except Exception:
                pass

        fresh_counters = DailyCounters(
            date=target_date_str,
            comments_executed=0,
            posts_executed=0,
            suggestions_sent=0,
        )
        self.save_daily_counters(fresh_counters)
        return fresh_counters

    def save_daily_counters(self, counters: DailyCounters) -> None:
        """Save daily counters to KV key daily_counters."""
        self._put_value("daily_counters", counters.model_dump_json(indent=2))

    # -------------------------------------------------------------------------
    # Safety and Pause State Management
    # -------------------------------------------------------------------------

    def is_paused(self) -> bool:
        """Check whether the agent has been paused via KV key paused."""
        raw = self._get_value("paused")
        return raw is not None

    def set_paused(self, paused: bool) -> None:
        """Set or clear the remote pause state in KV key paused."""
        if paused:
            payload = json.dumps({"paused_at": datetime.now(UTC).isoformat()})
            self._put_value("paused", payload)
        else:
            self._delete_key("paused")

    def read_incident(self) -> dict[str, Any] | None:
        """Read circuit breaker incident data from KV key incident if present."""
        raw = self._get_value("incident")
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return None
        except Exception:
            return {"reason": "Corrupted incident KV data"}

    def save_incident(self, incident_data: dict[str, Any]) -> None:
        """Persist circuit breaker incident details to KV key incident."""
        self._put_value("incident", json.dumps(incident_data, default=str))

    def clear_incident(self) -> bool:
        """Safely clear KV key incident if present to reset the circuit breaker."""
        if self._get_value("incident") is not None:
            return self._delete_key("incident")
        return False

    # -------------------------------------------------------------------------
    # Arbitrary Key/Value Storage
    # -------------------------------------------------------------------------

    def put_key(self, key: str, value: str | Any) -> None:
        """Store string value or JSON-serializable object for key in Cloudflare KV."""
        content = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
        self._put_value(key, content)

    def get_key(self, key: str) -> str | None:
        """Retrieve string value for key from Cloudflare KV."""
        return self._get_value(key)

    # -------------------------------------------------------------------------
    # Connection Outreach Queue
    # -------------------------------------------------------------------------

    def load_connection_queue(self) -> list[ConnectionRequestAction]:
        """Load pending connection request candidates from KV key connection_queue."""
        raw = self._get_value("connection_queue")
        if raw is None:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [ConnectionRequestAction.model_validate(item) for item in parsed]
            return []
        except Exception:
            return []

    def save_connection_queue(self, queue: list[ConnectionRequestAction]) -> None:
        """Persist list of connection candidates to KV key connection_queue."""
        payload = json.dumps([c.model_dump(mode="json") for c in queue])
        self._put_value("connection_queue", payload)

    # -------------------------------------------------------------------------
    # Scheduled Posts (Post Composer Studio)
    # -------------------------------------------------------------------------

    def save_scheduled_post(self, post: ScheduledPost) -> None:
        """Persist a scheduled post to KV keys scheduled:{post.id} and scheduled_posts."""
        payload = json.dumps(post.model_dump(mode="json"))
        self._put_value(f"scheduled:{post.id}", payload)
        posts = self.list_scheduled_posts()
        updated = [p for p in posts if p.id != post.id]
        updated.append(post)
        self._put_value("scheduled_posts", json.dumps([p.model_dump(mode="json") for p in updated]))

    def read_scheduled_post(self, post_id: str) -> ScheduledPost | None:
        """Retrieve a scheduled post by ID from KV key scheduled:{post_id}."""
        raw = self._get_value(f"scheduled:{post_id}")
        if raw is None:
            return None
        try:
            return ScheduledPost.model_validate(json.loads(raw))
        except Exception as err:
            raise StateStoreError(f"Failed to parse scheduled post {post_id}: {err}") from err

    def list_scheduled_posts(self) -> list[ScheduledPost]:
        """List all current scheduled posts from KV."""
        raw = self._get_value("scheduled_posts")
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [ScheduledPost.model_validate(p) for p in parsed]
            except Exception:
                pass
        keys = self._list_keys("scheduled:")
        posts: list[ScheduledPost] = []
        for k in keys:
            val = self._get_value(k)
            if val:
                try:
                    posts.append(ScheduledPost.model_validate(json.loads(val)))
                except Exception:
                    continue
        return posts

    def delete_scheduled_post(self, post_id: str) -> bool:
        """Delete a scheduled post from KV."""
        deleted = self._delete_key(f"scheduled:{post_id}")
        posts = self.list_scheduled_posts()
        updated = [p for p in posts if p.id != post_id]
        self._put_value("scheduled_posts", json.dumps([p.model_dump(mode="json") for p in updated]))
        return deleted

    # -------------------------------------------------------------------------
    # Scout Schedule (Configurable Scout Runs)
    # -------------------------------------------------------------------------

    def get_scout_schedule(self) -> list[dict[str, Any]]:
        """Retrieve configured scout schedule from KV key scout_schedule."""
        raw = self._get_value("scout_schedule")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def save_scout_schedule(self, schedule: list[dict[str, Any]]) -> None:
        """Persist configured scout schedule to KV key scout_schedule."""
        self._put_value("scout_schedule", json.dumps(schedule))

    # -------------------------------------------------------------------------
    # Active Threads (Comment Thread Monitoring)
    # -------------------------------------------------------------------------

    def list_active_threads(self) -> list[ActiveThreadRecord]:
        """List active comment threads from KV key active_threads."""
        raw = self._get_value("active_threads")
        if raw is None:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [ActiveThreadRecord.model_validate(item) for item in parsed]
            return []
        except Exception:
            return []

    def save_active_thread(self, thread: ActiveThreadRecord) -> None:
        """Persist or update an active comment thread in KV key active_threads."""
        threads = self.list_active_threads()
        for idx, item in enumerate(threads):
            if item.id == thread.id:
                threads[idx] = thread
                self._put_value(
                    "active_threads", json.dumps([t.model_dump(mode="json") for t in threads])
                )
                return
        threads.append(thread)
        self._put_value("active_threads", json.dumps([t.model_dump(mode="json") for t in threads]))

    def update_thread_status(self, thread_id: str, status: str) -> None:
        """Update lifecycle status of an active thread in KV key active_threads."""
        threads = self.list_active_threads()
        for idx, item in enumerate(threads):
            if item.id == thread_id:
                threads[idx] = item.model_copy(update={"status": status})
                self._put_value(
                    "active_threads", json.dumps([t.model_dump(mode="json") for t in threads])
                )
                return
