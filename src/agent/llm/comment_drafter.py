"""Comment and thread reply drafting orchestration with voice memory and anti-cliché repair.

Architecture Invariants:
- High-signal drafting: Injects operator bio, voice guidelines, and few-shot examples.
- Multimodal evidence: Injects visual evidence from post images when available.
- Anti-cliché defense: Deterministic scan with bounded 1-turn repair and deterministic sanitization fallback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import Settings
from agent.llm.models import build_chat_model
from agent.llm.multimodal import MultimodalAnalyzer, format_visual_evidence
from agent.llm.resilience import ResilienceRunner
from agent.llm.voice_memory import VoiceMemoryStore
from agent.models import (
    CommentDraft,
    EngagementStyle,
    PostRecord,
    ReplyTriageResult,
    ThreadReplyItem,
    TriageResult,
    VisualContext,
)
from agent.safety.anti_cliche import AntiClicheScanner

logger = logging.getLogger(__name__)


def build_anti_cliche_fallback_comment(post: PostRecord) -> str:
    """Construct a clean, substantive, anti-cliché fallback technical comment."""
    author = post.author_name.strip() if post.author_name else "the author"
    return (
        f"The architecture trade-offs highlighted by {author} emphasize key considerations around "
        "system reliability and operational complexity in production."
    )


class CommentDrafter:
    """Orchestrates comment generation, voice adaptation, and anti-cliché guardrails."""

    def __init__(
        self,
        settings: Settings,
        resilience_runner: ResilienceRunner,
        anti_cliche_scanner: AntiClicheScanner,
        voice_memory: VoiceMemoryStore,
        multimodal_analyzer: MultimodalAnalyzer | None = None,
    ) -> None:
        self.settings = settings
        self.resilience_runner = resilience_runner
        self.anti_cliche_scanner = anti_cliche_scanner
        self.voice_memory = voice_memory
        self.multimodal_analyzer = multimodal_analyzer

    async def draft_comment(
        self,
        post: PostRecord,
        triage: TriageResult,
        *,
        engagement_style: EngagementStyle | str | None = None,
        visual_context: VisualContext | None = None,
    ) -> CommentDraft:
        """Draft a substantive, value-adding LinkedIn comment."""
        raw_text = post.post_text.strip() if post.post_text else ""
        selected_style = (
            engagement_style or triage.engagement_style or EngagementStyle.TECHNICAL_DEEP_DIVE
        )
        style_str = (
            selected_style.value
            if isinstance(selected_style, EngagementStyle)
            else str(selected_style)
        )

        voice_context = self.voice_memory.get_voice_context(post_text=raw_text)

        # Resolve visual context and inject visual evidence
        effective_visual_context = visual_context or getattr(post, "visual_context", None)
        if (
            effective_visual_context is None
            and getattr(post, "image_url", None)
            and self.multimodal_analyzer is not None
        ):
            try:
                effective_visual_context = await self.multimodal_analyzer.analyze(post)
                if hasattr(post, "visual_context") and post.visual_context is None:
                    post.visual_context = effective_visual_context
            except Exception as err:
                logger.warning("Visual analysis failed for post %s: %s", post.post_urn, err)

        visual_evidence_str = format_visual_evidence(effective_visual_context)

        input_data: dict[str, Any] = {
            "max_words": self.settings.max_comment_words,
            "author_name": post.author_name.strip() or "LinkedIn Author",
            "post_url": post.post_url,
            "post_text": raw_text,
            "triage_reasoning": triage.reasoning,
            "engagement_style": style_str,
            "operator_bio": voice_context.get("operator_bio", ""),
            "style_guidelines": voice_context.get("style_guidelines", ""),
            "few_shot_examples": voice_context.get("few_shot_examples", ""),
            "visual_evidence": visual_evidence_str,
        }

        draft = await self.resilience_runner.execute("comment", input_data, CommentDraft)
        if draft.engagement_style is None:
            resolved_enum: EngagementStyle | None = None
            if isinstance(selected_style, EngagementStyle):
                resolved_enum = selected_style
            else:
                try:
                    resolved_enum = EngagementStyle(style_str)
                except ValueError:
                    resolved_enum = EngagementStyle.TECHNICAL_DEEP_DIVE
            draft = draft.model_copy(update={"engagement_style": resolved_enum})

        # Anti-cliché scan and bounded 1-turn repair
        scan_result = self.anti_cliche_scanner.scan(draft.comment_text)
        if not scan_result.passed:
            logger.warning(
                f"Comment draft failed anti-cliché guardrails with {len(scan_result.violations)} violation(s). "
                "Executing exactly one bounded corrective repair turn..."
            )
            repaired_draft = await self.attempt_anti_cliche_repair(
                draft=draft,
                violations=scan_result.violations,
                post=post,
                selected_style=style_str,
                visual_evidence=visual_evidence_str,
            )

            # Re-scan the repaired draft
            if repaired_draft is not None:
                re_scan = self.anti_cliche_scanner.scan(repaired_draft.comment_text)
                if re_scan.passed:
                    logger.info("Repaired comment draft passed anti-cliché guardrails.")
                    if repaired_draft.engagement_style is None:
                        repaired_draft = repaired_draft.model_copy(
                            update={"engagement_style": draft.engagement_style}
                        )
                    return repaired_draft
                logger.warning(
                    f"Repaired draft still failed anti-cliché scan with {len(re_scan.violations)} violation(s). "
                    "Proceeding to deterministic sanitization."
                )
                candidate_text = repaired_draft.comment_text
            else:
                candidate_text = draft.comment_text

            # If it still fails, sanitize the opener deterministically or fallback cleanly
            sanitized = self.anti_cliche_scanner.sanitize(candidate_text)
            if sanitized:
                final_scan = self.anti_cliche_scanner.scan(sanitized)
                if final_scan.passed:
                    logger.info("Deterministic sanitization of repaired draft passed guardrails.")
                    return draft.model_copy(update={"draft_comment": sanitized})

            # If candidate was repaired draft and failed sanitization, try sanitizing original draft
            if candidate_text != draft.comment_text:
                sanitized_orig = self.anti_cliche_scanner.sanitize(draft.comment_text)
                if sanitized_orig:
                    final_scan_orig = self.anti_cliche_scanner.scan(sanitized_orig)
                    if final_scan_orig.passed:
                        logger.info(
                            "Deterministic sanitization of original draft passed guardrails."
                        )
                        return draft.model_copy(update={"draft_comment": sanitized_orig})

            # Clean fallback
            logger.warning(
                "Deterministic sanitization exhausted; returning clean technical fallback."
            )
            fallback_text = build_anti_cliche_fallback_comment(post)
            return draft.model_copy(update={"draft_comment": fallback_text})

        return draft

    async def attempt_anti_cliche_repair(
        self,
        draft: CommentDraft,
        violations: list[str],
        post: PostRecord,
        selected_style: str,
        visual_evidence: str = "",
    ) -> CommentDraft | None:
        """Execute exactly one bounded corrective repair turn with the model."""
        violations_formatted = "\n".join(f"- {v}" for v in violations)
        repair_instruction = (
            "Your previous draft was rejected by the anti-cliché safety guardrail due to the following violations:\n"
            f"{violations_formatted}\n\n"
            "Rewrite the comment strictly avoiding these phrases and jump directly into the technical observation."
        )

        evidence_section = f"\n{visual_evidence}\n" if visual_evidence else "\n"
        messages = [
            SystemMessage(
                content=(
                    f"You are a Principal Software Engineer drafting a high-signal LinkedIn comment under {self.settings.max_comment_words} words. "
                    "Strictly avoid any generic praise, filler buzzwords, or sycophantic openers. "
                    "Start immediately with the substance of your technical insight. "
                    "Respond with a JSON object containing: 'draft_comment' (string) and 'topic_tags' (list of strings)."
                )
            ),
            HumanMessage(
                content=(
                    f"Author: {post.author_name}\n"
                    f'Post: """\n{post.post_text}\n"""{evidence_section}'
                    f'Previous rejected draft:\n"""\n{draft.draft_comment}\n"""\n\n'
                    f"{repair_instruction}"
                )
            ),
        ]

        repair_model = self.resilience_runner.repair_model
        if repair_model is None:
            try:
                repair_model = build_chat_model(self.settings, role="fallback")
            except Exception:
                repair_model = None

        if repair_model is None:
            return None

        try:
            response = await repair_model.ainvoke(messages)
            if isinstance(response, CommentDraft):
                return response
            if isinstance(response, dict):
                return CommentDraft.model_validate(response)

            response_text = response.content if hasattr(response, "content") else str(response)
            if isinstance(response_text, list):
                response_text = " ".join(str(p) for p in response_text)

            cleaned = str(response_text).strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    if "draft_comment" in data:
                        return CommentDraft.model_validate(data)
                    if "comment" in data:
                        return draft.model_copy(update={"draft_comment": data["comment"]})
            except Exception:
                pass

            if cleaned:
                return draft.model_copy(update={"draft_comment": cleaned})
            return None
        except Exception as e:
            logger.warning(f"Anti-cliché repair invocation failed: {e}")
            return None

    async def draft_thread_reply(
        self,
        reply: ThreadReplyItem,
        our_comment: str,
        original_post: str,
        triage: ReplyTriageResult,
    ) -> CommentDraft:
        """Draft a sharp, respectful, direct follow-up reply in a comment thread."""
        raw_text = reply.reply_text.strip() if reply.reply_text else ""
        selected_style = triage.engagement_style or EngagementStyle.TECHNICAL_DEEP_DIVE
        style_str = (
            selected_style.value
            if isinstance(selected_style, EngagementStyle)
            else str(selected_style)
        )

        voice_context = self.voice_memory.get_voice_context(post_text=raw_text)

        input_data: dict[str, Any] = {
            "original_post": original_post.strip() or "N/A",
            "our_comment": our_comment.strip() or "N/A",
            "author_name": reply.author_name.strip() or "LinkedIn Member",
            "author_headline": reply.author_headline.strip() or "",
            "is_post_author": "Yes" if reply.is_post_author else "No",
            "reply_text": raw_text,
            "triage_reasoning": triage.reasoning,
            "engagement_style": style_str,
            "operator_bio": voice_context.get("operator_bio", ""),
            "style_guidelines": voice_context.get("style_guidelines", ""),
        }

        draft = await self.resilience_runner.execute("thread_reply", input_data, CommentDraft)
        if draft.engagement_style is None:
            resolved_enum = (
                selected_style
                if isinstance(selected_style, EngagementStyle)
                else EngagementStyle.TECHNICAL_DEEP_DIVE
            )
            draft = draft.model_copy(update={"engagement_style": resolved_enum})

        # Anti-cliché scan
        scan_result = self.anti_cliche_scanner.scan(draft.comment_text)
        if not scan_result.passed:
            sanitized = self.anti_cliche_scanner.sanitize(draft.comment_text)
            if sanitized:
                final_scan = self.anti_cliche_scanner.scan(sanitized)
                if final_scan.passed:
                    return draft.model_copy(update={"draft_comment": sanitized})

        return draft
