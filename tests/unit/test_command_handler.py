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
from agent.models.schemas import DailyCounters, HistoryEntry, PendingAction
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
