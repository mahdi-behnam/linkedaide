"""Integration tests for HealthCheckGraph canary workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import BotDetectionError
from agent.graphs.health_graph import build_health_graph
from agent.graphs.state import GraphContext, HealthCheckState
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
        state_dir=test_repo / "state",
    )
    state_store = GitStateStore(test_repo)
    mock_telegram: Any = MagicMock()
    mock_telegram.send_notification = AsyncMock()
    mock_executor: Any = MagicMock()

    return GraphContext(
        settings=settings,
        state_store=state_store,
        telegram=mock_telegram,
        executor=mock_executor,
    )


@pytest.mark.asyncio
async def test_health_graph_healthy(mock_context: GraphContext) -> None:
    executor_mock: Any = mock_context.executor
    executor_mock.verify_login = AsyncMock(return_value=True)

    graph = build_health_graph()
    initial_state: HealthCheckState = {}
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["is_healthy"] is True
    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_graph_bot_challenge_trips_breaker(mock_context: GraphContext) -> None:
    executor_mock: Any = mock_context.executor
    executor_mock.verify_login = AsyncMock(
        side_effect=BotDetectionError("CAPTCHA checkpoint on health check")
    )

    graph = build_health_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert result["is_healthy"] is False
    assert result["status"] == "halted_challenge"

    incident_file = mock_context.settings.state_dir / "incident.json"
    assert incident_file.exists()
