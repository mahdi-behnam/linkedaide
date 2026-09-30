"""Integration tests for ExecuteGraph approval, rejection, and safety gates."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs.execute_graph import build_execute_graph
from agent.graphs.state import ExecuteState, GraphContext
from agent.models import ExecutionResult, PendingAction
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
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

    state_dir = repo / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
    return repo


@pytest.fixture
def mock_context(test_repo: Path) -> GraphContext:
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        max_comments_per_day=5,
        pending_action_ttl_hours=20,
        state_dir=test_repo / "state",
        dry_run=True,
    )
    state_store = GitStateStore(test_repo)
    enforcer = DailyCapEnforcer(settings)

    telegram = MagicMock()
    telegram.is_authorized = MagicMock(return_value=True)
    telegram.edit_to_outcome = AsyncMock()

    executor = MagicMock()
    executor.verify_login = AsyncMock(return_value=True)
    executor.verify_post_exists = AsyncMock(return_value=True)
    executor.post_comment = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            action_type="approve_comment",
            item_id="item1",
            comment_text="Sample",
            screenshot_path="path.png",
            error=None,
            executed_at=datetime.now(UTC),
        )
    )

    return GraphContext(
        settings=settings,
        state_store=state_store,
        telegram=telegram,
        executor=executor,
        enforcer=enforcer,
    )


@pytest.mark.asyncio
async def test_execute_graph_missing_pending_item(mock_context: GraphContext) -> None:
    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "nonexistent_item",
        "telegram_chat_id": 12345,
        "telegram_message_id": 500,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "already_handled"
    assert mock_context.telegram.edit_to_outcome.called  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_graph_reject_action(mock_context: GraphContext) -> None:
    pending = PendingAction(
        item_id="rej001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
        author_name="Author",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.9,
        reasoning="Fit",
        telegram_chat_id=12345,
        telegram_message_id=501,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "reject",
        "item_id": "rej001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 501,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "rejected"
    assert mock_context.state_store.read_pending("rej001") is None  # type: ignore[union-attr]

    history = mock_context.state_store.read_history()  # type: ignore[union-attr]
    assert len(history) == 1
    assert history[0].final_status == "rejected"


@pytest.mark.asyncio
async def test_execute_graph_approve_success(mock_context: GraphContext) -> None:
    pending = PendingAction(
        item_id="app001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:2/",
        author_name="Author 2",
        post_excerpt="Excerpt 2",
        draft_text="Great comment draft",
        confidence=0.95,
        reasoning="Good match",
        telegram_chat_id=12345,
        telegram_message_id=502,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "app001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 502,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "completed_success"
    assert mock_context.state_store.read_pending("app001") is None  # type: ignore[union-attr]

    counters = mock_context.state_store.load_daily_counters()  # type: ignore[union-attr]
    assert counters.comments_executed == 1


@pytest.mark.asyncio
async def test_execute_graph_expired_approval_rejected(mock_context: GraphContext) -> None:
    now = datetime.now(UTC)
    expired_pending = PendingAction(
        item_id="exp001",
        action_type="approve_comment",
        created_at=now - timedelta(hours=25),
        post_urn="urn:li:activity:3",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:3/",
        author_name="Author 3",
        post_excerpt="Excerpt 3",
        draft_text="Draft",
        confidence=0.85,
        reasoning="Reason",
        telegram_chat_id=12345,
        telegram_message_id=503,
    )
    mock_context.state_store.write_pending(expired_pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "exp001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 503,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "failed"
    assert "expired" in result["error"].lower()
    assert not mock_context.executor.post_comment.called  # type: ignore[union-attr]
