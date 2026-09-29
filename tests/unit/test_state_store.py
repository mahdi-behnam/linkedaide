"""Unit tests for GitStateStore persistence and atomic state operations."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from agent.errors import StateStoreError
from agent.models.schemas import HistoryEntry, PendingAction, PostRecord
from agent.state.store import GitStateStore


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Initialize a clean local git repository fixture for testing state storage."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"], cwd=str(repo), check=True, capture_output=True
    )
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


@pytest.fixture
def multi_repo(tmp_path: Path) -> tuple[GitStateStore, GitStateStore, Path]:
    """Create a bare remote and two independent clone clients for concurrency testing."""
    bare = tmp_path / "remote.git"
    bare.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main"],
        cwd=str(bare),
        check=True,
        capture_output=True,
    )

    client_a_path = tmp_path / "client_a"
    client_a_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Client A"],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "a@example.com"],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )

    state_dir_a = client_a_path / "state"
    state_dir_a.mkdir(parents=True, exist_ok=True)
    (state_dir_a / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(client_a_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=str(client_a_path),
        check=True,
        capture_output=True,
    )

    client_b_path = tmp_path / "client_b"
    subprocess.run(
        ["git", "clone", str(bare), str(client_b_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Client B"],
        cwd=str(client_b_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "b@example.com"],
        cwd=str(client_b_path),
        check=True,
        capture_output=True,
    )

    store_a = GitStateStore(client_a_path)
    store_b = GitStateStore(client_b_path)
    return store_a, store_b, bare


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


def test_find_pending_by_message_id(state_store: GitStateStore) -> None:
    item1 = PendingAction(
        item_id="item_msg_1",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        draft_text="Draft text 1",
        telegram_message_id=1001,
    )
    item2 = PendingAction(
        item_id="item_msg_2",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        draft_text="Draft text 2",
        telegram_message_id=1002,
    )
    state_store.write_pending(item1)
    state_store.write_pending(item2)

    found1 = state_store.find_pending_by_message_id(1001)
    assert found1 is not None
    assert found1.item_id == "item_msg_1"

    found2 = state_store.find_pending_by_message_id(1002)
    assert found2 is not None
    assert found2.item_id == "item_msg_2"

    assert state_store.find_pending_by_message_id(9999) is None


def test_update_pending_draft(state_store: GitStateStore) -> None:
    item = PendingAction(
        item_id="item_draft_update",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        draft_text="Initial draft text",
        telegram_message_id=2001,
    )
    state_store.write_pending(item)

    # Valid update
    updated = state_store.update_pending_draft("item_draft_update", "Revised improved draft text")
    assert updated is not None
    assert updated.item_id == "item_draft_update"
    assert updated.draft_text == "Revised improved draft text"
    assert updated.telegram_message_id == 2001

    # Verify on disk
    loaded = state_store.read_pending("item_draft_update")
    assert loaded is not None
    assert loaded.draft_text == "Revised improved draft text"

    # Non-existent item returns None
    assert state_store.update_pending_draft("nonexistent_item", "Some text") is None


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


def test_commit_and_push_local(state_store: GitStateStore) -> None:
    # 1. No changes staged
    assert state_store.commit_and_push("No changes") is False

    # 2. Add pending item and commit locally
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
    assert state_store.commit_and_push("feat: state update", push=False) is True

    # 3. Subsequent commit returns False
    assert state_store.commit_and_push("No changes", push=False) is False


def test_commit_and_push_fast_forward(
    multi_repo: tuple[GitStateStore, GitStateStore, Path],
) -> None:
    store_a, store_b, _ = multi_repo

    item_a = PendingAction(
        item_id="item_a123",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:100",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:100/",
        author_name="Alice",
        post_excerpt="Fast forward test",
        draft_text="Alice draft text",
        confidence=0.95,
        reasoning="Relevant topic",
        telegram_chat_id=1234,
        telegram_message_id=10,
    )
    store_a.write_pending(item_a)

    # Push from Client A
    assert store_a.commit_and_push("feat: add item a", push=True) is True

    # Pull in Client B
    subprocess.run(["git", "pull"], cwd=str(store_b.repo_root), check=True, capture_output=True)
    loaded_b = store_b.read_pending("item_a123")
    assert loaded_b is not None
    assert loaded_b.item_id == "item_a123"
    assert loaded_b.draft_text == "Alice draft text"


def test_commit_and_push_rebase_retry_on_remote_movement(
    multi_repo: tuple[GitStateStore, GitStateStore, Path],
) -> None:
    store_a, store_b, _ = multi_repo

    item_a = PendingAction(
        item_id="item_a_move",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:201",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:201/",
        author_name="Alice",
        post_excerpt="Movement test A",
        draft_text="Comment A",
        confidence=0.88,
        reasoning="Reason A",
        telegram_chat_id=1234,
        telegram_message_id=21,
    )
    store_a.write_pending(item_a)
    assert store_a.commit_and_push("feat: add item a", push=True) is True

    # Client B concurrently creates item_b without pulling Client A's commit
    item_b = PendingAction(
        item_id="item_b_move",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:202",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:202/",
        author_name="Bob",
        post_excerpt="Movement test B",
        draft_text="Comment B",
        confidence=0.91,
        reasoning="Reason B",
        telegram_chat_id=1234,
        telegram_message_id=22,
    )
    store_b.write_pending(item_b)

    # Client B pushes with rebase retry (backoff_factor=0.0 for speed)
    pushed = store_b.commit_and_push(
        "feat: add item b", push=True, max_retries=3, backoff_factor=0.0
    )
    assert pushed is True

    # Sync Client A with remote to verify both items survived rebase
    subprocess.run(["git", "pull"], cwd=str(store_a.repo_root), check=True, capture_output=True)

    # Both items must be present in both repositories
    assert store_a.read_pending("item_a_move") is not None
    assert store_a.read_pending("item_b_move") is not None
    assert store_b.read_pending("item_a_move") is not None
    assert store_b.read_pending("item_b_move") is not None


def test_commit_and_push_rebase_conflict_aborts_and_cleans_repo(
    multi_repo: tuple[GitStateStore, GitStateStore, Path],
) -> None:
    store_a, store_b, _ = multi_repo

    conflict_file_a = store_a.state_dir / "conflict.txt"
    conflict_file_a.write_text("Client A conflicting version\n", encoding="utf-8")
    assert store_a.commit_and_push("feat: conflict change A", push=True) is True

    # Client B writes conflicting content to the same file
    conflict_file_b = store_b.state_dir / "conflict.txt"
    conflict_file_b.write_text("Client B conflicting version\n", encoding="utf-8")

    # Client B pushes with rebase retry; should abort rebase on conflict and raise StateStoreError
    with pytest.raises(StateStoreError) as exc_info:
        store_b.commit_and_push(
            "feat: conflict change B", push=True, max_retries=3, backoff_factor=0.0
        )

    assert "Git pull --rebase failed" in str(exc_info.value)

    # Verify Client B working tree is left completely clean (no in-progress rebase)
    status_proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(store_b.repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_proc.stdout.strip() == ""
    assert not (store_b.repo_root / ".git" / "rebase-merge").exists()
    assert not (store_b.repo_root / ".git" / "rebase-apply").exists()


def test_commit_and_push_max_retries_exhausted(
    multi_repo: tuple[GitStateStore, GitStateStore, Path],
) -> None:
    store_a, _, bare = multi_repo

    # Install a rejecting pre-receive hook on the bare remote to force push rejection
    hook_dir = bare / "hooks"
    hook_dir.mkdir(exist_ok=True)
    hook_file = hook_dir / "pre-receive"
    hook_file.write_text("#!/bin/sh\necho 'Hook rejected' >&2\nexit 1\n", encoding="utf-8")
    hook_file.chmod(0o755)

    item = PendingAction(
        item_id="item_retry_exhaust",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:300",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:300/",
        author_name="Charlie",
        post_excerpt="Retry exhaust",
        draft_text="Draft retry",
        confidence=0.85,
        reasoning="Test retry exhaust",
        telegram_chat_id=1234,
        telegram_message_id=30,
    )
    store_a.write_pending(item)

    with pytest.raises(StateStoreError) as exc_info:
        store_a.commit_and_push("feat: doomed commit", push=True, max_retries=3, backoff_factor=0.0)

    assert "Git push failed after 3 attempts" in str(exc_info.value)


def test_commit_and_push_explicit_remote_and_branch(
    multi_repo: tuple[GitStateStore, GitStateStore, Path],
) -> None:
    store_a, store_b, _ = multi_repo

    item = PendingAction(
        item_id="item_explicit_rb",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:400",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:400/",
        author_name="Diana",
        post_excerpt="Explicit remote branch test",
        draft_text="Explicit remote branch draft",
        confidence=0.9,
        reasoning="Test explicit params",
        telegram_chat_id=1234,
        telegram_message_id=40,
    )
    store_a.write_pending(item)

    assert (
        store_a.commit_and_push(
            "feat: explicit remote branch",
            push=True,
            remote="origin",
            branch="main",
            backoff_factor=0.0,
        )
        is True
    )

    # Verify pull in client B
    subprocess.run(["git", "pull"], cwd=str(store_b.repo_root), check=True, capture_output=True)
    loaded = store_b.read_pending("item_explicit_rb")
    assert loaded is not None
    assert loaded.item_id == "item_explicit_rb"


def test_commit_and_push_non_repo_error(tmp_path: Path) -> None:
    non_repo_dir = tmp_path / "not_a_repo"
    non_repo_dir.mkdir(parents=True, exist_ok=True)
    store = GitStateStore(non_repo_dir)

    item = PendingAction(
        item_id="item_non_repo",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:500",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:500/",
        author_name="Eve",
        post_excerpt="Non repo test",
        draft_text="Draft non repo",
        confidence=0.8,
        reasoning="Test non repo",
        telegram_chat_id=1234,
        telegram_message_id=50,
    )
    store.write_pending(item)

    with pytest.raises(StateStoreError) as exc_info:
        store.commit_and_push("feat: should fail", push=False)

    assert "Git commit/push failed" in str(exc_info.value)


def test_prune_expired_pending_empty_store(state_store: GitStateStore) -> None:
    pruned = state_store.prune_expired_pending(ttl_hours=12)
    assert pruned == []
    assert state_store.read_history() == []


def test_prune_expired_pending_only_fresh_items(state_store: GitStateStore) -> None:
    now = datetime.now(UTC)
    item1 = PendingAction(
        item_id="fresh_01",
        action_type="approve_comment",
        created_at=now - timedelta(hours=1),
        post_urn="urn:li:activity:101",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:101/",
        author_name="Alice",
        post_excerpt="Excerpt 1",
        draft_text="Draft 1",
        confidence=0.9,
        reasoning="Reason 1",
        telegram_chat_id=123,
        telegram_message_id=101,
    )
    item2 = PendingAction(
        item_id="fresh_02",
        action_type="approve_post",
        created_at=now - timedelta(hours=5),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft post 2",
        confidence=0.85,
        reasoning="Reason 2",
        telegram_chat_id=123,
        telegram_message_id=102,
    )
    state_store.write_pending(item1)
    state_store.write_pending(item2)

    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert pruned == []
    assert len(state_store.list_pending()) == 2
    assert state_store.read_history() == []


def test_prune_expired_pending_mixed_items(state_store: GitStateStore) -> None:
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    # 1. Expired item 1 (24 hours old)
    item_exp1 = PendingAction(
        item_id="exp_01",
        action_type="approve_comment",
        created_at=now - timedelta(hours=24),
        post_urn="urn:li:activity:201",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:201/",
        author_name="Bob",
        post_excerpt="Excerpt Exp 1",
        draft_text="Draft Exp 1",
        confidence=0.92,
        reasoning="Reason Exp 1",
        telegram_chat_id=123,
        telegram_message_id=201,
    )
    # 2. Fresh item (2 hours old)
    item_fresh = PendingAction(
        item_id="fresh_01",
        action_type="approve_comment",
        created_at=now - timedelta(hours=2),
        post_urn="urn:li:activity:202",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:202/",
        author_name="Charlie",
        post_excerpt="Excerpt Fresh 1",
        draft_text="Draft Fresh 1",
        confidence=0.88,
        reasoning="Reason Fresh 1",
        telegram_chat_id=123,
        telegram_message_id=202,
    )
    # 3. Expired item 2 (48 hours old)
    item_exp2 = PendingAction(
        item_id="exp_02",
        action_type="approve_post",
        created_at=now - timedelta(hours=48),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft Exp Post 2",
        confidence=0.8,
        reasoning="Reason Exp 2",
        telegram_chat_id=123,
        telegram_message_id=203,
    )

    state_store.write_pending(item_exp1)
    state_store.write_pending(item_fresh)
    state_store.write_pending(item_exp2)

    assert len(state_store.list_pending()) == 3

    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(pruned) == 2
    pruned_ids = {p.item_id for p in pruned}
    assert pruned_ids == {"exp_01", "exp_02"}

    # Disk assertions
    assert state_store.read_pending("exp_01") is None
    assert state_store.read_pending("exp_02") is None
    loaded_fresh = state_store.read_pending("fresh_01")
    assert loaded_fresh is not None
    assert loaded_fresh.item_id == "fresh_01"
    assert len(state_store.list_pending()) == 1

    # History audit trail assertions
    history = state_store.read_history()
    assert len(history) == 2
    h_by_id = {h.item_id: h for h in history}

    assert "exp_01" in h_by_id
    assert h_by_id["exp_01"].final_status == "expired"
    assert h_by_id["exp_01"].action_type == "approve_comment"
    assert h_by_id["exp_01"].decided_at is None
    assert h_by_id["exp_01"].executed_at == now
    assert h_by_id["exp_01"].error == "Pending approval expired (exceeded 12h TTL)"

    assert "exp_02" in h_by_id
    assert h_by_id["exp_02"].final_status == "expired"
    assert h_by_id["exp_02"].action_type == "approve_post"
    assert h_by_id["exp_02"].decided_at is None
    assert h_by_id["exp_02"].executed_at == now
    assert h_by_id["exp_02"].error == "Pending approval expired (exceeded 12h TTL)"


def test_prune_expired_pending_naive_datetimes(state_store: GitStateStore) -> None:
    # Test naive datetime handling
    naive_created = datetime(2026, 9, 1, 0, 0, 0)
    naive_now = datetime(2026, 9, 2, 12, 0, 0)

    item = PendingAction(
        item_id="naive_exp",
        action_type="approve_comment",
        created_at=naive_created,
        post_urn="urn:li:activity:301",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:301/",
        author_name="Diana",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.9,
        reasoning="Reason",
        telegram_chat_id=123,
        telegram_message_id=301,
    )
    state_store.write_pending(item)

    pruned = state_store.prune_expired_pending(ttl_hours=12, now=naive_now)
    assert len(pruned) == 1
    assert pruned[0].item_id == "naive_exp"
    assert state_store.read_pending("naive_exp") is None
    history = state_store.read_history()
    assert len(history) == 1
    assert history[0].final_status == "expired"


def test_pause_state_management(state_store: GitStateStore) -> None:
    assert state_store.is_paused() is False

    # Pause
    state_store.set_paused(True)
    assert state_store.is_paused() is True
    assert state_store.pause_path.exists() is True

    # Resume
    state_store.set_paused(False)
    assert state_store.is_paused() is False
    assert state_store.pause_path.exists() is False


def test_incident_state_management(state_store: GitStateStore) -> None:
    # Initially no incident
    assert state_store.read_incident() is None
    assert state_store.clear_incident() is False

    # Create incident
    incident_data = {
        "created_at": "2026-09-03T19:00:00+00:00",
        "tripped_at": "2026-09-03T19:00:00+00:00",
        "reason": "Test incident reason",
        "context": {"key": "val"},
    }
    state_store.incident_path.write_text(json.dumps(incident_data), encoding="utf-8")

    # Read incident
    read_data = state_store.read_incident()
    assert read_data is not None
    assert read_data["reason"] == "Test incident reason"

    # Clear incident
    cleared = state_store.clear_incident()
    assert cleared is True
    assert state_store.incident_path.exists() is False
    assert state_store.read_incident() is None

    # Test corrupted incident file
    state_store.incident_path.write_text("invalid json {{{", encoding="utf-8")
    corrupted_data = state_store.read_incident()
    assert corrupted_data is not None
    assert "Corrupted" in corrupted_data["reason"]
    assert state_store.clear_incident() is True
