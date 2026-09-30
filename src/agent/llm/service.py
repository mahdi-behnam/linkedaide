"""LLM Service orchestrating triage, drafting, retry backoff, schema repair, and fallback.

Architecture Invariants:
- High-level business entrypoints: evaluate_post, draft_comment, draft_post_idea.
- Enforces concurrency semaphore, exponential backoff with full jitter, exactly-one schema repair, and fallback model.
- Returns validated Pydantic models or raises typed NIMError sub-exceptions.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from agent.config import Settings
from agent.llm.chains import LLMChains, build_structured_chains
from agent.llm.comment_drafter import CommentDrafter
from agent.llm.models import build_chat_model
from agent.llm.multimodal import MultimodalAnalyzer
from agent.llm.prompts import build_repair_prompt
from agent.llm.resilience import ResilienceRunner
from agent.llm.voice_memory import VoiceMemoryStore
from agent.models import (
    CommentDraft,
    EngagementStyle,
    PostIdea,
    PostIdeationContext,
    PostRecord,
    ReplyTriageResult,
    RiskFlag,
    ThreadReplyItem,
    TriageResult,
    VisualContext,
)
from agent.safety.anti_cliche import AntiClicheScanner

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Service layer managing structured interactions with NVIDIA NIM models."""

    def __init__(
        self,
        settings: Settings,
        *,
        chains: LLMChains | None = None,
        fallback_chains: LLMChains | None = None,
        repair_model: BaseChatModel | Any | None = None,
        anti_cliche_scanner: AntiClicheScanner | None = None,
        voice_memory: VoiceMemoryStore | None = None,
        multimodal_analyzer: MultimodalAnalyzer | None = None,
        backoff_base: float = 1.5,
        max_attempts: int = 3,
    ) -> None:
        self._settings = settings
        self._anti_cliche_scanner = anti_cliche_scanner or AntiClicheScanner()
        self._voice_memory = voice_memory or VoiceMemoryStore()
        self._multimodal_analyzer = (
            multimodal_analyzer if multimodal_analyzer is not None else MultimodalAnalyzer(settings)
        )

        resolved_chains = chains or build_structured_chains(settings)
        if fallback_chains:
            resolved_fallback = fallback_chains
        elif chains:
            resolved_fallback = chains
        else:
            fallback_model = build_chat_model(settings, role="fallback")
            resolved_fallback = build_structured_chains(
                settings,
                triage_model=fallback_model,
                generation_model=fallback_model,
            )

        if repair_model is not None:
            resolved_repair_model = repair_model
        elif chains:
            resolved_repair_model = None
        else:
            resolved_repair_model = build_chat_model(settings, role="fallback")

        self._resilience = ResilienceRunner(
            settings=settings,
            chains=resolved_chains,
            fallback_chains=resolved_fallback,
            repair_model=resolved_repair_model,
            repair_prompt=build_repair_prompt(),
            backoff_base=backoff_base,
            max_attempts=max_attempts,
        )

        self._comment_drafter = CommentDrafter(
            settings=settings,
            resilience_runner=self._resilience,
            anti_cliche_scanner=self._anti_cliche_scanner,
            voice_memory=self._voice_memory,
            multimodal_analyzer=self._multimodal_analyzer,
        )

    @property
    def resilience(self) -> ResilienceRunner:
        """Access the resilience and retry runner."""
        return self._resilience

    @property
    def comment_drafter(self) -> CommentDrafter:
        """Access the comment drafting orchestrator."""
        return self._comment_drafter

    @property
    def anti_cliche_scanner(self) -> AntiClicheScanner:
        """Access the deterministic anti-cliché scanner instance."""
        return self._anti_cliche_scanner

    @property
    def voice_memory(self) -> VoiceMemoryStore:
        """Access the operator voice memory store."""
        return self._voice_memory

    def index_executed_comment(
        self,
        item_id: str,
        comment_text: str,
        post_excerpt: str = "",
    ) -> None:
        """Index an operator-approved executed comment into voice memory for continuous learning."""
        self._voice_memory.index_executed_comment(
            item_id=item_id,
            comment_text=comment_text,
            post_excerpt=post_excerpt,
        )

    @property
    def multimodal_analyzer(self) -> MultimodalAnalyzer | None:
        """Access the multimodal vision analyzer instance."""
        return self._multimodal_analyzer

    async def evaluate_post(self, post: PostRecord) -> TriageResult:
        """Triage a scraped feed post to determine if commenting is recommended.

        Empty or whitespace posts are safely ignored without invoking the model.
        """
        raw_text = post.post_text.strip() if post.post_text else ""
        if not raw_text:
            return TriageResult(
                recommendation="ignore",
                confidence=1.0,
                reasoning="Post text is empty or contains only whitespace.",
                risk_flags=[RiskFlag.LOW_SIGNAL],
                engagement_style=None,
            )

        focus_areas_str = (
            ", ".join(self._settings.user_focus_areas)
            if self._settings.user_focus_areas
            else "General software engineering, AI systems, and distributed architecture"
        )

        input_data: dict[str, Any] = {
            "user_focus_areas": focus_areas_str,
            "author_name": post.author_name.strip() or "LinkedIn Author",
            "post_url": post.post_url,
            "post_text": raw_text,
        }

        return await self._resilience.execute("triage", input_data, TriageResult)

    async def draft_comment(
        self,
        post: PostRecord,
        triage: TriageResult,
        *,
        engagement_style: EngagementStyle | str | None = None,
        visual_context: VisualContext | None = None,
    ) -> CommentDraft:
        """Draft a substantive, value-adding LinkedIn comment."""
        return await self._comment_drafter.draft_comment(
            post=post,
            triage=triage,
            engagement_style=engagement_style,
            visual_context=visual_context,
        )

    async def draft_post_idea(self, context: PostIdeationContext) -> PostIdea | None:
        """Propose an original LinkedIn post idea."""
        focus_areas_str = (
            ", ".join(context.user_focus_areas)
            if context.user_focus_areas
            else ", ".join(self._settings.user_focus_areas)
            if self._settings.user_focus_areas
            else "Software Architecture, Python, AI Agents"
        )
        recent_topics_str = (
            ", ".join(context.recent_topics) if context.recent_topics else "None recorded yet"
        )

        input_data: dict[str, Any] = {
            "user_focus_areas": focus_areas_str,
            "recent_topics": recent_topics_str,
        }

        return await self._resilience.execute("post_idea", input_data, PostIdea)

    async def triage_thread_reply(
        self,
        reply: ThreadReplyItem,
        our_comment: str,
        original_post: str,
    ) -> ReplyTriageResult:
        """Triage an incoming reply to our comment to determine if follow-up is warranted."""
        raw_text = reply.reply_text.strip() if reply.reply_text else ""
        if not raw_text:
            return ReplyTriageResult(
                recommendation="ignore",
                confidence=1.0,
                reasoning="Reply text is empty or contains only whitespace.",
                engagement_style=None,
            )

        input_data: dict[str, Any] = {
            "original_post": original_post.strip() or "N/A",
            "our_comment": our_comment.strip() or "N/A",
            "author_name": reply.author_name.strip() or "LinkedIn Member",
            "author_headline": reply.author_headline.strip() or "",
            "is_post_author": "Yes" if reply.is_post_author else "No",
            "reply_text": raw_text,
        }

        return await self._resilience.execute("thread_triage", input_data, ReplyTriageResult)

    async def draft_thread_reply(
        self,
        reply: ThreadReplyItem,
        our_comment: str,
        original_post: str,
        triage: ReplyTriageResult,
    ) -> CommentDraft:
        """Draft a sharp, respectful, direct follow-up reply in a comment thread."""
        return await self._comment_drafter.draft_thread_reply(
            reply=reply,
            our_comment=our_comment,
            original_post=original_post,
            triage=triage,
        )


__all__ = ["LLMService"]
