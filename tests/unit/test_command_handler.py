"""Unit tests for Telegram operator Command & Control router (CommandHandler)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models import (
    CommentDraft,
    DailyCounters,
    EngagementStyle,
    HistoryEntry,
    PendingAction,
    PostIdea,
)
from agent.orchestration.poll_flow import run_poll_flow
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.command_handler import CommandHandler


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Fixture providing validated application settings for tests."""
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test-key-12345"),
        nim_model_primary="nvidia/nemotron-3-super-120b-a12b",
        nim_model_fallback="openai/gpt-oss-20b",
        telegram_bot_token=SecretStr("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
        telegram_authorized_chat_id=987654321,
        linkedin_storage_state_path=tmp_path / "storage_state.json",
        user_focus_areas=["AI", "Python", "Autonomous Agents"],
        max_comments_per_day=5,
        max_posts_per_day=1,
        max_suggestions_per_run=3,
        pending_action_ttl_hours=12,
        dry_run=True,
        agent_paused=False,
        state_dir=tmp_path / "state",
    )


@pytest.fixture
def test_state_store(tmp_path: Path) -> GitStateStore:
    """Fixture providing an initialized GitStateStore with temp directory backing."""
    store = GitStateStore(tmp_path)
    store.state_dir.mkdir(parents=True, exist_ok=True)
    store.pending_dir.mkdir(parents=True, exist_ok=True)
    return store


@pytest.fixture
def sample_pending_action() -> PendingAction:
    """Fixture for sample pending action."""
    return PendingAction(
        item_id="pending_cmd_001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:7890123456",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:7890123456/",
        author_name="Alice Developer & Engineer <Tech Lead>",
        post_excerpt="Exciting developments in Agentic AI systems!",
        draft_text="Fascinating overview! How do you handle circuit breakers in production?",
        confidence=0.92,
        reasoning="Relevant high-quality engineering discussion",
        telegram_chat_id=987654321,
        telegram_message_id=5001,
    )


class TestCommandHandlerAuthorization:
    """Tests for strict operator identity enforcement."""

    @pytest.mark.asyncio
    async def test_unauthorized_sender_rejected(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        recorded_messages: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_messages.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 111}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            # Sender 111222 is not authorized (authorized is 987654321)
            result = await cmd_handler.handle_command(
                text="/status",
                chat_id=111222,
                sender_id=111222,
            )
            assert result is False
            assert len(recorded_messages) == 0

    @pytest.mark.asyncio
    async def test_missing_chat_id_rejected(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        cmd_handler = CommandHandler(
            settings=mock_settings,
            state_store=test_state_store,
            telegram=TelegramClient(mock_settings),
        )
        result = await cmd_handler.handle_command(
            text="/status",
            chat_id=None,
            sender_id=987654321,
        )
        assert result is False


class TestCommandHandlerStatus:
    """Tests for /status command report generation."""

    @pytest.mark.asyncio
    async def test_status_operational_clean_system(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        counters = DailyCounters(
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            comments_executed=2,
            posts_executed=0,
            suggestions_sent=3,
        )
        test_state_store.save_daily_counters(counters)

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8801}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_status(chat_id=987654321)

            assert "Agent Status Report" in report
            assert "Operational" in report
            assert "Circuit Breaker:</b> 🟢 <b>Normal</b>" in report
            assert "1</b> action(s) awaiting review" in report
            assert "Comments Executed:</b> 2 / 5" in report
            assert "Posts Executed:</b> 0 / 1" in report
            assert "Suggestions Sent:</b> 3" in report
            assert len(sent_payloads) == 1
            assert sent_payloads[0]["chat_id"] == 987654321
            assert sent_payloads[0]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_status_when_paused(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        paused_settings = mock_settings.model_copy(update={"agent_paused": True})
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8802}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(paused_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=paused_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_status(chat_id=987654321)
            assert "⏸️ <b>Paused</b>" in report

    @pytest.mark.asyncio
    async def test_status_when_circuit_breaker_tripped(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        incident_data = {
            "created_at": "2026-09-03T18:00:00+00:00",
            "tripped_at": "2026-09-03T18:00:00+00:00",
            "reason": "Bot challenge encountered: checkpoint CAPTCHA",
            "context": {"url": "https://www.linkedin.com/checkpoint/challenge"},
        }
        test_state_store.incident_path.write_text(json.dumps(incident_data), encoding="utf-8")

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8803}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_status(chat_id=987654321)
            assert "Halted (Circuit Breaker Tripped)" in report
            assert "🔴 <b>Tripped</b>" in report
            assert "Bot challenge encountered" in report


class TestCommandHandlerHome:
    """Tests for /home command central Command & Control hub."""

    @pytest.mark.asyncio
    async def test_home_command_renders_hub(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8801}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_home(chat_id=987654321)
            assert "Command & Control Hub" in report
            assert "Operational" in report
            assert len(sent_payloads) == 1
            assert sent_payloads[0]["chat_id"] == 987654321
            assert "inline_keyboard" in sent_payloads[0]["reply_markup"]


class TestCommandHandlerStats:
    """Tests for /stats command historical metric processing."""

    @pytest.mark.asyncio
    async def test_stats_with_historical_entries(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        now = datetime.now(UTC)
        test_state_store.append_history(
            HistoryEntry(
                item_id="h1",
                action_type="approve_comment",
                final_status="executed_success",
                decided_at=now,
                executed_at=now,
            )
        )
        test_state_store.append_history(
            HistoryEntry(
                item_id="h2",
                action_type="approve_comment",
                final_status="rejected",
                decided_at=now,
                executed_at=None,
            )
        )
        test_state_store.append_history(
            HistoryEntry(
                item_id="h3",
                action_type="approve_post",
                final_status="executed_success",
                decided_at=now,
                executed_at=now,
            )
        )
        test_state_store.append_history(
            HistoryEntry(
                item_id="h4",
                action_type="approve_comment",
                final_status="expired",
                decided_at=None,
                executed_at=now,
                error="TTL expired",
            )
        )
        test_state_store.append_history(
            HistoryEntry(
                item_id="h5",
                action_type="approve_comment",
                final_status="executed_failed",
                decided_at=now,
                executed_at=now,
                error="Network timeout",
            )
        )

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8804}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_stats(chat_id=987654321)
            assert "Total Actions Logged:</b> 5" in report
            assert "Approved:</b> 2" in report
            assert "Rejected:</b> 1" in report
            assert "Expired:</b> 1" in report
            assert "Comments Posted:</b> 1" in report
            assert "Posts Published:</b> 1" in report
            assert "Failures:</b> 1" in report

    @pytest.mark.asyncio
    async def test_stats_empty_history(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8805}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_stats(chat_id=987654321)
            assert "No historical actions recorded yet" in report


class TestCommandHandlerPending:
    """Tests for /pending command listing."""

    @pytest.mark.asyncio
    async def test_pending_empty(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8806}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_pending(chat_id=987654321)
            assert "No actions currently awaiting approval" in report

    @pytest.mark.asyncio
    async def test_pending_populated_with_html_escaping(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8807}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_pending(chat_id=987654321)
            assert "Pending Actions (1)" in report
            assert sample_pending_action.item_id in report
            assert "LinkedIn Post" in report
            assert "&lt;Tech Lead&gt;" in report  # HTML escaped
            assert "Fascinating overview!" in report


class TestCommandHandlerPauseResumeClear:
    """Tests for /pause, /resume, and /clear_incident safety controls."""

    @pytest.mark.asyncio
    async def test_pause_and_resume_cycle(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8808}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            # 1. Execute /pause
            pause_msg = await cmd_handler.handle_pause(chat_id=987654321)
            assert "Agent Paused" in pause_msg
            assert bool(mock_settings.agent_paused) is True
            assert test_state_store.is_paused() is True

            # 2. Execute /resume
            resume_msg = await cmd_handler.handle_resume(chat_id=987654321)
            assert "Agent Resumed" in resume_msg
            assert bool(mock_settings.agent_paused) is False
            assert test_state_store.is_paused() is False

    @pytest.mark.asyncio
    async def test_clear_incident_when_tripped(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        test_state_store.incident_path.write_text(
            '{"reason": "CAPTCHA challenge"}', encoding="utf-8"
        )
        assert test_state_store.incident_path.exists() is True

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8809}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = await cmd_handler.handle_clear_incident(chat_id=987654321)
            assert "Circuit Breaker Reset" in msg
            assert test_state_store.incident_path.exists() is False

    @pytest.mark.asyncio
    async def test_clear_incident_when_clean(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        assert test_state_store.incident_path.exists() is False

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8810}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = await cmd_handler.handle_clear_incident(chat_id=987654321)
            assert "Circuit Breaker Normal" in msg


class TestCommandHandlerRouting:
    """Tests for command routing, bot username stripping, and help messages."""

    @pytest.mark.asyncio
    async def test_help_and_start_commands(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8811}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = await cmd_handler.handle_help(chat_id=987654321)
            assert "Operator Command & Control" in msg
            assert "/status" in msg
            assert "/pause" in msg
            assert "/clear_incident" in msg

    @pytest.mark.asyncio
    async def test_command_with_bot_username_suffix(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8812}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            # Command formatted with @bot_username
            res = await cmd_handler.handle_command(
                text="/status@linkedin_hitl_bot",
                chat_id=987654321,
                sender_id=987654321,
            )
            assert res is True
            assert len(sent_payloads) == 1
            assert "Agent Status Report" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_unknown_command(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8813}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            res = await cmd_handler.handle_command(
                text="/invalid_command_xyz",
                chat_id=987654321,
                sender_id=987654321,
            )
            assert res is True
            assert "Unknown Command" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_handle_message_non_command(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        cmd_handler = CommandHandler(
            settings=mock_settings,
            state_store=test_state_store,
            telegram=TelegramClient(mock_settings),
        )
        msg = {
            "text": "Regular conversational text without leading slash",
            "chat": {"id": 987654321},
            "from": {"id": 987654321},
        }
        res = await cmd_handler.handle_message(msg)
        assert res is False

    @pytest.mark.asyncio
    async def test_handle_message_docked_buttons(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 111}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            # Test 1: Docked Status button
            msg_status = {
                "text": "📊 Status",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
            }
            res_status = await cmd_handler.handle_message(msg_status)
            assert res_status is True
            assert "Agent Status Report" in sent_payloads[0]["text"]
            assert sent_payloads[0]["reply_markup"]["is_persistent"] is True

            # Test 2: Docked Pause button
            msg_pause = {
                "text": "⏸️ Pause",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
            }
            res_pause = await cmd_handler.handle_message(msg_pause)
            assert res_pause is True
            assert test_state_store.is_paused() is True
            assert "Agent Paused" in sent_payloads[1]["text"]

            # Test 3: Docked Resume button
            msg_resume = {
                "text": "▶️ Resume",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
            }
            res_resume = await cmd_handler.handle_message(msg_resume)
            assert res_resume is True
            assert test_state_store.is_paused() is False
            assert "Agent Resumed" in sent_payloads[2]["text"]

            # Test 4: Docked Home button
            msg_home = {
                "text": "🏠 Home Menu",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
            }
            res_home = await cmd_handler.handle_message(msg_home)
            assert res_home is True
            assert "Command & Control Hub" in sent_payloads[3]["text"]


class TestCommandHandlerOnDemandPostAndScout:
    """Tests for on-demand mobile content creation: /post, /scout, and voice notes."""

    @pytest.mark.asyncio
    async def test_post_command_with_idea_and_llm(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9901}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            mock_llm = AsyncMock()
            mock_llm.draft_post_idea.return_value = PostIdea(
                should_post=True,
                headline="Pitfalls of Production Agent Loops",
                draft_post_text="Here are 3 subtle pitfalls when building production agentic loops...",
                reasoning="Strong technical perspective",
                hashtags=["#AI", "#Python"],
            )

            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
                llm_service=mock_llm,
            )

            msg = {
                "text": "/post 3 subtle pitfalls in agentic loops",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 501,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True
            mock_llm.draft_post_idea.assert_awaited_once()

            # Verify pending action persisted
            pending_list = test_state_store.list_pending()
            assert len(pending_list) == 1
            pending = pending_list[0]
            assert pending.action_type == "approve_post"
            assert "Here are 3 subtle pitfalls" in pending.draft_text
            assert pending.telegram_message_id == 9901

            # Verify Telegram suggestion card delivered
            assert len(sent_payloads) == 1
            assert "📝 Original Post" in sent_payloads[0]["text"]
            assert "Here are 3 subtle pitfalls" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_post_command_without_llm_service(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9902}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
                llm_service=None,
            )

            msg = {
                "text": "/post Quick raw insight on LLM caching.",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 502,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True

            pending_list = test_state_store.list_pending()
            assert len(pending_list) == 1
            assert pending_list[0].action_type == "approve_post"
            assert pending_list[0].draft_text == "Quick raw insight on LLM caching."

    @pytest.mark.asyncio
    async def test_post_command_empty_prompt_shows_guidance(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9903}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "text": "/post",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 503,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True
            assert len(sent_payloads) == 1
            assert "Draft an Original Post" in sent_payloads[0]["text"]
            assert "/post 3 subtle pitfalls" in sent_payloads[0]["text"]
            assert len(test_state_store.list_pending()) == 0

    @pytest.mark.asyncio
    async def test_scout_command_with_url(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9904}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "text": "/scout https://www.linkedin.com/feed/update/urn:li:activity:123456789/",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 504,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True
            assert len(sent_payloads) == 1
            assert "Target Received" in sent_payloads[0]["text"]
            assert "urn:li:activity:123456789" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_scout_command_empty_url_shows_guidance(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9905}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "text": "/scout",
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 505,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True
            assert len(sent_payloads) == 1
            assert "On-Demand Target Scouting" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_voice_note_received_acknowledgment(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9906}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "voice": {"file_id": "voice_file_abc123", "duration": 12},
                "chat": {"id": 987654321},
                "from": {"id": 987654321},
                "message_id": 506,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is True
            assert len(sent_payloads) == 1
            assert "Voice Note Received" in sent_payloads[0]["text"]
            assert "/post" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_voice_note_unauthorized_dropped(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9907}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "voice": {"file_id": "voice_file_abc123"},
                "chat": {"id": 111222333},
                "from": {"id": 111222333},
                "message_id": 507,
            }
            res = await cmd_handler.handle_message(msg)
            assert res is False
            assert len(sent_payloads) == 0


class TestPollFlowCommandIntegration:
    """Tests verifying poll_flow integration with operator commands."""

    @pytest.mark.asyncio
    async def test_poll_flow_dispatches_status_command(
        self,
        mock_settings: Settings,
        tmp_path: Path,
    ) -> None:
        store = GitStateStore(tmp_path)
        store.state_dir.mkdir(parents=True, exist_ok=True)

        sample_updates = {
            "ok": True,
            "result": [
                {
                    "update_id": 101,
                    "message": {
                        "message_id": 4001,
                        "text": "/status",
                        "from": {"id": mock_settings.telegram_authorized_chat_id},
                        "chat": {"id": mock_settings.telegram_authorized_chat_id},
                    },
                }
            ],
        }

        sent_payloads: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9901}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as tg_http_client:
            tg = TelegramClient(mock_settings, http_client=tg_http_client)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.raise_for_status = lambda: None
                mock_resp.json = lambda: sample_updates
                mock_get.return_value = mock_resp

                results = await run_poll_flow(
                    settings=mock_settings,
                    repo_root=tmp_path,
                    telegram_client=tg,
                )

                assert len(results) == 1
                assert results[0]["status"] == "command_handled"
                assert results[0]["command"] == "status"
                assert len(sent_payloads) == 1
                assert "Agent Status Report" in sent_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_poll_flow_dispatches_draft_edit_reply(
        self,
        mock_settings: Settings,
        tmp_path: Path,
        sample_pending_action: PendingAction,
    ) -> None:
        store = GitStateStore(tmp_path)
        store.state_dir.mkdir(parents=True, exist_ok=True)
        store.pending_dir.mkdir(parents=True, exist_ok=True)
        action = sample_pending_action.model_copy(update={"telegram_message_id": 5001})
        store.write_pending(action)

        sample_updates = {
            "ok": True,
            "result": [
                {
                    "update_id": 102,
                    "message": {
                        "message_id": 6001,
                        "text": "Revised comment draft via poll flow",
                        "from": {"id": mock_settings.telegram_authorized_chat_id},
                        "chat": {"id": mock_settings.telegram_authorized_chat_id},
                        "reply_to_message": {
                            "message_id": 5001,
                            "text": f"ID: {action.item_id}\nDraft: original",
                        },
                    },
                }
            ],
        }

        sent_payloads: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9902}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as tg_http_client:
            tg = TelegramClient(mock_settings, http_client=tg_http_client)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.raise_for_status = lambda: None
                mock_resp.json = lambda: sample_updates
                mock_get.return_value = mock_resp

                results = await run_poll_flow(
                    settings=mock_settings,
                    repo_root=tmp_path,
                    telegram_client=tg,
                )

                assert len(results) == 1
                assert results[0]["status"] == "draft_edited"
                updated_item = store.read_pending(action.item_id)
                assert updated_item is not None
                assert updated_item.draft_text == "Revised comment draft via poll flow"

    @pytest.mark.asyncio
    async def test_poll_flow_dispatches_inline_edit_callback(
        self,
        mock_settings: Settings,
        tmp_path: Path,
        sample_pending_action: PendingAction,
    ) -> None:
        store = GitStateStore(tmp_path)
        store.state_dir.mkdir(parents=True, exist_ok=True)
        store.pending_dir.mkdir(parents=True, exist_ok=True)
        store.write_pending(sample_pending_action)

        sample_updates = {
            "ok": True,
            "result": [
                {
                    "update_id": 103,
                    "callback_query": {
                        "id": "cb_edit_1",
                        "from": {"id": mock_settings.telegram_authorized_chat_id},
                        "message": {"message_id": 5001},
                        "data": f"ed:{sample_pending_action.item_id}",
                    },
                }
            ],
        }

        answered_queries: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            answered_queries.append(data)
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as tg_http_client:
            tg = TelegramClient(mock_settings, http_client=tg_http_client)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.raise_for_status = lambda: None
                mock_resp.json = lambda: sample_updates
                mock_get.return_value = mock_resp

                results = await run_poll_flow(
                    settings=mock_settings,
                    repo_root=tmp_path,
                    telegram_client=tg,
                )

                assert len(results) == 1
                assert results[0]["status"] == "edit_prompted"
                assert results[0]["item_id"] == sample_pending_action.item_id
                assert len(answered_queries) == 1
                assert answered_queries[0]["callback_query_id"] == "cb_edit_1"

    @pytest.mark.asyncio
    async def test_poll_flow_unauthorized_message_skipped(
        self,
        mock_settings: Settings,
        tmp_path: Path,
    ) -> None:
        sample_updates = {
            "ok": True,
            "result": [
                {
                    "update_id": 104,
                    "message": {
                        "message_id": 4002,
                        "text": "/status",
                        "from": {"id": 99999999},  # Unauthorized
                        "chat": {"id": 99999999},
                    },
                }
            ],
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = lambda: None
            mock_resp.json = lambda: sample_updates
            mock_get.return_value = mock_resp

            results = await run_poll_flow(
                settings=mock_settings,
                repo_root=tmp_path,
            )
            assert results == []


class TestCommandHandlerCorruptedFilesResilience:
    """Tests resilience against corrupted history and incident files."""

    @pytest.mark.asyncio
    async def test_stats_corrupted_history_lines_skipped(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        now = datetime.now(UTC)
        valid_entry = HistoryEntry(
            item_id="valid_h1",
            action_type="approve_comment",
            final_status="executed_success",
            decided_at=now,
            executed_at=now,
        )
        test_state_store.append_history(valid_entry)

        # Append corrupted lines
        with test_state_store.history_path.open("a", encoding="utf-8") as f:
            f.write("corrupted non-json line\n")
            f.write("{broken json line\n")

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8815}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_stats(chat_id=987654321)
            assert "Total Actions Logged:</b> 1" in report
            assert "Approved:</b> 1" in report

    @pytest.mark.asyncio
    async def test_status_corrupted_incident_file_handled(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        test_state_store.incident_path.write_text("invalid json content", encoding="utf-8")

        sent_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_payloads.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8816}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            report = await cmd_handler.handle_status(chat_id=987654321)
            assert "Halted (Circuit Breaker Tripped)" in report
            assert "Corrupted incident.json file" in report


class TestCommandHandlerReplyEditing:
    """Test suite for inline draft editing via Telegram reply."""

    @pytest.mark.asyncio
    async def test_reply_edit_success(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 5001})
        test_state_store.write_pending(action)

        recorded_requests: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": str(request.url.path), "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7001}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6001,
                "text": "This is a brilliantly revised comment draft.",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "chat": {"id": mock_settings.telegram_authorized_chat_id},
                "reply_to_message": {
                    "message_id": 5001,
                    "text": f"ID: {action.item_id}\nDraft: original",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is True

            # Verify state updated
            updated_pending = test_state_store.read_pending(action.item_id)
            assert updated_pending is not None
            assert updated_pending.draft_text == "This is a brilliantly revised comment draft."

            # Verify editMessageText sent to update card
            edit_reqs = [r for r in recorded_requests if r["path"].endswith("/editMessageText")]
            assert len(edit_reqs) == 1
            assert edit_reqs[0]["payload"]["message_id"] == 5001
            assert "This is a brilliantly revised comment draft." in edit_reqs[0]["payload"]["text"]
            assert edit_reqs[0]["payload"]["reply_markup"] is not None

            # Verify confirmation reply sent
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert send_reqs[0]["payload"]["reply_to_message_id"] == 6001
            assert "✏️ Draft updated successfully!" in send_reqs[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_reply_edit_fallback_item_id_regex(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": None})
        test_state_store.write_pending(action)

        recorded_requests: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": str(request.url.path), "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7002}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6002,
                "text": "Regex fallback revised draft text.",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "chat": {"id": mock_settings.telegram_authorized_chat_id},
                "reply_to_message": {
                    "message_id": 99999,
                    "text": f"🚀 Suggestion\nID: {action.item_id}\nSome text...",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is True
            updated_pending = test_state_store.read_pending(action.item_id)
            assert updated_pending is not None
            assert updated_pending.draft_text == "Regex fallback revised draft text."

    @pytest.mark.asyncio
    async def test_reply_edit_unauthorized_sender(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 5001})
        test_state_store.write_pending(action)

        recorded_requests: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": str(request.url.path), "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7003}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6003,
                "text": "Unauthorized hack attempt",
                "from": {"id": 111222333},
                "chat": {"id": 111222333},
                "reply_to_message": {
                    "message_id": 5001,
                    "text": f"ID: {action.item_id}",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is False
            assert len(recorded_requests) == 0

            item = test_state_store.read_pending(action.item_id)
            assert item is not None
            assert item.draft_text == sample_pending_action.draft_text

    @pytest.mark.asyncio
    async def test_reply_edit_empty_text(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 5001})
        test_state_store.write_pending(action)

        sent_messages: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_messages.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7004}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6004,
                "text": "   ",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "chat": {"id": mock_settings.telegram_authorized_chat_id},
                "reply_to_message": {
                    "message_id": 5001,
                    "text": f"ID: {action.item_id}",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is False
            assert len(sent_messages) == 1
            assert "Draft text cannot be empty" in sent_messages[0]["text"]

    @pytest.mark.asyncio
    async def test_reply_edit_exceeds_max_length(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 5001})
        test_state_store.write_pending(action)

        sent_messages: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_messages.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7005}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6005,
                "text": "A" * 650,
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "chat": {"id": mock_settings.telegram_authorized_chat_id},
                "reply_to_message": {
                    "message_id": 5001,
                    "text": f"ID: {action.item_id}",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is False
            assert len(sent_messages) == 1
            assert "exceeds maximum length of 600" in sent_messages[0]["text"]

    @pytest.mark.asyncio
    async def test_reply_edit_not_found(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        sent_messages: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_messages.append(data)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7006}})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            msg = {
                "message_id": 6006,
                "text": "Trying to edit something that doesn't exist",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "chat": {"id": mock_settings.telegram_authorized_chat_id},
                "reply_to_message": {
                    "message_id": 8888,
                    "text": "Old message without valid ID",
                },
            }

            res = await cmd_handler.handle_message(msg)
            assert res is False
            assert len(sent_messages) == 1
            assert "no longer pending" in sent_messages[0]["text"]


class TestCommandHandlerCallbackQueries:
    """Test suite for edit and regenerate callback query processing in CommandHandler."""

    @pytest.mark.asyncio
    async def test_callback_edit_prompt(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        answered: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            answered.append(data)
            if "sendMessage" in str(request.url.path):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 9001}})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            cb = {
                "id": "cb_edit_test",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "data": f"edit:{sample_pending_action.item_id}",
                "message": {
                    "message_id": 5001,
                    "chat": {"id": mock_settings.telegram_authorized_chat_id},
                },
            }

            res = await cmd_handler.handle_callback_query(cb)
            assert res is True
            cb_answers = [a for a in answered if "callback_query_id" in a]
            assert len(cb_answers) == 1
            assert cb_answers[0]["callback_query_id"] == "cb_edit_test"
            assert "Reply to this suggestion with your revised draft text" in cb_answers[0]["text"]

            edit_markups = [a for a in answered if "reply_markup" in a and "inline_keyboard" in a["reply_markup"]]
            assert len(edit_markups) == 1
            assert edit_markups[0]["reply_markup"]["inline_keyboard"][0][0]["text"] == "❌ Cancel Edit"

            force_replies = [a for a in answered if "reply_markup" in a and a["reply_markup"].get("force_reply")]
            assert len(force_replies) == 1
            assert force_replies[0]["reply_markup"]["input_field_placeholder"] == "Enter revised draft text..."

    @pytest.mark.asyncio
    async def test_callback_reg_tone_guidance(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded.append({"path": str(request.url.path), "payload": data})
            if "sendMessage" in str(request.url.path):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 9001}})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
                llm_service=None,
            )

            cb = {
                "id": "cb_reg_test",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "data": f"reg:{sample_pending_action.item_id}",
                "message": {
                    "message_id": 5001,
                    "chat": {"id": mock_settings.telegram_authorized_chat_id},
                },
            }

            res = await cmd_handler.handle_callback_query(cb)
            assert res is True

            ans = [r for r in recorded if r["path"].endswith("/answerCallbackQuery")]
            assert len(ans) == 1
            assert ans[0]["payload"]["callback_query_id"] == "cb_reg_test"
            assert "tone style" in ans[0]["payload"]["text"].lower()

            edits = [r for r in recorded if r["path"].endswith("/editMessageReplyMarkup")]
            assert len(edits) == 1
            kb = edits[0]["payload"]["reply_markup"]["inline_keyboard"]
            assert kb[0][0]["callback_data"] == f"tone:technical:{sample_pending_action.item_id}"
            assert kb[2][0]["callback_data"] == f"back:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_callback_reg_with_llm_service(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(
            update={
                "telegram_message_id": 5001,
                "engagement_style": EngagementStyle.TECHNICAL_DEEP_DIVE,
            }
        )
        test_state_store.write_pending(action)
        recorded: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded.append({"path": str(request.url.path), "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        mock_llm = AsyncMock()
        mock_llm.draft_comment = AsyncMock(
            return_value=CommentDraft(
                draft_comment="Here is an alternative contrarian angle on concurrency.",
                topic_tags=["concurrency"],
            )
        )

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
                llm_service=mock_llm,
            )

            cb = {
                "id": "cb_reg_llm",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "data": f"tone:contrarian:{action.item_id}",
                "message": {
                    "message_id": 5001,
                    "chat": {"id": mock_settings.telegram_authorized_chat_id},
                },
            }

            res = await cmd_handler.handle_callback_query(cb)
            assert res is True

            updated_item = test_state_store.read_pending(action.item_id)
            assert updated_item is not None
            assert (
                updated_item.draft_text == "Here is an alternative contrarian angle on concurrency."
            )

            edits = [r for r in recorded if r["path"].endswith("/editMessageText")]
            assert len(edits) == 1
            assert "Here is an alternative contrarian angle" in edits[0]["payload"]["text"]

            ans = [r for r in recorded if r["path"].endswith("/answerCallbackQuery")]
            assert len(ans) == 1
            assert "Regenerating (contrarian)" in ans[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_callback_unauthorized_sender(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded.append(data)
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            cb = {
                "id": "cb_unauth",
                "from": {"id": 111222333},
                "data": f"reg:{sample_pending_action.item_id}",
                "message": {"message_id": 5001},
            }

            res = await cmd_handler.handle_callback_query(cb)
            assert res is False
            assert len(recorded) == 0

    @pytest.mark.asyncio
    async def test_callback_item_not_found(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        answered: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            answered.append(data)
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tg = TelegramClient(mock_settings, http_client=client)
            cmd_handler = CommandHandler(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=tg,
            )

            cb = {
                "id": "cb_missing",
                "from": {"id": mock_settings.telegram_authorized_chat_id},
                "data": "edit:missing_item_999",
                "message": {"message_id": 5001},
            }

            res = await cmd_handler.handle_callback_query(cb)
            assert res is False
            assert len(answered) == 1
            assert "no longer pending" in answered[0]["text"]
            assert answered[0]["show_alert"] is True


class TestPollFlowRegenerateCallback:
    """Test poll flow integration with reg:<item_id> callbacks."""

    @pytest.mark.asyncio
    async def test_poll_flow_dispatches_regenerate_callback(
        self,
        mock_settings: Settings,
        tmp_path: Path,
        sample_pending_action: PendingAction,
    ) -> None:
        store = GitStateStore(tmp_path)
        store.state_dir.mkdir(parents=True, exist_ok=True)
        store.pending_dir.mkdir(parents=True, exist_ok=True)
        store.write_pending(sample_pending_action)

        sample_updates = {
            "ok": True,
            "result": [
                {
                    "update_id": 104,
                    "callback_query": {
                        "id": "cb_reg_1",
                        "from": {"id": mock_settings.telegram_authorized_chat_id},
                        "message": {
                            "message_id": 5001,
                            "chat": {"id": mock_settings.telegram_authorized_chat_id},
                        },
                        "data": f"reg:{sample_pending_action.item_id}",
                    },
                }
            ],
        }

        answered_queries: list[dict[str, Any]] = []

        def tg_handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            answered_queries.append(data)
            if "sendMessage" in str(request.url.path):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 9002}})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(tg_handler)
        async with httpx.AsyncClient(transport=transport) as tg_http_client:
            tg = TelegramClient(mock_settings, http_client=tg_http_client)

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.raise_for_status = lambda: None
                mock_resp.json = lambda: sample_updates
                mock_get.return_value = mock_resp

                results = await run_poll_flow(
                    settings=mock_settings,
                    repo_root=tmp_path,
                    telegram_client=tg,
                )

                assert len(results) == 1
                assert results[0]["status"] == "regenerate_prompted"
                assert results[0]["item_id"] == sample_pending_action.item_id
                ans = [q for q in answered_queries if "callback_query_id" in q]
                assert len(ans) == 1
                assert ans[0]["callback_query_id"] == "cb_reg_1"
