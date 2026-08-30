"""Unit tests for orchestration flows dependency wiring and exit behavior."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models.schemas import PendingAction
from agent.orchestration.execute_flow import run_execute_flow
from agent.orchestration.health_check_flow import run_health_check_flow
from agent.orchestration.poll_flow import run_poll_flow
from agent.orchestration.scout_flow import run_scout_flow
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
def base_settings(test_repo: Path) -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        state_dir=test_repo / "state",
        dry_run=True,
    )


@pytest.mark.asyncio
async def test_scout_flow_halted_guard(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_scout_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"


@pytest.mark.asyncio
async def test_execute_flow_reject_flow(test_repo: Path, base_settings: Settings) -> None:
    store = GitStateStore(test_repo)
    pending = PendingAction(
        item_id="rej_flow_1",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
        author_name="Author",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.8,
        reasoning="Reason",
        telegram_chat_id=12345,
        telegram_message_id=999,
    )
    store.write_pending(pending)

    with patch("agent.orchestration.execute_flow.TelegramClient") as MockTG:
        mock_tg_inst = MockTG.return_value
        mock_tg_inst.edit_to_outcome = AsyncMock()

        result = await run_execute_flow(
            action="reject",
            item_id="rej_flow_1",
            telegram_chat_id=12345,
            telegram_message_id=999,
            settings=base_settings,
            repo_root=test_repo,
        )

        assert result["status"] == "rejected"
        assert store.read_pending("rej_flow_1") is None


@pytest.mark.asyncio
async def test_health_check_flow_halted_guard(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_health_check_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"
    assert result["is_healthy"] is False


@pytest.mark.asyncio
async def test_poll_flow_processes_callback(test_repo: Path, base_settings: Settings) -> None:
    sample_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "callback_query": {
                    "id": "cb123",
                    "from": {"id": 12345},
                    "message": {"message_id": 888},
                    "data": "rej:item_poll_1",
                },
            }
        ],
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: sample_updates
        mock_get.return_value = mock_resp

        with patch("agent.orchestration.poll_flow.run_execute_flow") as mock_exec:
            mock_exec.return_value = {"status": "rejected"}

            results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
            assert len(results) == 1
            assert mock_exec.called
