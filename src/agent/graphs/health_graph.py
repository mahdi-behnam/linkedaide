"""Read-only LinkedIn session canary HealthCheckGraph."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.browser.session import check_session_expiry
from agent.errors import BotDetectionError, SessionExpiredError
from agent.graphs.state import HealthCheckState, get_graph_context
from agent.safety.circuit_breaker import is_halted, trip_breaker


async def check_halted(state: HealthCheckState, config: RunnableConfig) -> dict[str, Any]:
    """Check if the system is already halted."""
    context = get_graph_context(config)
    halted, reason = is_halted(
        context.settings.state_dir.parent, context.settings, state_store=context.state_store
    )
    if halted:
        return {"halted_reason": reason, "status": "halted"}
    return {"halted_reason": None, "status": "active"}


async def verify_session(state: HealthCheckState, config: RunnableConfig) -> dict[str, Any]:
    """Verify session login status (read-only, no writes)."""
    context = get_graph_context(config)
    if not context.executor:
        return {"is_healthy": True, "status": "mock_healthy"}

    try:
        logged_in = await context.executor.verify_login()
        if not logged_in:
            return {"is_healthy": False, "status": "unauthenticated"}

        # Inspect session expiry for proactive warning
        expiry_info = check_session_expiry(
            context.settings.linkedin_storage_state_path,
            warning_days=getattr(context.settings, "session_expiry_warning_days", 3),
        )
        days_rem = expiry_info.get("days_remaining")
        is_expiring = expiry_info.get("is_expiring_soon", False)

        if is_expiring and context.telegram:
            days_str = f"{days_rem:.1f}" if days_rem is not None else "few"
            await context.telegram.send_notification(
                f"⚠️ <b>LinkedIn Session Expiring Soon</b>\n\n"
                f"Your session cookie (<code>li_at</code>) expires in <b>{days_str} days</b>.\n"
                f"Please capture a fresh session via Desktop Cockpit or run:\n"
                f"<code>uv run python scripts/extract_linkedin_session.py</code>"
            )

        return {
            "is_healthy": True,
            "status": "healthy",
            "days_remaining": days_rem,
            "is_expiring_soon": is_expiring,
        }
    except BotDetectionError as err:
        if context.state_store:
            trip_breaker(
                context.settings.state_dir.parent, str(err), state_store=context.state_store
            )
        if context.telegram:
            await context.telegram.send_notification(
                f"🚨 Bot challenge detected during health check: {err}"
            )
        return {"is_healthy": False, "halted_reason": str(err), "status": "halted_challenge"}
    except SessionExpiredError as err:
        if context.telegram:
            await context.telegram.send_notification(
                "⚠️ LinkedIn session expired. Please re-run session extraction."
            )
        return {"is_healthy": False, "error": str(err), "status": "session_expired"}
    except Exception as err:
        return {"is_healthy": False, "error": str(err), "status": "error"}


def route_after_halt(state: HealthCheckState) -> str:
    if state.get("halted_reason"):
        return END
    return "verify_session"


def build_health_graph() -> Any:
    """Build and compile the deterministic HealthCheck StateGraph."""
    graph = StateGraph(HealthCheckState)

    graph.add_node("check_halted", check_halted)
    graph.add_node("verify_session", verify_session)

    graph.add_edge(START, "check_halted")
    graph.add_conditional_edges("check_halted", route_after_halt, [END, "verify_session"])
    graph.add_edge("verify_session", END)

    return graph.compile()
