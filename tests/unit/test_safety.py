"""Unit tests for safety policies, circuit breaker, and rate limiters."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.models.schemas import DailyCounters, PendingAction
from agent.safety.circuit_breaker import is_halted, trip_breaker
from agent.safety.rate_limiter import DailyCapEnforcer


@pytest.fixture
def base_settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test-key-12345"),
        nim_model_primary="nvidia/nemotron-3-super-120b-a12b",
        nim_model_fallback="meta/llama-3.3-70b-instruct",
        telegram_bot_token=SecretStr("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
        telegram_authorized_chat_id=123456789,
        linkedin_storage_state_path=tmp_path / "storage_state.json",
        user_focus_areas=["AI", "Python"],
        max_comments_per_day=5,
        max_posts_per_day=1,
        max_suggestions_per_run=3,
        pending_action_ttl_hours=20,
        dry_run=False,
        agent_paused=False,
    )


def test_is_halted_when_paused(tmp_path: Path, base_settings: Settings) -> None:
    paused_settings = base_settings.model_copy(update={"agent_paused": True})
    halted, reason = is_halted(tmp_path, paused_settings)
    assert halted is True
    assert reason is not None
    assert "paused" in reason.lower()


def test_is_halted_when_clean(tmp_path: Path, base_settings: Settings) -> None:
    halted, reason = is_halted(tmp_path, base_settings)
    assert halted is False
    assert reason is None


def test_trip_breaker_creates_incident_file_and_halts(
    tmp_path: Path, base_settings: Settings
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    trip_breaker(
        tmp_path,
        reason="Checkpoint verification detected",
        context={"url": "https://www.linkedin.com/checkpoint/challenge"},
    )

    incident_file = state_dir / "incident.json"
    assert incident_file.exists()

    data = json.loads(incident_file.read_text(encoding="utf-8"))
    assert data["reason"] == "Checkpoint verification detected"
    assert data["context"]["url"] == "https://www.linkedin.com/checkpoint/challenge"
    assert "created_at" in data
    assert "tripped_at" in data

    halted, reason = is_halted(tmp_path, base_settings)
    assert halted is True
    assert reason is not None
    assert "Checkpoint verification detected" in reason


def test_trip_breaker_idempotency_preserves_earliest_created_at(tmp_path: Path) -> None:
    initial_created_at = "2026-08-30T10:00:00+00:00"
    incident_file = tmp_path / "state" / "incident.json"
    incident_file.parent.mkdir(parents=True, exist_ok=True)
    incident_file.write_text(
        json.dumps(
            {
                "created_at": initial_created_at,
                "tripped_at": initial_created_at,
                "reason": "First incident",
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    trip_breaker(tmp_path, reason="Second incident", context={"extra": 1})

    data = json.loads(incident_file.read_text(encoding="utf-8"))
    assert data["created_at"] == initial_created_at
    assert data["reason"] == "Second incident"
    assert data["context"]["extra"] == 1


def test_daily_cap_enforcer_comments(base_settings: Settings) -> None:
    enforcer = DailyCapEnforcer(base_settings)

    counters_ok = DailyCounters(
        date="2026-08-30", comments_executed=4, posts_executed=0, suggestions_sent=2
    )
    can_exec, reason = enforcer.can_execute_comment(counters_ok)
    assert can_exec is True
    assert reason is None

    counters_capped = DailyCounters(
        date="2026-08-30", comments_executed=5, posts_executed=0, suggestions_sent=2
    )
    can_exec, reason = enforcer.can_execute_comment(counters_capped)
    assert can_exec is False
    assert reason is not None
    assert "comment cap reached" in reason.lower()


def test_daily_cap_enforcer_posts(base_settings: Settings) -> None:
    enforcer = DailyCapEnforcer(base_settings)

    counters_ok = DailyCounters(
        date="2026-08-30", comments_executed=2, posts_executed=0, suggestions_sent=2
    )
    can_exec, reason = enforcer.can_execute_post(counters_ok)
    assert can_exec is True
    assert reason is None

    counters_capped = DailyCounters(
        date="2026-08-30", comments_executed=2, posts_executed=1, suggestions_sent=2
    )
    can_exec, reason = enforcer.can_execute_post(counters_capped)
    assert can_exec is False
    assert reason is not None
    assert "post cap reached" in reason.lower()


def test_daily_cap_enforcer_suggestions(base_settings: Settings) -> None:
    enforcer = DailyCapEnforcer(base_settings)
    assert enforcer.can_send_suggestion(0) is True
    assert enforcer.can_send_suggestion(2) is True
    assert enforcer.can_send_suggestion(3) is False
    assert enforcer.can_send_suggestion(5) is False


def test_daily_cap_enforcer_ttl(base_settings: Settings) -> None:
    enforcer = DailyCapEnforcer(base_settings)
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    # Within 20h TTL (created 5 hours ago)
    valid_pending = PendingAction(
        item_id="a1b2c3d4",
        action_type="approve_comment",
        created_at=now - timedelta(hours=5),
        post_urn="urn:li:activity:100",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:100/",
        author_name="Alice",
        post_excerpt="Post excerpt",
        draft_text="Great comment",
        confidence=0.9,
        reasoning="Good fit",
        telegram_chat_id=123456789,
        telegram_message_id=1,
    )
    assert enforcer.is_within_ttl(valid_pending, now=now) is True

    # Expired (created 21 hours ago)
    expired_pending = valid_pending.model_copy(update={"created_at": now - timedelta(hours=21)})
    assert enforcer.is_within_ttl(expired_pending, now=now) is False

    # Custom TTL override (10 hours)
    assert enforcer.is_within_ttl(valid_pending, max_ttl_hours=4, now=now) is False
