"""Typed state definitions and runtime context schema for LangGraph graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from langchain_core.runnables import RunnableConfig

from agent.browser.executor import ActionExecutor
from agent.browser.scraper import FeedScraper
from agent.config import Settings
from agent.llm.service import LLMService
from agent.models import (
    CommentDraft,
    ConnectionRequestAction,
    HistoryEntry,
    PendingAction,
    PostIdea,
    PostRecord,
    TriageResult,
)
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient


class ScoutState(TypedDict, total=False):
    """Workflow state for ScoutGraph."""

    posts: list[PostRecord]
    seen_hashes: set[str]
    triage_results: list[tuple[PostRecord, TriageResult]]
    drafts: list[tuple[PostRecord, TriageResult, CommentDraft]]
    pending_items: list[PendingAction]
    connection_candidates: list[ConnectionRequestAction]
    pruned_items: list[PendingAction]
    errors: list[str]
    halted_reason: str | None
    status: str


class ExecuteState(TypedDict, total=False):
    """Workflow state for ExecuteGraph."""

    action: Literal["approve", "reject"] | str
    item_id: str
    telegram_chat_id: int | None
    telegram_message_id: int | None
    telegram_callback_query_id: str | None
    pending: PendingAction | None
    outcome: HistoryEntry | None
    halted_reason: str | None
    status: str
    error: str | None


class HealthCheckState(TypedDict, total=False):
    """Workflow state for HealthCheckGraph."""

    is_healthy: bool
    halted_reason: str | None
    error: str | None
    status: str


class IdeationState(TypedDict, total=False):
    """Workflow state for IdeationGraph."""

    user_focus_areas: list[str]
    recent_topics: list[str]
    candidate_ideas: list[PostIdea]
    filtered_ideas: list[PostIdea]
    pending_items: list[PendingAction]
    errors: list[str]
    halted_reason: str | None
    status: str


@dataclass(frozen=True)
class GraphContext:
    """Runtime dependencies injected into LangGraph nodes via runtime context config."""

    settings: Settings
    llm: LLMService | None = None
    state_store: BaseStateStore | None = None
    telegram: TelegramClient | None = None
    scraper: FeedScraper | None = None
    executor: ActionExecutor | None = None
    enforcer: DailyCapEnforcer | None = None


def get_graph_context(config: RunnableConfig) -> GraphContext:
    """Extract typed GraphContext from RunnableConfig."""
    configurable = config.get("configurable", {})
    context = configurable.get("context")
    if not isinstance(context, GraphContext):
        raise ValueError(
            f"Valid GraphContext instance required in config['configurable']['context'], got: {type(context)}"
        )
    return context
