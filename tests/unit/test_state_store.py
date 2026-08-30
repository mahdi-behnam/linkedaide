"""Unit tests for GitStateStore persistence and atomic state operations."""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from agent.models.schemas import HistoryEntry, PendingAction, PostRecord
from agent.state.store import GitStateStore


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Initialize a clean local git repository fixture for testing state storage."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    state_dir = repo / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def state_store(temp_git_repo: Path) -> GitStateStore:
    return GitStateStore(temp_git_repo)


def test_pending_actions_crud(state_store: GitStateStore) -> None:
    now = datetime.now(UTC)
    item = PendingAction(
        item_id="a1b2c3d4",
        action_type="approve_comment",
        created_at=now,
        post_urn="urn:li:activity:12345",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:12345/",
        author_name="John Doe",
        post_excerpt="Exploring Python 3.14 async...",
        draft_text="Very exciting improvements!",
        confidence=0.92,
        reasoning="Relevant to Python AI focus",
        telegram_chat_id=123456789,
        telegram_message_id=4567,
    )

    # 1. Write pending
    written_path = state_store.write_pending(item)
    assert written_path.exists()

    # 2. Read pending
    loaded = state_store.read_pending("a1b2c3d4")
    assert loaded is not None
    assert loaded.item_id == "a1b2c3d4"
    assert loaded.draft_text == "Very exciting improvements!"

    # 3. Read non-existent
    assert state_store.read_pending("nonexistent") is None

    # 4. List pending
    item2 = item.model_copy(
        update={"item_id": "b2c3d4e5", "created_at": now + timedelta(minutes=1)}
    )
    state_store.write_pending(item2)
    all_pending = state_store.list_pending()
    assert len(all_pending) == 2
    assert [p.item_id for p in all_pending] == ["a1b2c3d4", "b2c3d4e5"]

    # 5. Delete pending
    assert state_store.delete_pending("a1b2c3d4") is True
    assert state_store.delete_pending("a1b2c3d4") is False
    assert state_store.read_pending("a1b2c3d4") is None
    assert len(state_store.list_pending()) == 1


def test_history_jsonl_append_and_read(state_store: GitStateStore) -> None:
    now = datetime.now(UTC)
    entry1 = HistoryEntry(
        item_id="item001",
        action_type="approve_comment",
        final_status="executed_success",
        decided_at=now,
        executed_at=now + timedelta(seconds=30),
        screenshot_path="debug/screenshots/item001.png",
        error=None,
    )
    entry2 = HistoryEntry(
        item_id="item002",
        action_type="approve_post",
        final_status="rejected",
        decided_at=now + timedelta(minutes=5),
        executed_at=None,
        screenshot_path=None,
        error=None,
    )

    state_store.append_history(entry1)
    state_store.append_history(entry2)

    history = state_store.read_history()
    assert len(history) == 2
    assert history[0].item_id == "item001"
    assert history[0].final_status == "executed_success"
    assert history[1].item_id == "item002"
    assert history[1].final_status == "rejected"

    # Test limit
    recent = state_store.read_history(limit=1)
    assert len(recent) == 1
    assert recent[0].item_id == "item002"


def test_seen_posts_hashes_and_ttl_pruning(state_store: GitStateStore) -> None:
    now = datetime.now(UTC)
    fresh_time = now.isoformat()
    stale_time = (now - timedelta(days=35)).isoformat()

    # Pre-populate seen hashes with fresh and stale entry
    state_store.save_seen_hashes(
        {
            "fresh_hash_123": fresh_time,
            "stale_hash_456": stale_time,
        }
    )

    # Load with 30 day TTL
    valid_hashes = state_store.load_seen_hashes(ttl_days=30)
    assert "fresh_hash_123" in valid_hashes
    assert "stale_hash_456" not in valid_hashes

    # Record new post
    new_post = PostRecord(
        post_urn="urn:li:activity:999",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:999/",
        author_name="Bob",
        post_text="New post about ML",
        content_hash="brand_new_hash_789",
        scraped_at=now,
    )
    updated_hashes = state_store.record_seen_posts([new_post])
    assert "brand_new_hash_789" in updated_hashes
    assert "fresh_hash_123" in updated_hashes


def test_daily_counters_rollover_and_increment(state_store: GitStateStore) -> None:
    day1 = date(2026, 8, 29)
    day2 = date(2026, 8, 30)

    # Initial load on Day 1
    c1 = state_store.load_daily_counters(today=day1)
    assert c1.date == "2026-08-29"
    assert c1.comments_executed == 0
    assert c1.posts_executed == 0
    assert c1.suggestions_sent == 0

    # Increments on Day 1
    state_store.increment_comment_count(today=day1)
    state_store.increment_comment_count(today=day1)
    state_store.increment_post_count(today=day1)
    state_store.increment_suggestion_count(count=3, today=day1)

    c1_updated = state_store.load_daily_counters(today=day1)
    assert c1_updated.comments_executed == 2
    assert c1_updated.posts_executed == 1
    assert c1_updated.suggestions_sent == 3

    # Date rollover to Day 2 automatically resets counts to 0
    c2 = state_store.load_daily_counters(today=day2)
    assert c2.date == "2026-08-30"
    assert c2.comments_executed == 0
    assert c2.posts_executed == 0
    assert c2.suggestions_sent == 0


def test_commit_and_push(state_store: GitStateStore) -> None:
    # 1. No changes staged
    assert state_store.commit_and_push("No changes") is False

    # 2. Add pending item and commit
    item = PendingAction(
        item_id="testcommit",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
        author_name="User",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.8,
        reasoning="Reason",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    state_store.write_pending(item)
    assert state_store.commit_and_push("feat: state update") is True

    # 3. Subsequent commit returns False
    assert state_store.commit_and_push("No changes") is False
