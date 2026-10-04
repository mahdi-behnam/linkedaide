"""Unit tests for orchestration flows dependency wiring and exit behavior."""

from __future__ import annotations

import os
import runpy
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models import PendingAction
from agent.orchestration.execute_flow import main as execute_main
from agent.orchestration.execute_flow import run_execute_flow
from agent.orchestration.health_check_flow import main as health_check_main
from agent.orchestration.health_check_flow import run_health_check_flow
from agent.orchestration.ideation_flow import main as ideation_main
from agent.orchestration.ideation_flow import run_ideation_flow
from agent.orchestration.poll_flow import (
    get_last_offset,
    run_poll_flow,
    set_last_offset,
)
from agent.orchestration.poll_flow import (
    main as poll_main,
)
from agent.orchestration.scout_flow import main as scout_main
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


def _create_mock_playwright() -> Any:
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw_cm = AsyncMock()
    mock_pw_cm.__aenter__.return_value = mock_pw
    mock_pw_cm.__aexit__.return_value = None
    return mock_pw_cm, mock_browser, mock_context, mock_page


# ============================================================================
# Scout Flow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_scout_flow_halted_guard(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_scout_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"


@pytest.mark.asyncio
async def test_scout_flow_success_execution(test_repo: Path, base_settings: Settings) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"status": "completed", "pending_items": [MagicMock()], "errors": []}
    )

    with (
        patch(
            "agent.orchestration.scout_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.scout_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.scout_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.scout_flow.build_scout_graph", return_value=mock_graph),
    ):
        result = await run_scout_flow(settings=base_settings, repo_root=test_repo, headless=True)

        assert result["status"] == "completed"
        assert len(result["pending_items"]) == 1
        mock_pw_cm.__aenter__.return_value.chromium.launch.assert_awaited_once_with(headless=True)
        mock_page.goto.assert_awaited_once_with(
            "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000
        )
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_scout_flow_navigation_warning(test_repo: Path, base_settings: Settings) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_page.goto.side_effect = Exception("Feed navigation timeout")

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"status": "completed", "pending_items": [], "errors": []}
    )

    with (
        patch(
            "agent.orchestration.scout_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.scout_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.scout_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.scout_flow.build_scout_graph", return_value=mock_graph),
    ):
        result = await run_scout_flow(settings=base_settings, repo_root=test_repo, headless=False)

        assert result["status"] == "completed"
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_scout_flow_default_args(test_repo: Path, base_settings: Settings) -> None:
    mock_pw_cm, mock_browser, mock_context, _ = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"status": "completed", "pending_items": [], "errors": []}
    )

    with (
        patch("agent.orchestration.scout_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.scout_flow.Path.cwd", return_value=test_repo),
        patch("agent.orchestration.scout_flow.LLMService"),
        patch(
            "agent.orchestration.scout_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.scout_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.scout_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.scout_flow.build_scout_graph", return_value=mock_graph),
    ):
        result = await run_scout_flow(settings=None, repo_root=None, headless=True)
        assert result["status"] == "completed"


def test_scout_main_success_default_args(base_settings: Settings) -> None:
    with (
        patch("sys.argv", ["scout_flow"]),
        patch("agent.orchestration.scout_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.scout_flow.run_scout_flow", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = {"status": "completed"}
        with pytest.raises(SystemExit) as exc:
            scout_main()
        assert exc.value.code == 0
        mock_run.assert_called_once_with(settings=base_settings, headless=True)


def test_scout_main_dry_run_and_headed(base_settings: Settings) -> None:
    with (
        patch("sys.argv", ["scout_flow", "--dry-run", "--headed"]),
        patch("agent.orchestration.scout_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.scout_flow.run_scout_flow", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = {"status": "completed"}
        with pytest.raises(SystemExit) as exc:
            scout_main()
        assert exc.value.code == 0
        assert mock_run.call_args.kwargs["headless"] is False
        assert mock_run.call_args.kwargs["settings"].dry_run is True


@pytest.mark.parametrize("error_status", ["halted_bot_detection", "scrape_error"])
def test_scout_main_error_statuses(base_settings: Settings, error_status: str) -> None:
    with (
        patch("sys.argv", ["scout_flow"]),
        patch("agent.orchestration.scout_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.scout_flow.run_scout_flow", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = {"status": error_status}
        with pytest.raises(SystemExit) as exc:
            scout_main()
        assert exc.value.code == 1


def test_scout_main_exception(base_settings: Settings, capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["scout_flow"]),
        patch("agent.orchestration.scout_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.scout_flow.run_scout_flow", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.side_effect = RuntimeError("Fatal crash in browser")
        with pytest.raises(SystemExit) as exc:
            scout_main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Fatal Scout error: Fatal crash in browser" in captured.err


def test_scout_flow_dunder_main(base_settings: Settings) -> None:
    def fake_asyncio_run(coro: Any) -> Any:
        coro.close()
        return {"status": "completed"}

    with (
        patch("sys.argv", ["scout_flow"]),
        patch("agent.config.load_settings", return_value=base_settings),
        patch("asyncio.run", side_effect=fake_asyncio_run),
    ):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("agent.orchestration.scout_flow", run_name="__main__")
        assert exc.value.code == 0


# ============================================================================
# Health Check Flow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_flow_halted_guard(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_health_check_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"
    assert result["is_healthy"] is False


@pytest.mark.asyncio
async def test_health_check_flow_success_execution(
    test_repo: Path, base_settings: Settings
) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "healthy", "is_healthy": True})

    with (
        patch(
            "agent.orchestration.health_check_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.health_check_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.health_check_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch(
            "agent.orchestration.health_check_flow.build_health_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_health_check_flow(settings=base_settings, repo_root=test_repo)

        assert result["is_healthy"] is True
        mock_pw_cm.__aenter__.return_value.chromium.launch.assert_awaited_once_with(headless=True)
        mock_page.goto.assert_awaited_once_with(
            "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000
        )
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check_flow_navigation_warning(
    test_repo: Path, base_settings: Settings
) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_page.goto.side_effect = Exception("Nav warning")

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "healthy", "is_healthy": True})

    with (
        patch(
            "agent.orchestration.health_check_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.health_check_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.health_check_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch(
            "agent.orchestration.health_check_flow.build_health_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_health_check_flow(settings=base_settings, repo_root=test_repo)

        assert result["is_healthy"] is True
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_check_flow_default_args(test_repo: Path, base_settings: Settings) -> None:
    mock_pw_cm, mock_browser, mock_context, _ = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "healthy", "is_healthy": True})

    with (
        patch("agent.orchestration.health_check_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.health_check_flow.Path.cwd", return_value=test_repo),
        patch(
            "agent.orchestration.health_check_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.health_check_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.health_check_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch(
            "agent.orchestration.health_check_flow.build_health_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_health_check_flow(settings=None, repo_root=None)
        assert result["is_healthy"] is True


def test_health_check_main_healthy() -> None:
    with patch(
        "agent.orchestration.health_check_flow.run_health_check_flow", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = {"is_healthy": True}
        with pytest.raises(SystemExit) as exc:
            health_check_main()
        assert exc.value.code == 0


@pytest.mark.parametrize("status_dict", [{"is_healthy": False}, {}])
def test_health_check_main_unhealthy(status_dict: dict[str, Any]) -> None:
    with patch(
        "agent.orchestration.health_check_flow.run_health_check_flow", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = status_dict
        with pytest.raises(SystemExit) as exc:
            health_check_main()
        assert exc.value.code == 1


def test_health_check_main_exception(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "agent.orchestration.health_check_flow.run_health_check_flow", new_callable=AsyncMock
    ) as mock_run:
        mock_run.side_effect = RuntimeError("Canary failure")
        with pytest.raises(SystemExit) as exc:
            health_check_main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Fatal Health Check error: Canary failure" in captured.err


def test_health_check_flow_dunder_main(base_settings: Settings) -> None:
    def fake_asyncio_run(coro: Any) -> Any:
        coro.close()
        return {"is_healthy": True}

    with (
        patch("sys.argv", ["health_check_flow"]),
        patch("agent.config.load_settings", return_value=base_settings),
        patch("asyncio.run", side_effect=fake_asyncio_run),
    ):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("agent.orchestration.health_check_flow", run_name="__main__")
        assert exc.value.code == 0


# ============================================================================
# Execute Flow Tests
# ============================================================================


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
async def test_execute_flow_halted_guard_paused(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_execute_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"
    assert "paused" in result["halted_reason"].lower()


@pytest.mark.asyncio
async def test_execute_flow_halted_guard_circuit_breaker(
    test_repo: Path, base_settings: Settings
) -> None:
    with patch(
        "agent.orchestration.execute_flow.is_halted",
        return_value=(True, "Circuit breaker tripped"),
    ):
        result = await run_execute_flow(settings=base_settings, repo_root=test_repo)
        assert result["status"] == "halted"
        assert result["halted_reason"] == "Circuit breaker tripped"


@pytest.mark.asyncio
async def test_execute_flow_approve_browser_execution_success(
    test_repo: Path, base_settings: Settings
) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "executed_success"})

    with (
        patch(
            "agent.orchestration.execute_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.execute_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.execute_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.execute_flow.build_execute_graph", return_value=mock_graph),
    ):
        result = await run_execute_flow(
            action="approve",
            item_id="item_app_1",
            settings=base_settings,
            repo_root=test_repo,
        )
        assert result["status"] == "executed_success"
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_flow_approve_browser_ensures_close_on_error(
    test_repo: Path, base_settings: Settings
) -> None:
    mock_pw_cm, mock_browser, mock_context, mock_page = _create_mock_playwright()
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Graph failure"))

    with (
        patch(
            "agent.orchestration.execute_flow.ensure_session_file",
            return_value=test_repo / "session.json",
        ),
        patch("agent.orchestration.execute_flow.async_playwright", return_value=mock_pw_cm),
        patch(
            "agent.orchestration.execute_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.execute_flow.build_execute_graph", return_value=mock_graph),
    ):
        with pytest.raises(RuntimeError, match="Graph failure"):
            await run_execute_flow(
                action="approve",
                item_id="item_app_err",
                settings=base_settings,
                repo_root=test_repo,
            )
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_flow_environment_variables_fallback(
    test_repo: Path, base_settings: Settings
) -> None:
    env_vars = {
        "ACTION": "reject",
        "ITEM_ID": "env_item_999",
        "TELEGRAM_CHAT_ID": "88888",
        "TELEGRAM_MESSAGE_ID": "777",
        "TELEGRAM_CALLBACK_QUERY_ID": "cb_env_42",
    }
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "rejected"})

    with (
        patch.dict(os.environ, env_vars),
        patch("agent.orchestration.execute_flow.build_execute_graph", return_value=mock_graph),
    ):
        result = await run_execute_flow(settings=base_settings, repo_root=test_repo)
        assert result["status"] == "rejected"
        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["action"] == "reject"
        assert call_args["item_id"] == "env_item_999"
        assert call_args["telegram_chat_id"] == 88888
        assert call_args["telegram_message_id"] == 777
        assert call_args["telegram_callback_query_id"] == "cb_env_42"


@pytest.mark.parametrize(
    "status,expected_exit",
    [
        ("executed_success", 0),
        ("rejected", 0),
        ("failed", 1),
        ("halted_challenge", 1),
        ("session_error", 1),
    ],
)
def test_execute_flow_main_cli_exit_codes(status: str, expected_exit: int) -> None:
    with patch(
        "agent.orchestration.execute_flow.run_execute_flow",
        new_callable=AsyncMock,
        return_value={"status": status},
    ):
        with pytest.raises(SystemExit) as exc:
            execute_main()
        assert exc.value.code == expected_exit


def test_execute_flow_main_cli_exception(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "agent.orchestration.execute_flow.run_execute_flow",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Fatal error in execute flow"),
    ):
        with pytest.raises(SystemExit) as exc:
            execute_main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Fatal Execute error" in captured.err


def test_execute_flow_dunder_main(base_settings: Settings) -> None:
    def fake_asyncio_run(coro: Any) -> Any:
        coro.close()
        return {"status": "executed_success"}

    with (
        patch("sys.argv", ["execute_flow"]),
        patch("agent.config.load_settings", return_value=base_settings),
        patch("asyncio.run", side_effect=fake_asyncio_run),
    ):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("agent.orchestration.execute_flow", run_name="__main__")
        assert exc.value.code == 0


# ============================================================================
# Poll Flow Tests
# ============================================================================


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


@pytest.mark.asyncio
async def test_poll_flow_http_error_returns_empty(test_repo: Path, base_settings: Settings) -> None:
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert results == []


@pytest.mark.asyncio
async def test_poll_flow_http_status_error_returns_empty(
    test_repo: Path, base_settings: Settings
) -> None:
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "502 Bad Gateway", request=MagicMock(), response=MagicMock()
        )
    )
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert results == []


@pytest.mark.asyncio
async def test_poll_flow_skips_non_callback_update(
    test_repo: Path, base_settings: Settings
) -> None:
    sample_updates = {
        "ok": True,
        "result": [
            {"update_id": 1, "message": {"text": "hello"}},
            {"update_id": 2},
        ],
    }
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: sample_updates
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert results == []


@pytest.mark.asyncio
async def test_poll_flow_skips_unauthorized_sender(
    test_repo: Path, base_settings: Settings
) -> None:
    sample_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "callback_query": {
                    "id": "cb_unauth",
                    "from": {"id": 999999},  # unauthorized
                    "message": {"message_id": 888},
                    "data": "app:item_poll_1",
                },
            }
        ],
    }
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: sample_updates
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert results == []


@pytest.mark.asyncio
async def test_poll_flow_skips_corrupted_callback_data(
    test_repo: Path, base_settings: Settings
) -> None:
    sample_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "callback_query": {
                    "id": "cb_bad",
                    "from": {"id": base_settings.telegram_authorized_chat_id},
                    "message": {"message_id": 888},
                    "data": "corrupted_payload_without_colon",
                },
            }
        ],
    }
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: sample_updates
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert results == []


@pytest.mark.asyncio
async def test_poll_flow_processes_approval_callback(
    test_repo: Path, base_settings: Settings
) -> None:
    sample_updates = {
        "ok": True,
        "result": [
            {
                "update_id": 1,
                "callback_query": {
                    "id": "cb_app_1",
                    "from": {"id": base_settings.telegram_authorized_chat_id},
                    "message": {"message_id": 444},
                    "data": "ac:item_app_1",
                },
            }
        ],
    }
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: sample_updates
    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        patch(
            "agent.orchestration.poll_flow.run_execute_flow",
            new_callable=AsyncMock,
            return_value={"status": "executed_success"},
        ) as mock_exec,
    ):
        results = await run_poll_flow(settings=base_settings, repo_root=test_repo)
        assert len(results) == 1
        assert results[0]["status"] == "executed_success"
        mock_exec.assert_awaited_once_with(
            action="approve",
            item_id="item_app_1",
            telegram_chat_id=base_settings.telegram_authorized_chat_id,
            telegram_message_id=444,
            telegram_callback_query_id="cb_app_1",
            settings=base_settings,
            repo_root=test_repo,
        )


@pytest.mark.asyncio
async def test_poll_flow_defaults_and_plain_str_token() -> None:
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: {"result": []}
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "plain_token_string"
    mock_settings.telegram_authorized_chat_id = 12345

    with (
        patch("agent.orchestration.poll_flow.load_settings", return_value=mock_settings),
        patch("httpx.AsyncClient.get", return_value=mock_resp) as mock_get,
    ):
        results = await run_poll_flow()
        assert results == []
        assert "plain_token_string" in mock_get.call_args[0][0]


def test_poll_flow_main_success() -> None:
    with patch(
        "agent.orchestration.poll_flow.run_poll_flow",
        new_callable=AsyncMock,
        return_value=[{"status": "ok"}],
    ):
        with pytest.raises(SystemExit) as exc:
            poll_main()
        assert exc.value.code == 0


def test_poll_flow_main_exception(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "agent.orchestration.poll_flow.run_poll_flow",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Poll error"),
    ):
        with pytest.raises(SystemExit) as exc:
            poll_main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Fatal Poll error" in captured.err


def test_poll_flow_dunder_main(base_settings: Settings) -> None:
    def fake_asyncio_run(coro: Any) -> Any:
        coro.close()
        return [{"status": "ok"}]

    with (
        patch("sys.argv", ["poll_flow"]),
        patch("agent.config.load_settings", return_value=base_settings),
        patch("asyncio.run", side_effect=fake_asyncio_run),
    ):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("agent.orchestration.poll_flow", run_name="__main__")
        assert exc.value.code == 0


@pytest.mark.asyncio
async def test_poll_flow_tracks_and_advances_offset(
    test_repo: Path, base_settings: Settings
) -> None:
    set_last_offset(None)
    sample_updates = {
        "ok": True,
        "result": [
            {"update_id": 42, "message": {"text": "unrelated"}},
            {"update_id": 45, "message": {"text": "unrelated"}},
        ],
    }

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: sample_updates

    with patch("httpx.AsyncClient.get", return_value=mock_resp) as mock_get:
        await run_poll_flow(settings=base_settings, repo_root=test_repo)
        # Verify first call had no offset
        first_call_params = mock_get.call_args[1]["params"]
        assert "offset" not in first_call_params
        # Offset should advance to max(42, 45) + 1 = 46
        assert get_last_offset() == 46

        # Second poll should use tracked offset 46
        await run_poll_flow(settings=base_settings, repo_root=test_repo)
        second_call_params = mock_get.call_args[1]["params"]
        assert second_call_params["offset"] == 46

    set_last_offset(None)


@pytest.mark.asyncio
async def test_poll_flow_explicit_offset_override(test_repo: Path, base_settings: Settings) -> None:
    set_last_offset(10)
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: {"ok": True, "result": []}

    with patch("httpx.AsyncClient.get", return_value=mock_resp) as mock_get:
        await run_poll_flow(settings=base_settings, repo_root=test_repo, offset=999)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["offset"] == 999

    set_last_offset(None)


# ============================================================================
# Ideation Flow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ideation_flow_halted_guard(test_repo: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    result = await run_ideation_flow(settings=paused_settings, repo_root=test_repo)
    assert result["status"] == "halted"
    assert "paused" in result["halted_reason"].lower()


@pytest.mark.asyncio
async def test_ideation_flow_success_execution(test_repo: Path, base_settings: Settings) -> None:
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"status": "completed", "pending_items": [MagicMock()], "errors": []}
    )

    with (
        patch("agent.orchestration.ideation_flow.LLMService"),
        patch("agent.orchestration.ideation_flow.TelegramClient"),
        patch(
            "agent.orchestration.ideation_flow.build_ideation_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_ideation_flow(settings=base_settings, repo_root=test_repo)

        assert result["status"] == "completed"
        assert len(result["pending_items"]) == 1
        mock_graph.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_ideation_flow_default_args(test_repo: Path, base_settings: Settings) -> None:
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"status": "completed", "pending_items": [], "errors": []}
    )

    with (
        patch("agent.orchestration.ideation_flow.load_settings", return_value=base_settings),
        patch("agent.orchestration.ideation_flow.Path.cwd", return_value=test_repo),
        patch("agent.orchestration.ideation_flow.LLMService"),
        patch("agent.orchestration.ideation_flow.TelegramClient"),
        patch(
            "agent.orchestration.ideation_flow.build_ideation_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_ideation_flow(settings=None, repo_root=None)
        assert result["status"] == "completed"


def test_ideation_main_success_default_args(base_settings: Settings) -> None:
    with (
        patch("sys.argv", ["ideation_flow"]),
        patch("agent.orchestration.ideation_flow.load_settings", return_value=base_settings),
        patch(
            "agent.orchestration.ideation_flow.run_ideation_flow",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        mock_run.return_value = {"status": "completed"}
        with pytest.raises(SystemExit) as exc:
            ideation_main()
        assert exc.value.code == 0
        mock_run.assert_called_once_with(settings=base_settings)


def test_ideation_main_dry_run(base_settings: Settings) -> None:
    with (
        patch("sys.argv", ["ideation_flow", "--dry-run"]),
        patch("agent.orchestration.ideation_flow.load_settings", return_value=base_settings),
        patch(
            "agent.orchestration.ideation_flow.run_ideation_flow",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        mock_run.return_value = {"status": "completed_dry_run"}
        with pytest.raises(SystemExit) as exc:
            ideation_main()
        assert exc.value.code == 0
        assert mock_run.call_args.kwargs["settings"].dry_run is True


@pytest.mark.parametrize("error_status", ["failed", "llm_unavailable"])
def test_ideation_main_error_statuses(base_settings: Settings, error_status: str) -> None:
    with (
        patch("sys.argv", ["ideation_flow"]),
        patch("agent.orchestration.ideation_flow.load_settings", return_value=base_settings),
        patch(
            "agent.orchestration.ideation_flow.run_ideation_flow",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        mock_run.return_value = {"status": error_status}
        with pytest.raises(SystemExit) as exc:
            ideation_main()
        assert exc.value.code == 1


def test_ideation_main_exception(
    base_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    with (
        patch("sys.argv", ["ideation_flow"]),
        patch("agent.orchestration.ideation_flow.load_settings", return_value=base_settings),
        patch(
            "agent.orchestration.ideation_flow.run_ideation_flow",
            new_callable=AsyncMock,
        ) as mock_run,
    ):
        mock_run.side_effect = RuntimeError("Fatal LLM crash")
        with pytest.raises(SystemExit) as exc:
            ideation_main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Fatal Ideation error: Fatal LLM crash" in captured.err


def test_ideation_flow_dunder_main(base_settings: Settings) -> None:
    def fake_asyncio_run(coro: Any) -> Any:
        coro.close()
        return {"status": "completed"}

    with (
        patch("sys.argv", ["ideation_flow"]),
        patch("agent.config.load_settings", return_value=base_settings),
        patch("asyncio.run", side_effect=fake_asyncio_run),
    ):
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("agent.orchestration.ideation_flow", run_name="__main__")
        assert exc.value.code == 0
