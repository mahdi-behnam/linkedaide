"""Unit tests for CloudflareKVStateStore persistence backend using httpx mock transport."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote

import httpx
import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import ConfigError, StateStoreError
from agent.models import DailyCounters, HistoryEntry, PendingAction, PostRecord
from agent.state import CloudflareKVStateStore, GitStateStore, get_state_store


class MockKVHandler:
    """In-memory mock for Cloudflare Workers KV REST API."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.fail_paths: dict[str, int] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        # Check simulated failure
        for fail_prefix, status_code in self.fail_paths.items():
            if fail_prefix in path:
                return httpx.Response(
                    status_code, json={"success": False, "errors": ["Simulated error"]}
                )

        # Match /values/{key}
        if "/values/" in path:
            key = path.split("/values/", 1)[1]
            if request.method == "GET":
                if key in self.kv:
                    return httpx.Response(200, text=self.kv[key])
                return httpx.Response(
                    404,
                    json={
                        "success": False,
                        "errors": [{"code": 10009, "message": "key not found"}],
                    },
                )

            if request.method == "PUT":
                self.kv[key] = request.content.decode("utf-8")
                return httpx.Response(
                    200, json={"success": True, "errors": [], "messages": [], "result": None}
                )

            if request.method == "DELETE":
                if key in self.kv:
                    del self.kv[key]
                    return httpx.Response(
                        200, json={"success": True, "errors": [], "messages": [], "result": None}
                    )
                return httpx.Response(
                    404,
                    json={
                        "success": False,
                        "errors": [{"code": 10009, "message": "key not found"}],
                    },
                )

        # Match /keys
        if path.endswith("/keys"):
            query = parse_qs(
                request.url.query.decode("utf-8")
                if isinstance(request.url.query, bytes)
                else str(request.url.query)
            )
            prefix = query.get("prefix", [""])[0]
            cursor_param = query.get("cursor", [""])[0]
            limit = int(query.get("limit", ["1000"])[0])

            matched = [k for k in sorted(self.kv.keys()) if k.startswith(prefix)]

            # Simulated pagination if many items
            start_idx = int(cursor_param) if cursor_param.isdigit() else 0
            page_items = matched[start_idx : start_idx + limit]
            next_idx = start_idx + limit
            next_cursor = str(next_idx) if next_idx < len(matched) else ""

            return httpx.Response(
                200,
                json={
                    "success": True,
                    "errors": [],
                    "messages": [],
                    "result": [{"name": k} for k in page_items],
                    "result_info": {"count": len(page_items), "cursor": next_cursor},
                },
            )

        return httpx.Response(404, text="Not Found")


@pytest.fixture
def mock_kv_handler() -> MockKVHandler:
    return MockKVHandler()


@pytest.fixture
def kv_store(mock_kv_handler: MockKVHandler) -> CloudflareKVStateStore:
    transport = httpx.MockTransport(mock_kv_handler.handle_request)
    client = httpx.Client(
        base_url="https://api.cloudflare.com/client/v4/accounts/test_account/storage/kv/namespaces/test_namespace",
        transport=transport,
    )
    return CloudflareKVStateStore(
        account_id="test_account",
        namespace_id="test_namespace",
        api_token="test_token",
        client=client,
    )


def test_kv_store_init_validation() -> None:
    """Test validation on CloudflareKVStateStore initialization."""
    with pytest.raises(ConfigError, match="account_id"):
        CloudflareKVStateStore(account_id="", namespace_id="ns", api_token="tok")

    with pytest.raises(ConfigError, match="namespace_id"):
        CloudflareKVStateStore(account_id="acc", namespace_id="", api_token="tok")

    with pytest.raises(ConfigError, match="api_token"):
        CloudflareKVStateStore(account_id="acc", namespace_id="ns", api_token="")

    # Accepts SecretStr
    store = CloudflareKVStateStore(
        account_id="acc", namespace_id="ns", api_token=SecretStr("secret_tok")
    )
    assert store.account_id == "acc"
    assert store.namespace_id == "ns"
    store.close()


def test_pending_actions_crud(kv_store: CloudflareKVStateStore) -> None:
    """Test write, read, list, and delete pending actions in KV."""
    now = datetime.now(UTC)
    item = PendingAction(
        item_id="item_001",
        action_type="approve_comment",
        created_at=now,
        post_urn="urn:li:activity:101",
        post_url="https://linkedin.com/feed/update/urn:li:activity:101",
        author_name="Alice",
        post_excerpt="Exploring AI agents.",
        draft_text="Insightful post on AI systems.",
        confidence=0.92,
        reasoning="Strong alignment with focus areas.",
        telegram_chat_id=12345,
        telegram_message_id=987,
    )

    # 1. Write pending action
    key = kv_store.write_pending(item)
    assert key == "pending:item_001"

    # 2. Read pending action
    fetched = kv_store.read_pending("item_001")
    assert fetched is not None
    assert fetched.item_id == "item_001"
    assert fetched.author_name == "Alice"
    assert fetched.draft_text == "Insightful post on AI systems."

    # 3. Read non-existent item
    assert kv_store.read_pending("non_existent") is None

    # 4. List pending actions
    items = kv_store.list_pending()
    assert len(items) == 1
    assert items[0].item_id == "item_001"

    # 5. Delete pending action
    deleted = kv_store.delete_pending("item_001")
    assert deleted is True
    assert kv_store.read_pending("item_001") is None

    # 6. Delete again returns False (not found)
    assert kv_store.delete_pending("item_001") is False


def test_find_pending_by_message_id(
    kv_store: CloudflareKVStateStore, mock_kv_handler: MockKVHandler
) -> None:
    """Test lookup of pending actions by Telegram message ID with secondary index."""
    item1 = PendingAction(
        item_id="item_a",
        action_type="approve_comment",
        draft_text="Draft A",
        telegram_message_id=111,
    )
    item2 = PendingAction(
        item_id="item_b",
        action_type="approve_comment",
        draft_text="Draft B",
        telegram_message_id=222,
    )
    kv_store.write_pending(item1)
    kv_store.write_pending(item2)

    # Verify secondary index keys are populated
    assert mock_kv_handler.kv.get("msg_id:111") == "item_a"
    assert mock_kv_handler.kv.get("msg_id:222") == "item_b"

    found = kv_store.find_pending_by_message_id(222)
    assert found is not None
    assert found.item_id == "item_b"

    assert kv_store.find_pending_by_message_id(999) is None

    # Delete item2 and verify secondary index key is cleaned up
    assert kv_store.delete_pending("item_b") is True
    assert "msg_id:222" not in mock_kv_handler.kv
    assert kv_store.find_pending_by_message_id(222) is None


def test_update_pending_draft(kv_store: CloudflareKVStateStore) -> None:
    """Test updating the draft text of an existing pending item."""
    item = PendingAction(
        item_id="item_edit",
        action_type="approve_comment",
        draft_text="Initial Draft",
    )
    kv_store.write_pending(item)

    updated = kv_store.update_pending_draft("item_edit", "Revised Draft Content")
    assert updated is not None
    assert updated.draft_text == "Revised Draft Content"

    # Read back from KV
    fetched = kv_store.read_pending("item_edit")
    assert fetched is not None
    assert fetched.draft_text == "Revised Draft Content"

    # Non-existent item returns None
    assert kv_store.update_pending_draft("unknown", "New text") is None


def test_prune_expired_pending(kv_store: CloudflareKVStateStore) -> None:
    """Test TTL pruning of expired pending suggestions."""
    now = datetime.now(UTC)
    fresh_item = PendingAction(
        item_id="fresh_1",
        action_type="approve_comment",
        created_at=now - timedelta(hours=2),
        draft_text="Fresh",
    )
    expired_item = PendingAction(
        item_id="expired_1",
        action_type="approve_comment",
        created_at=now - timedelta(hours=14),
        draft_text="Expired",
    )
    kv_store.write_pending(fresh_item)
    kv_store.write_pending(expired_item)

    pruned = kv_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(pruned) == 1
    assert pruned[0].item_id == "expired_1"

    # Verify expired item deleted and fresh item kept
    assert kv_store.read_pending("expired_1") is None
    assert kv_store.read_pending("fresh_1") is not None

    # Verify history recorded expiration
    history = kv_store.read_history()
    assert len(history) == 1
    assert history[0].item_id == "expired_1"
    assert history[0].final_status == "expired"


def test_history_append_and_read(kv_store: CloudflareKVStateStore) -> None:
    """Test history audit log append and limit-bounded reading."""
    assert kv_store.read_history() == []

    entry1 = HistoryEntry(
        item_id="hist_1",
        action_type="approve_comment",
        final_status="executed_success",
    )
    entry2 = HistoryEntry(
        item_id="hist_2",
        action_type="approve_post",
        final_status="rejected",
    )
    kv_store.append_history(entry1)
    kv_store.append_history(entry2)

    history = kv_store.read_history()
    assert len(history) == 2
    assert history[0].item_id == "hist_1"
    assert history[1].item_id == "hist_2"

    limited = kv_store.read_history(limit=1)
    assert len(limited) == 1
    assert limited[0].item_id == "hist_2"


def test_seen_posts_and_ttl_pruning(kv_store: CloudflareKVStateStore) -> None:
    """Test seen posts hash tracking and TTL pruning."""
    now = datetime.now(UTC)
    fresh_time = now.isoformat()
    old_time = (now - timedelta(days=35)).isoformat()

    kv_store.save_seen_hashes(
        {
            "fresh_hash": fresh_time,
            "old_hash": old_time,
        }
    )

    # load_seen_hashes prunes entries older than 30 days
    valid_hashes = kv_store.load_seen_hashes(ttl_days=30)
    assert "fresh_hash" in valid_hashes
    assert "old_hash" not in valid_hashes

    # record_seen_posts adds new posts
    post1 = PostRecord(
        post_urn="urn:li:activity:999",
        author_name="Bob",
        post_text="Content to hash",
        content_hash="hash_999",
        post_url="https://linkedin.com",
    )
    updated_set = kv_store.record_seen_posts([post1])
    assert post1.content_hash in updated_set
    assert "fresh_hash" in updated_set


def test_daily_counters_rollover_and_increments(kv_store: CloudflareKVStateStore) -> None:
    """Test daily counter auto-rollover and atomic increments."""
    today = date(2026, 9, 29)
    yesterday = date(2026, 9, 28)

    # Pre-populate yesterday counters
    kv_store.save_daily_counters(
        DailyCounters(
            date=yesterday.isoformat(),
            comments_executed=5,
            posts_executed=1,
            suggestions_sent=3,
        )
    )

    # Rollover to today resets to 0
    counters = kv_store.load_daily_counters(today=today)
    assert counters.date == today.isoformat()
    assert counters.comments_executed == 0
    assert counters.posts_executed == 0
    assert counters.suggestions_sent == 0

    # Increments
    updated = kv_store.increment_comment_count(today=today)
    assert updated.comments_executed == 1

    updated = kv_store.increment_post_count(today=today)
    assert updated.posts_executed == 1

    updated = kv_store.increment_suggestion_count(count=3, today=today)
    assert updated.suggestions_sent == 3


def test_pause_and_incident_state(kv_store: CloudflareKVStateStore) -> None:
    """Test remote pause and circuit breaker incident state."""
    # Pause state
    assert kv_store.is_paused() is False
    kv_store.set_paused(True)
    assert kv_store.is_paused() is True
    kv_store.set_paused(False)
    assert kv_store.is_paused() is False

    # Incident state
    assert kv_store.read_incident() is None
    kv_store.record_incident(
        reason="Challenge checkpoint detected", context={"url": "https://linkedin.com/checkpoint"}
    )
    incident = kv_store.read_incident()
    assert incident is not None
    assert incident["reason"] == "Challenge checkpoint detected"
    assert incident["context"]["url"] == "https://linkedin.com/checkpoint"

    # Clear incident
    cleared = kv_store.clear_incident()
    assert cleared is True
    assert kv_store.read_incident() is None
    assert kv_store.clear_incident() is False


def test_commit_and_push_noop(kv_store: CloudflareKVStateStore) -> None:
    """Test commit_and_push returns True without errors for KV backend."""
    assert kv_store.commit_and_push("test commit") is True


def test_error_handling(kv_store: CloudflareKVStateStore, mock_kv_handler: MockKVHandler) -> None:
    """Test proper exception raising on HTTP failures."""
    mock_kv_handler.fail_paths["failing_key"] = 500

    with pytest.raises(StateStoreError, match="status 500"):
        kv_store.read_pending("failing_key")


def test_get_state_store_factory(tmp_path: Path) -> None:
    """Test get_state_store factory selects correct backend based on settings."""
    # Default is git
    settings_git = Settings(
        nvidia_nim_api_key="key",
        telegram_bot_token="tok",
        telegram_authorized_chat_id=123,
        state_backend="git",
    )
    store_git = get_state_store(settings_git, tmp_path)
    assert isinstance(store_git, GitStateStore)

    # KV configuration
    settings_kv = Settings(
        nvidia_nim_api_key="key",
        telegram_bot_token="tok",
        telegram_authorized_chat_id=123,
        state_backend="kv",
        cloudflare_account_id="acc_123",
        cloudflare_kv_namespace_id="ns_456",
        cloudflare_api_token="cf_tok",
    )
    store_kv = get_state_store(settings_kv, tmp_path)
    assert isinstance(store_kv, CloudflareKVStateStore)
    assert store_kv.account_id == "acc_123"
    assert store_kv.namespace_id == "ns_456"
    store_kv.close()

    # Missing KV credentials when backend="kv" raises ConfigError
    settings_invalid_kv = Settings(
        nvidia_nim_api_key="key",
        telegram_bot_token="tok",
        telegram_authorized_chat_id=123,
        state_backend="kv",
        cloudflare_account_id=None,
    )
    with pytest.raises(ConfigError, match="CLOUDFLARE_ACCOUNT_ID"):
        get_state_store(settings_invalid_kv, tmp_path)
