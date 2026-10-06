"""Base state store abstraction for durable agent state management."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime
from typing import Any

from agent.models import (
    ActiveThreadRecord,
    ConnectionRequestAction,
    DailyCounters,
    HistoryEntry,
    PendingAction,
    PostRecord,
    ScheduledPost,
)


class BaseStateStore(ABC):
    """Abstract interface defining required state persistence operations."""

    # -------------------------------------------------------------------------
    # Pending Actions
    # -------------------------------------------------------------------------

    @abstractmethod
    def write_pending(self, item: PendingAction) -> Any:
        """Write or persist a pending action."""
        ...

    @abstractmethod
    def read_pending(self, item_id: str) -> PendingAction | None:
        """Read a pending action by its item_id. Returns None if not found."""
        ...

    @abstractmethod
    def delete_pending(self, item_id: str) -> bool:
        """Delete a pending action by its item_id. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def list_pending(self) -> list[PendingAction]:
        """List all current pending actions sorted chronologically."""
        ...

    def find_pending_by_message_id(self, message_id: int) -> PendingAction | None:
        """Find a pending action by its telegram_message_id. Returns None if not found."""
        for item in self.list_pending():
            if item.telegram_message_id == message_id:
                return item
        return None

    def update_pending_draft(self, item_id: str, new_draft_text: str) -> PendingAction | None:
        """Update the draft text of an existing pending action."""
        item = self.read_pending(item_id)
        if item is None:
            return None
        updated = item.model_copy(update={"draft_text": new_draft_text})
        self.write_pending(updated)
        return updated

    def prune_expired_pending(
        self, ttl_hours: int = 12, now: datetime | None = None
    ) -> list[PendingAction]:
        """Scan and prune pending actions that have exceeded their approval TTL."""
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)

        pruned_items: list[PendingAction] = []
        pending_items = self.list_pending()

        for item in pending_items:
            created_at = item.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            elapsed_seconds = (current_time - created_at).total_seconds()
            if elapsed_seconds > (ttl_hours * 3600):
                entry = HistoryEntry(
                    item_id=item.item_id,
                    action_type=item.action_type,
                    final_status="expired",
                    decided_at=None,
                    executed_at=current_time,
                    screenshot_path=None,
                    error=f"Pending approval expired (exceeded {ttl_hours}h TTL)",
                )
                self.append_history(entry)
                self.delete_pending(item.item_id)
                pruned_items.append(item)

        return pruned_items

    # -------------------------------------------------------------------------
    # History Audit Log
    # -------------------------------------------------------------------------

    @abstractmethod
    def append_history(self, entry: HistoryEntry) -> None:
        """Append an outcome entry to the audit log."""
        ...

    @abstractmethod
    def read_history(self, limit: int | None = None) -> list[HistoryEntry]:
        """Read recent history entries up to limit."""
        ...

    # -------------------------------------------------------------------------
    # Seen Posts Hashes
    # -------------------------------------------------------------------------

    @abstractmethod
    def load_seen_hashes(self, ttl_days: int = 30) -> set[str]:
        """Load valid seen post hashes, pruning expired entries."""
        ...

    @abstractmethod
    def save_seen_hashes(self, hashes: dict[str, str]) -> None:
        """Save a dictionary of content_hash -> iso_timestamp."""
        ...

    @abstractmethod
    def record_seen_posts(self, posts: list[PostRecord]) -> set[str]:
        """Record newly seen posts with current timestamp and return updated hash set."""
        ...

    # -------------------------------------------------------------------------
    # Daily Counters
    # -------------------------------------------------------------------------

    @abstractmethod
    def load_daily_counters(self, today: date | None = None) -> DailyCounters:
        """Load daily counters, rolling over to 0 if stored date != today."""
        ...

    @abstractmethod
    def save_daily_counters(self, counters: DailyCounters) -> None:
        """Save daily counters."""
        ...

    def increment_comment_count(self, today: date | None = None) -> DailyCounters:
        """Increment daily comment count by 1 and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed + 1,
            posts_executed=counters.posts_executed,
            suggestions_sent=counters.suggestions_sent,
        )
        self.save_daily_counters(updated)
        return updated

    def increment_post_count(self, today: date | None = None) -> DailyCounters:
        """Increment daily post count by 1 and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed,
            posts_executed=counters.posts_executed + 1,
            suggestions_sent=counters.suggestions_sent,
        )
        self.save_daily_counters(updated)
        return updated

    def increment_suggestion_count(
        self, count: int = 1, today: date | None = None
    ) -> DailyCounters:
        """Increment daily suggestions sent count and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed,
            posts_executed=counters.posts_executed,
            suggestions_sent=counters.suggestions_sent + count,
            connections_sent=counters.connections_sent,
        )
        self.save_daily_counters(updated)
        return updated

    def increment_connection_count(self, today: date | None = None) -> DailyCounters:
        """Increment daily connection requests sent count and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed,
            posts_executed=counters.posts_executed,
            suggestions_sent=counters.suggestions_sent,
            connections_sent=counters.connections_sent + 1,
        )
        self.save_daily_counters(updated)
        return updated

    # -------------------------------------------------------------------------
    # Connection Outreach Queue
    # -------------------------------------------------------------------------

    def load_connection_queue(self) -> list[ConnectionRequestAction]:
        """Load pending connection request candidates."""
        return []

    @abstractmethod
    def save_connection_queue(self, queue: list[ConnectionRequestAction]) -> None:
        """Save list of connection request candidates."""
        pass

    def add_connection_candidate(self, candidate: ConnectionRequestAction) -> None:
        """Add or update a connection request candidate in the outreach queue."""
        queue = self.load_connection_queue()
        for idx, item in enumerate(queue):
            if item.id == candidate.id:
                queue[idx] = candidate
                self.save_connection_queue(queue)
                return
        queue.append(candidate)
        self.save_connection_queue(queue)

    def read_connection_candidate(self, candidate_id: str) -> ConnectionRequestAction | None:
        """Find a connection request candidate by ID."""
        for item in self.load_connection_queue():
            if item.id == candidate_id:
                return item
        return None

    def update_connection_status(
        self,
        candidate_id: str,
        status: str,
        approved_at: datetime | None = None,
        note: str | None = None,
        note_text: str | None = None,
    ) -> ConnectionRequestAction | None:
        """Update the status, note, or approval timestamp of a connection candidate."""
        effective_note = note if note is not None else note_text
        queue = self.load_connection_queue()
        target = None
        for idx, item in enumerate(queue):
            if item.id == candidate_id:
                updated = item.model_copy(
                    update={
                        "status": status,
                        "approved_at": approved_at
                        or (datetime.now(UTC) if status == "approved" else item.approved_at),
                        "note_text": effective_note
                        if effective_note is not None
                        else item.note_text,
                    }
                )
                queue[idx] = updated
                target = updated
                break
        if target:
            self.save_connection_queue(queue)
        return target

    # -------------------------------------------------------------------------
    # Scheduled Posts (Post Composer Studio)
    # -------------------------------------------------------------------------

    @abstractmethod
    def save_scheduled_post(self, post: ScheduledPost) -> None:
        """Persist a scheduled post to the state store."""
        pass

    def read_scheduled_post(self, post_id: str) -> ScheduledPost | None:
        """Retrieve a scheduled post by ID, or None if not found."""
        return None

    def list_scheduled_posts(self) -> list[ScheduledPost]:
        """List all current scheduled posts."""
        return []

    def delete_scheduled_post(self, post_id: str) -> bool:
        """Delete a scheduled post by ID. Returns True if deleted."""
        return False

    # -------------------------------------------------------------------------
    # Active Threads (Comment Thread Monitoring)
    # -------------------------------------------------------------------------

    def list_active_threads(self) -> list[ActiveThreadRecord]:
        """List active multi-turn comment threads being monitored."""
        return []

    @abstractmethod
    def save_active_thread(self, thread: ActiveThreadRecord) -> None:
        """Persist an active comment thread record."""
        pass

    @abstractmethod
    def update_thread_status(self, thread_id: str, status: str) -> None:
        """Update lifecycle status of an active comment thread."""
        pass

    # -------------------------------------------------------------------------
    # Safety and Pause State Management
    # -------------------------------------------------------------------------

    @abstractmethod
    def is_paused(self) -> bool:
        """Check whether the agent is paused remotely."""
        ...

    @abstractmethod
    def set_paused(self, paused: bool) -> None:
        """Set or clear the remote pause state."""
        ...

    @abstractmethod
    def read_incident(self) -> dict[str, Any] | None:
        """Read active circuit breaker incident details, or None if normal."""
        ...

    @abstractmethod
    def save_incident(self, incident_data: dict[str, Any]) -> None:
        """Persist circuit breaker incident details."""
        ...

    def record_incident(self, reason: str, context: dict[str, Any] | None = None) -> None:
        """Trip circuit breaker and record incident details idempotently."""
        now_iso = datetime.now(UTC).isoformat()
        existing = self.read_incident()
        created_at = existing.get("created_at", now_iso) if existing else now_iso
        payload = {
            "created_at": created_at,
            "tripped_at": now_iso,
            "reason": reason,
            "context": context or {},
        }
        self.save_incident(payload)

    @abstractmethod
    def clear_incident(self) -> bool:
        """Safely clear active incident to reset the circuit breaker."""
        ...

    def commit_and_push(
        self,
        message: str,
        push: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Persist or commit state changes if required by the storage backend.

        For remote storage backends (e.g. Cloudflare KV), writes are already durable;
        this method acts as a no-op returning True.
        """
        return True

    # -------------------------------------------------------------------------
    # Arbitrary Key/Value Storage
    # -------------------------------------------------------------------------

    @abstractmethod
    def put_key(self, key: str, value: str | Any) -> None:
        """Store an arbitrary string value or serializable data for a key."""
        ...

    def get_key(self, key: str) -> str | None:
        """Retrieve an arbitrary string value for a key, or None if not found."""
        return None

    # -------------------------------------------------------------------------
    # Dynamic Voice Memory Samples
    # -------------------------------------------------------------------------

    def load_dynamic_voice_samples(self) -> list[dict[str, Any]]:
        """Load dynamically indexed operator voice samples from durable storage."""
        raw = self.get_key("voice_samples")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_dynamic_voice_samples(self, samples: list[dict[str, Any]]) -> None:
        """Persist dynamically indexed operator voice samples to durable storage."""
        self.put_key("voice_samples", samples)

    # -------------------------------------------------------------------------
    # Rejection Feedback Tags
    # -------------------------------------------------------------------------

    def append_rejection_feedback(self, item_id: str, reason: str) -> None:
        """Record operator rejection feedback tag."""
        raw = self.get_key("rejection_feedback")
        feedbacks: list[dict[str, Any]] = []
        if raw:
            try:
                feedbacks = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(feedbacks, list):
                    feedbacks = []
            except Exception:
                feedbacks = []
        feedbacks.append({
            "item_id": item_id,
            "reason": reason,
            "created_at": datetime.now(UTC).isoformat(),
        })
        if len(feedbacks) > 200:
            feedbacks = feedbacks[-200:]
        self.put_key("rejection_feedback", json.dumps(feedbacks))

    def load_rejection_feedbacks(self) -> list[dict[str, Any]]:
        """Load recent operator rejection feedback tags."""
        raw = self.get_key("rejection_feedback")
        if not raw:
            return []
        try:
            feedbacks = json.loads(raw) if isinstance(raw, str) else raw
            return feedbacks if isinstance(feedbacks, list) else []
        except Exception:
            return []
