"""Unit tests for the comment thread monitoring subsystem."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models import (
    ActiveThreadRecord,
    CommentDraft,
    EngagementStyle,
    PendingAction,
    ReplyTriageResult,
    ThreadReplyItem,
)
from agent.orchestration.thread_monitor import find_thread_replies


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("test-key"),
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Systems"],
    )


@pytest.mark.asyncio
async def test_find_thread_replies_no_threads(mock_settings: Settings) -> None:
    executor = MagicMock()
    llm = MagicMock()
    state_store = MagicMock()
    state_store.list_active_threads.return_value = []

    results = await find_thread_replies(executor, llm, state_store, mock_settings)
    assert results == []
    executor.inspect_comment_replies.assert_not_called()


@pytest.mark.asyncio
async def test_find_thread_replies_inactive_threads_skipped(mock_settings: Settings) -> None:
    executor = MagicMock()
    llm = MagicMock()
    state_store = MagicMock()
    inactive_thread = ActiveThreadRecord(
        id="th-1",
        post_url="https://linkedin.com/post/1",
        post_urn="urn:li:post:1",
        our_comment_urn="urn:li:comment:1",
        our_comment_text="Our comment",
        post_author="Author",
        status="resolved",
    )
    state_store.list_active_threads.return_value = [inactive_thread]

    results = await find_thread_replies(executor, llm, state_store, mock_settings)
    assert results == []
    executor.inspect_comment_replies.assert_not_called()


@pytest.mark.asyncio
async def test_find_thread_replies_inspection_error_handled_gracefully(
    mock_settings: Settings,
) -> None:
    executor = MagicMock()
    executor.inspect_comment_replies = AsyncMock(side_effect=RuntimeError("DOM timeout"))
    llm = MagicMock()
    state_store = MagicMock()
    active_thread = ActiveThreadRecord(
        id="th-2",
        post_url="https://linkedin.com/post/2",
        post_urn="urn:li:post:2",
        our_comment_urn="urn:li:comment:2",
        our_comment_text="Our comment",
        post_author="Author",
        status="active",
    )
    state_store.list_active_threads.return_value = [active_thread]

    results = await find_thread_replies(executor, llm, state_store, mock_settings)
    assert results == []
    executor.inspect_comment_replies.assert_called_once()


@pytest.mark.asyncio
async def test_find_thread_replies_duplicate_skipped(mock_settings: Settings) -> None:
    executor = MagicMock()
    reply = ThreadReplyItem(
        reply_urn="urn:li:reply:10",
        parent_comment_urn="urn:li:comment:2",
        author_name="Bob",
        reply_text="Interesting thought",
    )
    executor.inspect_comment_replies = AsyncMock(return_value=[reply])
    llm = MagicMock()
    state_store = MagicMock()
    active_thread = ActiveThreadRecord(
        id="th-2",
        post_url="https://linkedin.com/post/2",
        post_urn="urn:li:post:2",
        our_comment_urn="urn:li:comment:2",
        our_comment_text="Our comment",
        post_author="Author",
        status="active",
    )
    state_store.list_active_threads.return_value = [active_thread]
    # Simulate already existing pending action
    state_store.read_pending.return_value = MagicMock(spec=PendingAction)

    results = await find_thread_replies(executor, llm, state_store, mock_settings)
    assert results == []
    llm.triage_thread_reply.assert_not_called()


@pytest.mark.asyncio
async def test_find_thread_replies_triage_ignore(mock_settings: Settings) -> None:
    executor = MagicMock()
    reply = ThreadReplyItem(
        reply_urn="urn:li:reply:10",
        parent_comment_urn="urn:li:comment:2",
        author_name="Spammer",
        reply_text="Thanks for sharing!",
    )
    executor.inspect_comment_replies = AsyncMock(return_value=[reply])
    llm = MagicMock()
    llm.triage_thread_reply = AsyncMock(
        return_value=ReplyTriageResult(
            recommendation="ignore",
            reasoning="Generic compliment",
            confidence=0.9,
        )
    )
    state_store = MagicMock()
    active_thread = ActiveThreadRecord(
        id="th-2",
        post_url="https://linkedin.com/post/2",
        post_urn="urn:li:post:2",
        our_comment_urn="urn:li:comment:2",
        our_comment_text="Our comment",
        post_author="Author",
        status="active",
    )
    state_store.list_active_threads.return_value = [active_thread]
    state_store.read_pending.return_value = None

    results = await find_thread_replies(executor, llm, state_store, mock_settings)
    assert results == []
    llm.draft_thread_reply.assert_not_called()


@pytest.mark.asyncio
async def test_find_thread_replies_success_with_telegram(mock_settings: Settings) -> None:
    executor = MagicMock()
    reply = ThreadReplyItem(
        reply_urn="urn:li:reply:20",
        parent_comment_urn="urn:li:comment:2",
        author_name="Alice",
        author_headline="VP of Engineering",
        reply_text="How do you benchmark throughput under heavy contention?",
    )
    executor.inspect_comment_replies = AsyncMock(return_value=[reply])

    llm = MagicMock()
    triage_res = ReplyTriageResult(
        recommendation="reply",
        reasoning="Technical substantive question",
        confidence=0.95,
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )
    llm.triage_thread_reply = AsyncMock(return_value=triage_res)
    llm.draft_thread_reply = AsyncMock(
        return_value=CommentDraft(
            draft_comment="We benchmark with synthetic skewed zipfian distributions.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
    )

    state_store = MagicMock()
    active_thread = ActiveThreadRecord(
        id="th-3",
        post_url="https://linkedin.com/post/3",
        post_urn="urn:li:post:3",
        our_comment_urn="urn:li:comment:3",
        our_comment_text="Our distributed systems comment",
        post_author="Author",
        status="active",
    )
    state_store.list_active_threads.return_value = [active_thread]
    state_store.read_pending.return_value = None

    telegram = MagicMock()
    telegram.send_suggestion = AsyncMock(return_value=9988)

    results = await find_thread_replies(
        executor, llm, state_store, mock_settings, telegram=telegram
    )

    assert len(results) == 1
    action = results[0]
    assert action.action_type == "approve_reply"
    assert action.author_name == "Alice"
    assert action.draft_text == "We benchmark with synthetic skewed zipfian distributions."
    assert action.telegram_message_id == 9988
    assert state_store.write_pending.call_count >= 1
    telegram.send_suggestion.assert_called_once()


@pytest.mark.asyncio
async def test_run_thread_monitor_flow_halted(mock_settings: Settings, tmp_path: Path) -> None:
    from agent.orchestration.thread_monitor_flow import run_thread_monitor_flow

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
    from agent.orchestration.thread_monitor_flow import run_thread_monitor_flow

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


def test_cli_thread_monitor_parser() -> None:
    from agent.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["thread-monitor", "--headed", "--repo-root", "/tmp/repo"])
    assert args.command == "thread-monitor"
    assert args.headed is True
    assert args.repo_root == "/tmp/repo"


def test_cli_run_thread_monitor_exit_code() -> None:
    from agent.cli import build_parser, run_thread_monitor

    parser = build_parser()
    args = parser.parse_args(["thread-monitor"])
    with patch(
        "agent.orchestration.thread_monitor_flow.run_thread_monitor_flow", new_callable=AsyncMock
    ) as mock_flow:
        mock_flow.return_value = {
            "status": "completed",
            "queued_count": 2,
            "queued_actions": ["a1", "a2"],
        }
        code = run_thread_monitor(args)
        assert code == 0
