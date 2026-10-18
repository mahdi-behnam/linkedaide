"""Unit tests for the comment thread monitoring flow and CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models import ActiveThreadRecord, PendingAction
from agent.orchestration.thread_monitor_flow import main as thread_monitor_main
from agent.orchestration.thread_monitor_flow import run_thread_monitor_flow


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("test-key"),
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Systems"],
    )


@pytest.mark.asyncio
async def test_run_thread_monitor_flow_halted(mock_settings: Settings, tmp_path: Path) -> None:
    with patch(
        "agent.orchestration.thread_monitor_flow.is_halted",
        return_value=(True, "Kill switch active"),
    ):
        result = await run_thread_monitor_flow(settings=mock_settings, repo_root=tmp_path)
        assert result["status"] == "halted"
        assert result["queued_count"] == 0


@pytest.mark.asyncio
async def test_run_thread_monitor_flow_no_active_threads(
    mock_settings: Settings, tmp_path: Path
) -> None:
    with (
        patch("agent.orchestration.thread_monitor_flow.is_halted", return_value=(False, None)),
        patch("agent.orchestration.thread_monitor_flow.get_state_store") as mock_get_store,
    ):
        mock_store = MagicMock()
        mock_store.list_active_threads.return_value = []
        mock_get_store.return_value = mock_store

        result = await run_thread_monitor_flow(settings=mock_settings, repo_root=tmp_path)
        assert result["status"] == "no_active_threads"
        assert result["queued_count"] == 0
        assert result["queued_actions"] == []


@pytest.mark.asyncio
async def test_run_thread_monitor_flow_success_execution(
    mock_settings: Settings, tmp_path: Path
) -> None:
    active_thread = ActiveThreadRecord(
        id="th-active-1",
        post_url="https://linkedin.com/post/1",
        post_urn="urn:li:post:1",
        our_comment_urn="urn:li:comment:1",
        our_comment_text="Original test comment",
        post_author="Test Author",
        status="active",
    )

    mock_store = MagicMock()
    mock_store.list_active_threads.return_value = [active_thread]

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.__aenter__.return_value = mock_playwright
    mock_playwright_cm.__aexit__.return_value = None

    mock_pending = MagicMock(spec=PendingAction)
    mock_pending.item_id = "pending_reply_001"

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "status": "completed",
            "pending_items": [mock_pending],
        }
    )

    with (
        patch("agent.orchestration.thread_monitor_flow.is_halted", return_value=(False, None)),
        patch("agent.orchestration.thread_monitor_flow.get_state_store", return_value=mock_store),
        patch(
            "agent.orchestration.thread_monitor_flow.ensure_session_file",
            return_value=tmp_path / "session.json",
        ),
        patch(
            "agent.orchestration.thread_monitor_flow.async_playwright",
            return_value=mock_playwright_cm,
        ),
        patch(
            "agent.orchestration.thread_monitor_flow.new_stealth_context",
            AsyncMock(return_value=mock_context),
        ),
        patch("agent.orchestration.thread_monitor_flow.wait_for_login_redirect", AsyncMock()),
        patch(
            "agent.orchestration.thread_monitor_flow.build_thread_monitor_graph",
            return_value=mock_graph,
        ),
    ):
        result = await run_thread_monitor_flow(
            settings=mock_settings, repo_root=tmp_path, headless=True
        )
        assert result["status"] == "completed"
        assert result["queued_count"] == 1
        assert result["queued_actions"] == ["pending_reply_001"]


def test_thread_monitor_flow_main_success(mock_settings: Settings) -> None:
    with (
        patch("agent.orchestration.thread_monitor_flow.load_settings", return_value=mock_settings),
        patch("sys.argv", ["thread_monitor_flow"]),
        patch(
            "agent.orchestration.thread_monitor_flow.run_thread_monitor_flow",
            new_callable=AsyncMock,
            return_value={"status": "completed", "queued_count": 0},
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        thread_monitor_main()
    assert exc_info.value.code == 0


def test_thread_monitor_flow_main_halted(mock_settings: Settings) -> None:
    with (
        patch("agent.orchestration.thread_monitor_flow.load_settings", return_value=mock_settings),
        patch("sys.argv", ["thread_monitor_flow"]),
        patch(
            "agent.orchestration.thread_monitor_flow.run_thread_monitor_flow",
            new_callable=AsyncMock,
            return_value={"status": "halted"},
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        thread_monitor_main()
    assert exc_info.value.code == 1


def test_cli_thread_monitor_parser() -> None:
    from agent.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["thread-monitor", "--headed", "--repo-root", "/tmp/repo"])
    assert args.command == "thread-monitor"
    assert args.headed is True
    assert args.repo_root == "/tmp/repo"


def test_cli_run_thread_monitor_exit_code(mock_settings: Settings) -> None:
    from agent.cli import build_parser, run_thread_monitor

    parser = build_parser()
    args = parser.parse_args(["thread-monitor"])
    with (
        patch("agent.cli.load_settings", return_value=mock_settings),
        patch(
            "agent.orchestration.thread_monitor_flow.run_thread_monitor_flow",
            new_callable=AsyncMock,
        ) as mock_flow,
    ):
        mock_flow.return_value = {
            "status": "completed",
            "queued_count": 2,
            "queued_actions": ["a1", "a2"],
        }
        code = run_thread_monitor(args)
        assert code == 0
