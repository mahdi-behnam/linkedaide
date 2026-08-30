"""Read-only LinkedIn session canary HealthCheckGraph."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.errors import BotDetectionError, SessionExpiredError
from agent.graphs.state import HealthCheckState, get_graph_context
from agent.safety.circuit_breaker import is_halted, trip_breaker


async def check_halted(state: HealthCheckState, config: RunnableConfig) -> dict[str, Any]:
    """Check if the system is already halted."""
    context = get_graph_context(config)
    halted, reason = is_halted(context.settings.state_dir.parent, context.settings)
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
        return {"is_healthy": logged_in, "status": "healthy" if logged_in else "unauthenticated"}
    except BotDetectionError as err:
        if context.state_store:
            trip_breaker(context.settings.state_dir.parent, str(err))
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
