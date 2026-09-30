"""Adversarial challenge and stress-testing suite for GitStateStore concurrency and rebase."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import StateStoreError, TelegramAPIError
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext
from agent.models import HistoryEntry, PendingAction
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient


@pytest.fixture
def multi_client_remote(tmp_path: Path) -> tuple[GitStateStore, GitStateStore, GitStateStore, Path]:
    """Create a bare remote and 3 independent clones for multi-client concurrency testing."""
    bare = tmp_path / "remote.git"
    bare.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main"],
        cwd=str(bare),
        check=True,
        capture_output=True,
    )

    # Initialize client A with base commit
    client_a = tmp_path / "client_a"
    client_a.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"], cwd=str(client_a), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Client A"],
        cwd=str(client_a),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "a@test.com"],
        cwd=str(client_a),
        check=True,
        capture_output=True,
    )

    state_dir_a = client_a / "state"
    state_dir_a.mkdir(parents=True, exist_ok=True)
    (state_dir_a / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(client_a), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(client_a),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)],
        cwd=str(client_a),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"], cwd=str(client_a), check=True, capture_output=True
    )

    # Clone client B
    client_b = tmp_path / "client_b"
    subprocess.run(["git", "clone", str(bare), str(client_b)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Client B"],
        cwd=str(client_b),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "b@test.com"],
        cwd=str(client_b),
        check=True,
        capture_output=True,
    )

    # Clone client C
    client_c = tmp_path / "client_c"
    subprocess.run(["git", "clone", str(bare), str(client_c)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Client C"],
        cwd=str(client_c),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "c@test.com"],
        cwd=str(client_c),
        check=True,
        capture_output=True,
    )

    store_a = GitStateStore(client_a)
    store_b = GitStateStore(client_b)
    store_c = GitStateStore(client_c)
    return store_a, store_b, store_c, bare


def test_adv_concurrent_remote_movement_3_commits_ahead(
    multi_client_remote: tuple[GitStateStore, GitStateStore, GitStateStore, Path],
) -> None:
    """Stress-test: remote branch moves forward by 3 separate commits while Client B prepares a commit.

    Client B's commit_and_push must rebase across all 3 remote commits cleanly and push.
    """
    store_a, store_b, _, _ = multi_client_remote
    now = datetime.now(UTC)

    # Client A pushes commit 1
    item_a1 = PendingAction(
        item_id="item_a1",
        action_type="approve_comment",
        created_at=now,
        post_urn="urn:li:activity:101",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:101/",
        author_name="Alice",
        post_excerpt="Commit 1 excerpt",
        draft_text="Comment 1",
        confidence=0.9,
        reasoning="Reason 1",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    store_a.write_pending(item_a1)
    assert store_a.commit_and_push("feat: add item a1", push=True) is True

    # Client A pushes commit 2
    item_a2 = PendingAction(
        item_id="item_a2",
        action_type="approve_comment",
        created_at=now + timedelta(seconds=1),
        post_urn="urn:li:activity:102",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:102/",
        author_name="Alice",
        post_excerpt="Commit 2 excerpt",
        draft_text="Comment 2",
        confidence=0.9,
        reasoning="Reason 2",
        telegram_chat_id=123,
        telegram_message_id=2,
    )
    store_a.write_pending(item_a2)
    assert store_a.commit_and_push("feat: add item a2", push=True) is True

    # Client A pushes commit 3
    item_a3 = PendingAction(
        item_id="item_a3",
        action_type="approve_comment",
        created_at=now + timedelta(seconds=2),
        post_urn="urn:li:activity:103",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:103/",
        author_name="Alice",
        post_excerpt="Commit 3 excerpt",
        draft_text="Comment 3",
        confidence=0.9,
        reasoning="Reason 3",
        telegram_chat_id=123,
        telegram_message_id=3,
    )
    store_a.write_pending(item_a3)
    assert store_a.commit_and_push("feat: add item a3", push=True) is True

    # Remote is now 3 commits ahead of Client B.
    # Client B now writes item_b and executes commit_and_push.
    item_b = PendingAction(
        item_id="item_b1",
        action_type="approve_post",
        created_at=now + timedelta(seconds=3),
        post_urn="urn:li:activity:201",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:201/",
        author_name="Bob",
        post_excerpt="Commit B excerpt",
        draft_text="Post B draft",
        confidence=0.95,
        reasoning="Reason B",
        telegram_chat_id=123,
        telegram_message_id=4,
    )
    store_b.write_pending(item_b)

    # Client B pushes; automatic rebase pulls all 3 commits and replays item_b cleanly
    pushed = store_b.commit_and_push(
        "feat: add item b1", push=True, max_retries=3, backoff_factor=0.0
    )
    assert pushed is True

    # Verify all 4 items exist in Client B
    assert store_b.read_pending("item_a1") is not None
    assert store_b.read_pending("item_a2") is not None
    assert store_b.read_pending("item_a3") is not None
    assert store_b.read_pending("item_b1") is not None

    # Pull in Client A and verify all 4 items exist in Client A
    subprocess.run(["git", "pull"], cwd=str(store_a.repo_root), check=True, capture_output=True)
    assert store_a.read_pending("item_a1") is not None
    assert store_a.read_pending("item_a2") is not None
    assert store_a.read_pending("item_a3") is not None
    assert store_a.read_pending("item_b1") is not None

    # Verify commit log is linear
    log_proc = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=str(store_b.repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    log_lines = log_proc.stdout.strip().splitlines()
    # Initial + 3 from A + 1 from B = 5 commits
    assert len(log_lines) == 5


def test_adv_rebase_conflict_aborts_and_leaves_working_tree_completely_clean(
    multi_client_remote: tuple[GitStateStore, GitStateStore, GitStateStore, Path],
) -> None:
    """Stress-test: unresolvable rebase conflict triggers git rebase --abort, leaving working tree 100% clean."""
    store_a, store_b, _, _ = multi_client_remote

    # Client A writes conflict file and pushes
    conflict_file_a = store_a.state_dir / "conflict_target.json"
    conflict_file_a.write_text('{"version": "A", "data": [1, 2, 3]}\n', encoding="utf-8")
    assert store_a.commit_and_push("feat: conflicting state from A", push=True) is True

    # Client B writes divergent conflict file
    conflict_file_b = store_b.state_dir / "conflict_target.json"
    conflict_file_b.write_text('{"version": "B", "data": [4, 5, 6]}\n', encoding="utf-8")

    # Client B attempts commit_and_push
    with pytest.raises(StateStoreError) as exc_info:
        store_b.commit_and_push(
            "feat: conflicting state from B", push=True, max_retries=3, backoff_factor=0.0
        )

    assert "Git pull --rebase failed during push retry" in str(exc_info.value)

    # Assert working tree is completely clean and not stuck in rebasing state
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

    # Verify Client B can still execute subsequent valid git commands without error
    branch_proc = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(store_b.repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_proc.stdout.strip() == "main"


def test_adv_max_retries_exhaustion_preserves_local_commit(
    multi_client_remote: tuple[GitStateStore, GitStateStore, GitStateStore, Path],
) -> None:
    """Stress-test: continuous push failures exhaust max_retries, raising StateStoreError while preserving local commit."""
    store_a, _, _, bare = multi_client_remote

    # Install rejecting pre-receive hook
    hook_dir = bare / "hooks"
    hook_dir.mkdir(exist_ok=True)
    hook_file = hook_dir / "pre-receive"
    hook_file.write_text(
        "#!/bin/sh\necho 'Remote push rejected by server policy' >&2\nexit 1\n", encoding="utf-8"
    )
    hook_file.chmod(0o755)

    item = PendingAction(
        item_id="item_doomed_001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:999",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:999/",
        author_name="Doomed Author",
        post_excerpt="Doomed excerpt",
        draft_text="Doomed draft",
        confidence=0.5,
        reasoning="Doomed reason",
        telegram_chat_id=123,
        telegram_message_id=99,
    )
    store_a.write_pending(item)

    with pytest.raises(StateStoreError) as exc_info:
        store_a.commit_and_push("feat: doomed item", push=True, max_retries=3, backoff_factor=0.0)

    assert "Git push failed after 3 attempts" in str(exc_info.value)

    # Local commit is preserved in the local Git object store (state not lost locally)
    log_proc = subprocess.run(
        ["git", "log", "-n", "1", "--format=%s"],
        cwd=str(store_a.repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    assert log_proc.stdout.strip() == "feat: doomed item"
    assert store_a.read_pending("item_doomed_001") is not None


def test_adv_three_client_concurrent_race_and_history_integrity(
    multi_client_remote: tuple[GitStateStore, GitStateStore, GitStateStore, Path],
) -> None:
    """Stress-test: 3 concurrent clients (A, B, C) perform interleaved mutations and pushes."""
    store_a, store_b, store_c, _ = multi_client_remote
    now = datetime.now(UTC)

    # Client A creates pending A and appends history A
    item_a = PendingAction(
        item_id="race_item_a",
        action_type="approve_comment",
        created_at=now,
        post_urn="urn:li:activity:301",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:301/",
        author_name="Alice",
        post_excerpt="Race excerpt A",
        draft_text="Draft A",
        confidence=0.9,
        reasoning="Race A",
        telegram_chat_id=123,
        telegram_message_id=31,
    )
    store_a.write_pending(item_a)
    store_a.append_history(
        HistoryEntry(
            item_id="race_item_a",
            action_type="approve_comment",
            final_status="executed_success",
            decided_at=now,
            executed_at=now + timedelta(seconds=5),
            screenshot_path="debug/a.png",
            error=None,
        )
    )
    assert store_a.commit_and_push("feat: client a race commit", push=True) is True

    # Client B concurrently creates pending B (without pulling A first)
    item_b = PendingAction(
        item_id="race_item_b",
        action_type="approve_post",
        created_at=now + timedelta(seconds=1),
        post_urn="urn:li:activity:302",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:302/",
        author_name="Bob",
        post_excerpt="Race excerpt B",
        draft_text="Draft B",
        confidence=0.85,
        reasoning="Race B",
        telegram_chat_id=123,
        telegram_message_id=32,
    )
    store_b.write_pending(item_b)
    assert (
        store_b.commit_and_push(
            "feat: client b race commit", push=True, max_retries=3, backoff_factor=0.0
        )
        is True
    )

    # Client C concurrently creates pending C (without pulling A or B first)
    item_c = PendingAction(
        item_id="race_item_c",
        action_type="approve_comment",
        created_at=now + timedelta(seconds=2),
        post_urn="urn:li:activity:303",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:303/",
        author_name="Charlie",
        post_excerpt="Race excerpt C",
        draft_text="Draft C",
        confidence=0.88,
        reasoning="Race C",
        telegram_chat_id=123,
        telegram_message_id=33,
    )
    store_c.write_pending(item_c)
    assert (
        store_c.commit_and_push(
            "feat: client c race commit", push=True, max_retries=3, backoff_factor=0.0
        )
        is True
    )

    # Sync all clients
    subprocess.run(["git", "pull"], cwd=str(store_a.repo_root), check=True, capture_output=True)
    subprocess.run(["git", "pull"], cwd=str(store_b.repo_root), check=True, capture_output=True)
    subprocess.run(["git", "pull"], cwd=str(store_c.repo_root), check=True, capture_output=True)

    # Verify all 3 pending items are present in all 3 client repositories
    for store in (store_a, store_b, store_c):
        assert store.read_pending("race_item_a") is not None
        assert store.read_pending("race_item_b") is not None
        assert store.read_pending("race_item_c") is not None
        pending_list = store.list_pending()
        assert len(pending_list) == 3


@pytest.mark.asyncio
async def test_adv_telegram_client_edit_to_outcome_payload_format(
    tmp_path: Path,
) -> None:
    """Stress-test: verify TelegramClient.edit_to_outcome sends exact expected wire payload."""
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
        telegram_authorized_chat_id=987654321,
        user_focus_areas=["AI"],
        dry_run=False,
    )

    captured_requests: list[dict[str, Any]] = []

    def transport_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        captured_requests.append(
            {
                "url": str(request.url),
                "method": request.method,
                "json": payload,
            }
        )
        return httpx.Response(
            200, json={"ok": True, "result": {"message_id": payload["message_id"]}}
        )

    transport = httpx.MockTransport(transport_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = TelegramClient(settings=settings, http_client=http_client)
        await client.edit_to_outcome(
            chat_id=987654321,
            message_id=42,
            outcome_text="⏱️ Suggestion expired (exceeded approval TTL)",
        )

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req["method"] == "POST"
    assert (
        req["url"]
        == "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/editMessageText"
    )
    assert req["json"]["chat_id"] == 987654321
    assert req["json"]["message_id"] == 42
    assert req["json"]["text"] == "⏱️ Suggestion expired (exceeded approval TTL)"
    assert req["json"]["parse_mode"] == "HTML"
    assert req["json"]["link_preview_options"] == {"is_disabled": True}
    assert req["json"]["reply_markup"] == {"inline_keyboard": []}


@pytest.mark.asyncio
async def test_adv_telegram_client_edit_to_outcome_handles_message_not_modified(
    tmp_path: Path,
) -> None:
    """Stress-test: Telegram 400 'message is not modified' error is caught and ignored gracefully."""
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123456:token"),
        telegram_authorized_chat_id=111,
        user_focus_areas=["AI"],
    )

    def not_modified_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message",
            },
        )

    transport = httpx.MockTransport(not_modified_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = TelegramClient(settings=settings, http_client=http_client)
        # Must not raise an exception
        await client.edit_to_outcome(
            chat_id=111,
            message_id=50,
            outcome_text="⏱️ Suggestion expired (exceeded approval TTL)",
        )


@pytest.mark.asyncio
async def test_adv_scout_graph_prune_heterogeneous_batch_with_unhandled_telegram_exceptions(
    tmp_path: Path,
) -> None:
    """Stress-test: ScoutGraph pruning with a heterogeneous batch of items:
    - 2 fresh items (not pruned)
    - 1 expired item with successful Telegram outcome update
    - 1 expired item where Telegram raises TelegramAPIError (HTTP 403 bot blocked)
    - 1 expired item where Telegram raises httpx.ConnectTimeout (network failure)
    - 1 expired item where Telegram raises generic unhandled RuntimeError
    - 1 expired item with telegram_message_id = 0 (skipped telegram)
    - 1 expired item with telegram_message_id = None (skipped telegram)
    - 1 expired item with custom telegram_chat_id = 999999
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(repo), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    (repo / "state").mkdir(parents=True, exist_ok=True)
    (repo / "state" / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)

    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        max_suggestions_per_run=3,
        pending_action_ttl_hours=12,
        state_dir=repo / "state",
        dry_run=True,
    )
    store = GitStateStore(repo)

    now = datetime(2026, 9, 2, 14, 0, 0, tzinfo=UTC)

    # 1. Fresh item 1 (1 hour old)
    item_fresh_1 = PendingAction(
        item_id="fresh_001",
        action_type="approve_comment",
        created_at=now - timedelta(hours=1),
        post_urn="urn:li:activity:f1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:f1/",
        author_name="Fresh Author 1",
        post_excerpt="Fresh 1",
        draft_text="Draft 1",
        confidence=0.9,
        reasoning="Fresh 1",
        telegram_chat_id=12345,
        telegram_message_id=1001,
    )
    # 2. Fresh item 2 (11 hours old, within 12h TTL)
    item_fresh_2 = PendingAction(
        item_id="fresh_002",
        action_type="approve_post",
        created_at=now - timedelta(hours=11),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft 2",
        confidence=0.85,
        reasoning="Fresh 2",
        telegram_chat_id=12345,
        telegram_message_id=1002,
    )
    # 3. Expired item: Telegram succeeds (13 hours old)
    item_exp_ok = PendingAction(
        item_id="exp_ok_001",
        action_type="approve_comment",
        created_at=now - timedelta(hours=13),
        post_urn="urn:li:activity:e1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:e1/",
        author_name="Exp Author OK",
        post_excerpt="Exp OK",
        draft_text="Draft Exp OK",
        confidence=0.9,
        reasoning="Exp OK",
        telegram_chat_id=12345,
        telegram_message_id=2001,
    )
    # 4. Expired item: Telegram 403 Forbidden
    item_exp_403 = PendingAction(
        item_id="exp_403_002",
        action_type="approve_comment",
        created_at=now - timedelta(hours=15),
        post_urn="urn:li:activity:e2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:e2/",
        author_name="Exp Author 403",
        post_excerpt="Exp 403",
        draft_text="Draft Exp 403",
        confidence=0.9,
        reasoning="Exp 403",
        telegram_chat_id=12345,
        telegram_message_id=2002,
    )
    # 5. Expired item: Telegram ConnectTimeout
    item_exp_timeout = PendingAction(
        item_id="exp_timeout_003",
        action_type="approve_comment",
        created_at=now - timedelta(hours=20),
        post_urn="urn:li:activity:e3",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:e3/",
        author_name="Exp Author Timeout",
        post_excerpt="Exp Timeout",
        draft_text="Draft Exp Timeout",
        confidence=0.9,
        reasoning="Exp Timeout",
        telegram_chat_id=12345,
        telegram_message_id=2003,
    )
    # 6. Expired item: generic unhandled RuntimeError
    item_exp_runtime = PendingAction(
        item_id="exp_runtime_004",
        action_type="approve_comment",
        created_at=now - timedelta(hours=25),
        post_urn="urn:li:activity:e4",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:e4/",
        author_name="Exp Author Runtime",
        post_excerpt="Exp Runtime",
        draft_text="Draft Exp Runtime",
        confidence=0.9,
        reasoning="Exp Runtime",
        telegram_chat_id=12345,
        telegram_message_id=2004,
    )
    # 7. Expired item: message_id = 0
    item_exp_msg0 = PendingAction(
        item_id="exp_msg0_005",
        action_type="approve_comment",
        created_at=now - timedelta(hours=30),
        post_urn="urn:li:activity:e5",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:e5/",
        author_name="Exp Author Msg0",
        post_excerpt="Exp Msg0",
        draft_text="Draft Exp Msg0",
        confidence=0.9,
        reasoning="Exp Msg0",
        telegram_chat_id=12345,
        telegram_message_id=0,
    )
    # 8. Expired item: custom chat_id
    item_exp_custom_chat = PendingAction(
        item_id="exp_custom_006",
        action_type="approve_post",
        created_at=now - timedelta(hours=35),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft Exp Custom Chat",
        confidence=0.9,
        reasoning="Exp Custom Chat",
        telegram_chat_id=999999,
        telegram_message_id=2006,
    )

    for item in [
        item_fresh_1,
        item_fresh_2,
        item_exp_ok,
        item_exp_403,
        item_exp_timeout,
        item_exp_runtime,
        item_exp_msg0,
        item_exp_custom_chat,
    ]:
        store.write_pending(item)

    assert len(store.list_pending()) == 8

    # Set up Telegram mock with selective failures per message_id
    telegram_calls: list[dict[str, Any]] = []

    async def mock_edit_to_outcome(chat_id: int, message_id: int, outcome_text: str) -> None:
        telegram_calls.append(
            {"chat_id": chat_id, "message_id": message_id, "outcome_text": outcome_text}
        )
        if message_id == 2002:
            raise TelegramAPIError(
                "Forbidden: bot was blocked by the user", details={"status_code": 403}
            )
        elif message_id == 2003:
            raise httpx.ConnectTimeout("Connection timed out to api.telegram.org")
        elif message_id == 2004:
            raise RuntimeError("Unexpected internal crash in telegram serializer")

    mock_telegram = MagicMock()
    mock_telegram.edit_to_outcome = AsyncMock(side_effect=mock_edit_to_outcome)

    mock_scraper = MagicMock()
    mock_scraper.scrape_feed = AsyncMock(return_value=[])

    context = GraphContext(
        settings=settings,
        llm=MagicMock(),
        state_store=store,
        telegram=mock_telegram,
        scraper=mock_scraper,
    )

    graph = build_scout_graph()

    # Invoke graph with fixed current time
    with patch("agent.state.store.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        result = await graph.ainvoke({}, config={"configurable": {"context": context}})

    # 1. Verify graph returned all 6 pruned items in state
    pruned_items = result.get("pruned_items", [])
    assert len(pruned_items) == 6
    pruned_ids = {p.item_id for p in pruned_items}
    assert pruned_ids == {
        "exp_ok_001",
        "exp_403_002",
        "exp_timeout_003",
        "exp_runtime_004",
        "exp_msg0_005",
        "exp_custom_006",
    }

    # 2. Verify all Telegram outcome calls had exact text and correct params
    assert len(telegram_calls) == 5  # msg_id=0 was skipped
    for call in telegram_calls:
        assert call["outcome_text"] == "⏱️ Suggestion expired (exceeded approval TTL)"

    called_msg_ids = {c["message_id"] for c in telegram_calls}
    assert called_msg_ids == {2001, 2002, 2003, 2004, 2006}

    # Verify custom chat_id was respected
    custom_call = next(c for c in telegram_calls if c["message_id"] == 2006)
    assert custom_call["chat_id"] == 999999

    # 3. Verify disk persistence: 6 pruned items deleted, 2 fresh items remain
    assert len(store.list_pending()) == 2
    remaining_ids = {p.item_id for p in store.list_pending()}
    assert remaining_ids == {"fresh_001", "fresh_002"}

    # 4. Verify history: exactly 6 expired records written
    history = store.read_history()
    assert len(history) == 6
    for h in history:
        assert h.final_status == "expired"
        assert h.error == "Pending approval expired (exceeded 12h TTL)"
        assert h.decided_at is None
