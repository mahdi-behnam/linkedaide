"""Topology and safety routing invariant tests for LangGraph state machines."""

from __future__ import annotations

from agent.graphs.execute_graph import build_execute_graph
from agent.graphs.health_graph import build_health_graph
from agent.graphs.scout_graph import build_scout_graph


def test_scout_graph_nodes_present() -> None:
    """Verify all expected nodes exist in ScoutGraph."""
    graph = build_scout_graph()
    # graph is a CompiledStateGraph
    nodes = set(graph.nodes.keys())
    expected_nodes = {
        "check_halted",
        "load_seen",
        "scrape_feed",
        "triage_batch",
        "draft_batch",
        "rank_and_build_pending",
        "persist_state",
        "send_telegram_suggestions",
    }
    for node in expected_nodes:
        assert node in nodes, f"Missing required node '{node}' in ScoutGraph"


def test_execute_graph_nodes_present() -> None:
    """Verify all expected nodes exist in ExecuteGraph."""
    graph = build_execute_graph()
    nodes = set(graph.nodes.keys())
    expected_nodes = {
        "check_halted",
        "load_pending",
        "notify_already_handled",
        "handle_rejection",
        "validate_request",
        "verify_target",
        "execute_browser_action",
        "persist_success",
        "notify_success",
        "handle_failure",
    }
    for node in expected_nodes:
        assert node in nodes, f"Missing required node '{node}' in ExecuteGraph"


def test_health_graph_nodes_present() -> None:
    """Verify all expected nodes exist in HealthCheckGraph."""
    graph = build_health_graph()
    nodes = set(graph.nodes.keys())
    expected_nodes = {
        "check_halted",
        "verify_session",
    }
    for node in expected_nodes:
        assert node in nodes, f"Missing required node '{node}' in HealthCheckGraph"
