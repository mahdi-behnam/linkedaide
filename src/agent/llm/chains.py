"""Structured LangChain Runnable chains for LLM operations.

Architecture Invariants:
- Chains use LangChain's structured output mechanism (`with_structured_output`).
- Pydantic models (TriageResult, CommentDraft, PostIdea) define the strict return types.
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from agent.config import Settings
from agent.llm.models import build_chat_model
from agent.llm.prompts import (
    build_comment_prompt,
    build_post_idea_prompt,
    build_thread_reply_prompt,
    build_thread_triage_prompt,
    build_triage_prompt,
)
from agent.models.schemas import CommentDraft, PostIdea, ReplyTriageResult, TriageResult


@dataclass(frozen=True)
class LLMChains:
    """Encapsulates structured LangChain Runnable chains."""

    triage: Runnable[dict[str, Any], Any]
    comment: Runnable[dict[str, Any], Any]
    post_idea: Runnable[dict[str, Any], Any]
    thread_triage: Runnable[dict[str, Any], Any] | None = None
    thread_reply: Runnable[dict[str, Any], Any] | None = None


def build_structured_chains(
    settings: Settings,
    *,
    triage_model: BaseChatModel | None = None,
    generation_model: BaseChatModel | None = None,
) -> LLMChains:
    """Construct structured Runnable chains for triage, comment drafting, ideation, and thread engagement.

    Args:
        settings: Application configuration settings.
        triage_model: Optional pre-configured chat model for triage.
        generation_model: Optional pre-configured chat model for drafting.

    Returns:
        LLMChains instance holding structured Runnables.
    """
    model_triage = triage_model or build_chat_model(settings, role="triage")
    model_gen = generation_model or build_chat_model(settings, role="generation")

    triage_prompt = build_triage_prompt()
    comment_prompt = build_comment_prompt()
    post_idea_prompt = build_post_idea_prompt()
    thread_triage_prompt = build_thread_triage_prompt()
    thread_reply_prompt = build_thread_reply_prompt()

    triage_chain = triage_prompt | model_triage.with_structured_output(TriageResult)
    comment_chain = comment_prompt | model_gen.with_structured_output(CommentDraft)
    post_idea_chain = post_idea_prompt | model_gen.with_structured_output(PostIdea)
    thread_triage_chain = thread_triage_prompt | model_triage.with_structured_output(
        ReplyTriageResult
    )
    thread_reply_chain = thread_reply_prompt | model_gen.with_structured_output(CommentDraft)

    return LLMChains(
        triage=triage_chain,
        comment=comment_chain,
        post_idea=post_idea_chain,
        thread_triage=thread_triage_chain,
        thread_reply=thread_reply_chain,
    )
