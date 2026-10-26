"""Operational alerting and health telemetry for LLM resilience.

Monitors LLM execution health, updates durable state store with health records,
broadcasts realtime warnings to the Desktop Cockpit via Cloudflare Worker WebSockets,
and delivers debounced notifications to the authorized Telegram chat without spamming.

Architecture Invariants:
- Never hardcode model identifiers in messages, errors, or notifications.
- Debounce standalone Telegram notifications (default 12-hour cooldown).
- Fails open: failure in alerting must never disrupt core graph outcomes.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import UTC, datetime
from typing import Any

from agent.config import Settings
from agent.llm.service import LLMService
from agent.orchestration.worker_notifier import notify_worker_event
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient

logger = logging.getLogger(__name__)

ALERT_TIMESTAMP_KEY = "alert:primary_model_degraded_ts"
HEALTH_RECORD_KEY = "llm_health"


def is_alert_debounced(
    last_alert_iso: str | None,
    cooldown_hours: float = 12.0,
    current_time: datetime | None = None,
) -> bool:
    """Determine whether an alert should be suppressed due to the debounce cooldown window."""
    if not last_alert_iso:
        return False
    try:
        last_dt = datetime.fromisoformat(last_alert_iso)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        now = current_time or datetime.now(UTC)
        elapsed_seconds = (now - last_dt).total_seconds()
        return elapsed_seconds < (cooldown_hours * 3600.0)
    except Exception as err:
        logger.debug("Failed to parse last alert timestamp '%s': %s", last_alert_iso, err)
        return False


async def check_and_notify_llm_health(
    settings: Settings,
    llm: LLMService,
    state_store: BaseStateStore,
    telegram: TelegramClient | None = None,
    debounce_hours: float = 12.0,
) -> dict[str, Any]:
    """Inspect LLM runner health and broadcast multi-channel alerts if degraded.

    Args:
        settings: Runtime application settings.
        llm: LLM service instance containing resilience telemetry.
        state_store: Durable repository state store for persistence and debouncing.
        telegram: Optional Telegram client for operator alerts.
        debounce_hours: Minimum hours between standalone Telegram alert messages.

    Returns:
        The health report dictionary.
    """
    report = llm.get_health_report()
    is_degraded = report.get("status") == "degraded"
    primary_model = report.get("primary_model") or settings.effective_primary_model
    fallback_model = report.get("fallback_model") or settings.effective_fallback_model
    last_error = report.get("last_primary_error") or "Unknown error"

    now_iso = datetime.now(UTC).isoformat()
    report["timestamp"] = now_iso

    if is_degraded:
        logger.warning(
            "LLM degradation detected: primary model '%s' failed (errors: %d, fallback: '%s')",
            primary_model,
            report.get("primary_failure_count", 0),
            fallback_model,
        )

        # 1. Persist degraded state to durable store for Desktop & CLI queries
        try:
            state_store.put_key(HEALTH_RECORD_KEY, json.dumps(report))
        except Exception as err:
            logger.warning("Failed to persist LLM health record to state store: %s", err)

        # 2. Dispatch realtime warning to Cloudflare Worker for Desktop WebSocket push
        try:
            await notify_worker_event(
                settings,
                "system_warning",
                {
                    "code": "LLM_PRIMARY_DEGRADED",
                    "model": primary_model,
                    "fallback": fallback_model,
                    "error": last_error,
                    "failure_count": report.get("primary_failure_count", 1),
                },
            )
        except Exception as err:
            logger.debug("Failed to dispatch worker alert event: %s", err)

        # 3. Deliver debounced Telegram notification to operator
        if telegram is not None:
            try:
                last_alert_iso = state_store.get_key(ALERT_TIMESTAMP_KEY)
                if not is_alert_debounced(last_alert_iso, cooldown_hours=debounce_hours):
                    clean_error = last_error.split("\n")[0][:250]
                    msg_text = (
                        "⚠️ <b>LLM Warning: Operating on Fallback Model</b>\n\n"
                        f"The primary model (<code>{html.escape(primary_model)}</code>) failed during execution:\n"
                        f"<code>{html.escape(clean_error)}</code>\n\n"
                        f"The agent automatically routed requests to <code>{html.escape(fallback_model)}</code>. "
                        "Suggestions will continue to be drafted, but output style or formatting may vary.\n\n"
                        "👉 <i>You can select another model in Desktop Settings or update your repository variables.</i>"
                    )
                    await telegram.send_notification(msg_text)
                    state_store.put_key(ALERT_TIMESTAMP_KEY, now_iso)
                    logger.info("Sent debounced LLM degradation alert to Telegram")
                else:
                    logger.debug(
                        "Telegram LLM alert suppressed by %gh debounce window", debounce_hours
                    )
            except Exception as err:
                logger.warning("Failed to deliver LLM degradation alert to Telegram: %s", err)

    else:
        # Check if previously degraded, and clear/recover if so
        try:
            raw_previous = state_store.get_key(HEALTH_RECORD_KEY)
            if raw_previous:
                prev_data = json.loads(raw_previous)
                if prev_data.get("status") == "degraded":
                    state_store.put_key(
                        HEALTH_RECORD_KEY,
                        json.dumps(
                            {
                                "status": "healthy",
                                "primary_model": primary_model,
                                "fallback_model": fallback_model,
                                "timestamp": now_iso,
                            }
                        ),
                    )
                    await notify_worker_event(
                        settings,
                        "system_recovered",
                        {"code": "LLM_HEALTHY", "model": primary_model},
                    )
                    logger.info("LLM health restored to healthy status")
        except Exception as err:
            logger.debug("Could not verify or update LLM recovery state: %s", err)

    return report
