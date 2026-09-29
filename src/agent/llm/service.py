"""LLM Service orchestrating triage, drafting, retry backoff, schema repair, and fallback.

Architecture Invariants:
- High-level business entrypoints: evaluate_post, draft_comment, draft_post_idea.
- Enforces concurrency semaphore, exponential backoff with full jitter, exactly-one schema repair, and fallback model.
- Returns validated Pydantic models or raises typed NIMError sub-exceptions.
"""

import asyncio
import json
import logging
import random
from typing import Any, NoReturn, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from agent.config import Settings
from agent.errors import (
    NIMError,
    NIMRateLimitError,
    NIMSchemaValidationError,
    NIMTimeoutError,
)
from agent.llm.chains import LLMChains, build_structured_chains
from agent.llm.models import build_chat_model
from agent.llm.prompts import build_repair_prompt
from agent.models.schemas import (
    CommentDraft,
    EngagementStyle,
    PostIdea,
    PostIdeationContext,
    PostRecord,
    RiskFlag,
    TriageResult,
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
        backoff_base: float = 1.5,
        max_attempts: int = 3,
    ) -> None:
        self._settings = settings
        self._backoff_base = backoff_base
        self._max_attempts = max_attempts
        self._semaphore = asyncio.Semaphore(settings.nim_max_concurrency)
        self._anti_cliche_scanner = anti_cliche_scanner or AntiClicheScanner()

        self._chains = chains or build_structured_chains(settings)
        if fallback_chains:
            self._fallback_chains = fallback_chains
        elif chains:
            self._fallback_chains = chains
        else:
            fallback_model = build_chat_model(settings, role="fallback")
            self._fallback_chains = build_structured_chains(
                settings,
                triage_model=fallback_model,
                generation_model=fallback_model,
            )

        if repair_model is not None:
            self._repair_model = repair_model
        elif chains:
            self._repair_model = None
        else:
            self._repair_model = build_chat_model(settings, role="fallback")
        self._repair_prompt = build_repair_prompt()

    @property
    def anti_cliche_scanner(self) -> AntiClicheScanner:
        """Access the deterministic anti-cliché scanner instance."""
        return self._anti_cliche_scanner

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

        return await self._execute_with_resilience("triage", input_data, TriageResult)

    async def draft_comment(
        self,
        post: PostRecord,
        triage: TriageResult,
        *,
        engagement_style: EngagementStyle | str | None = None,
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

        input_data: dict[str, Any] = {
            "max_words": self._settings.max_comment_words,
            "author_name": post.author_name.strip() or "LinkedIn Author",
            "post_url": post.post_url,
            "post_text": raw_text,
            "triage_reasoning": triage.reasoning,
            "engagement_style": style_str,
        }

        draft = await self._execute_with_resilience("comment", input_data, CommentDraft)
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
        scan_result = self._anti_cliche_scanner.scan(draft.comment_text)
        if not scan_result.passed:
            logger.warning(
                f"Comment draft failed anti-cliché guardrails with {len(scan_result.violations)} violation(s). "
                "Executing exactly one bounded corrective repair turn..."
            )
            repaired_draft = await self._attempt_anti_cliche_repair(
                draft=draft,
                violations=scan_result.violations,
                post=post,
                selected_style=style_str,
            )

            # Re-scan the repaired draft
            if repaired_draft is not None:
                re_scan = self._anti_cliche_scanner.scan(repaired_draft.comment_text)
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
            sanitized = self._anti_cliche_scanner.sanitize(candidate_text)
            if sanitized:
                final_scan = self._anti_cliche_scanner.scan(sanitized)
                if final_scan.passed:
                    logger.info("Deterministic sanitization of repaired draft passed guardrails.")
                    return draft.model_copy(update={"draft_comment": sanitized})

            # If candidate was repaired draft and failed sanitization, try sanitizing original draft
            if candidate_text != draft.comment_text:
                sanitized_orig = self._anti_cliche_scanner.sanitize(draft.comment_text)
                if sanitized_orig:
                    final_scan_orig = self._anti_cliche_scanner.scan(sanitized_orig)
                    if final_scan_orig.passed:
                        logger.info("Deterministic sanitization of original draft passed guardrails.")
                        return draft.model_copy(update={"draft_comment": sanitized_orig})

            # Clean fallback
            logger.warning(
                "Deterministic sanitization exhausted; returning clean technical fallback."
            )
            fallback_text = self._build_anti_cliche_fallback_comment(post)
            return draft.model_copy(update={"draft_comment": fallback_text})

        return draft

    async def _attempt_anti_cliche_repair(
        self,
        draft: CommentDraft,
        violations: list[str],
        post: PostRecord,
        selected_style: str,
    ) -> CommentDraft | None:
        """Execute exactly one bounded corrective repair turn with the model."""
        violations_formatted = "\n".join(f"- {v}" for v in violations)
        repair_instruction = (
            "Your previous draft was rejected by the anti-cliché safety guardrail due to the following violations:\n"
            f"{violations_formatted}\n\n"
            "Rewrite the comment strictly avoiding these phrases and jump directly into the technical observation."
        )

        messages = [
            SystemMessage(
                content=(
                    f"You are a Principal Software Engineer drafting a high-signal LinkedIn comment under {self._settings.max_comment_words} words. "
                    "Strictly avoid any generic praise, filler buzzwords, or sycophantic openers. "
                    "Start immediately with the substance of your technical insight. "
                    "Respond with a JSON object containing: 'draft_comment' (string) and 'topic_tags' (list of strings)."
                )
            ),
            HumanMessage(
                content=(
                    f"Author: {post.author_name}\n"
                    f"Post: \"\"\"\n{post.post_text}\n\"\"\"\n\n"
                    f"Previous rejected draft:\n\"\"\"\n{draft.draft_comment}\n\"\"\"\n\n"
                    f"{repair_instruction}"
                )
            ),
        ]

        repair_model = self._repair_model
        if repair_model is None:
            try:
                repair_model = build_chat_model(self._settings, role="fallback")
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

    def _build_anti_cliche_fallback_comment(self, post: PostRecord) -> str:
        """Construct a clean, substantive, anti-cliché fallback technical comment."""
        author = post.author_name.strip() if post.author_name else "the author"
        return (
            f"The architecture trade-offs highlighted by {author} emphasize key considerations around "
            "system reliability and operational complexity in production."
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

        return await self._execute_with_resilience("post_idea", input_data, PostIdea)

    async def _execute_with_resilience(
        self,
        chain_name: str,
        input_data: dict[str, Any],
        target_schema: type[T],
    ) -> T:
        """Execute a chain with semaphore concurrency, retry with jitter, schema repair, and fallback."""
        async with self._semaphore:
            # Step 1: Attempt execution with primary chain
            try:
                return await self._run_chain_with_retry(
                    self._get_chain(self._chains, chain_name),
                    input_data,
                    target_schema,
                )
            except Exception as primary_err:
                logger.warning(
                    f"Primary chain '{chain_name}' failed ({type(primary_err).__name__}: {primary_err}). "
                    "Attempting fallback model..."
                )

            # Step 2: Attempt fallback chain
            try:
                return await self._run_chain_with_retry(
                    self._get_chain(self._fallback_chains, chain_name),
                    input_data,
                    target_schema,
                )
            except Exception as fallback_err:
                logger.error(
                    f"Fallback chain '{chain_name}' also failed ({type(fallback_err).__name__}: {fallback_err})."
                )
                self._raise_typed_nim_error(fallback_err)

    async def _run_chain_with_retry(
        self,
        chain: Any,
        input_data: dict[str, Any],
        target_schema: type[T],
    ) -> T:
        """Run chain with exponential backoff + jitter for transient errors, and 1-turn repair for schema errors."""
        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                result = await chain.ainvoke(input_data)
                if isinstance(result, target_schema):
                    return result
                if isinstance(result, dict):
                    return target_schema.model_validate(result)
                if isinstance(result, str):
                    repaired = await self._attempt_schema_repair(
                        result, target_schema, "Model returned raw string"
                    )
                    if repaired is not None:
                        return repaired
                    raise ValidationError.from_exception_data("Schema validation error", [])
                return target_schema.model_validate(result)
            except (ValidationError, ValueError, json.JSONDecodeError) as schema_err:
                logger.info(
                    f"Schema validation error on attempt {attempt + 1}: {schema_err}. Attempting repair..."
                )
                repaired = await self._attempt_schema_repair(
                    str(schema_err), target_schema, str(schema_err)
                )
                if repaired is not None:
                    return repaired
                last_error = schema_err
                # Schema repair failed, do not loop transient retries for static schema error
                break
            except Exception as transient_err:
                last_error = transient_err
                if not self._is_transient_error(transient_err) or attempt == self._max_attempts - 1:
                    break
                # Exponential backoff with full jitter
                sleep_seconds = random.uniform(0, self._backoff_base * (2**attempt))
                logger.debug(
                    f"Transient error ({transient_err}). Retrying in {sleep_seconds:.2f}s..."
                )
                await asyncio.sleep(sleep_seconds)

        assert last_error is not None
        raise last_error

    async def _attempt_schema_repair(
        self,
        raw_output: str,
        target_schema: type[T],
        error_details: str,
    ) -> T | None:
        """Attempt exactly ONE repair turn using the repair prompt and schema validation."""
        try:
            repair_input = {
                "schema_name": target_schema.__name__,
                "error_details": error_details,
                "raw_output": raw_output,
            }
            messages = self._repair_prompt.format_messages(**repair_input)
            response = await self._repair_model.ainvoke(messages)
            response_text = response.content if hasattr(response, "content") else str(response)
            if isinstance(response_text, list):
                response_text = " ".join(str(p) for p in response_text)

            # Strip code fences if returned
            cleaned = str(response_text).strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            parsed_dict = json.loads(cleaned)
            return target_schema.model_validate(parsed_dict)
        except Exception as e:
            logger.warning(f"Schema repair attempt failed: {e}")
            return None

    def _get_chain(self, chains: LLMChains, chain_name: str) -> Any:
        if chain_name == "triage":
            return chains.triage
        if chain_name == "comment":
            return chains.comment
        if chain_name == "post_idea":
            return chains.post_idea
        raise ValueError(f"Unknown chain name '{chain_name}'")

    def _is_transient_error(self, err: Exception) -> bool:
        """Check if an exception represents a transient failure eligible for retry."""
        if isinstance(
            err, NIMRateLimitError | NIMTimeoutError | TimeoutError | asyncio.TimeoutError
        ):
            return True
        err_msg = str(err).lower()
        if any(
            marker in err_msg
            for marker in (
                "429",
                "rate limit",
                "too many requests",
                "timeout",
                "timed out",
                "500",
                "502",
                "503",
                "504",
                "connection reset",
                "econnreset",
            )
        ):
            return True
        return False

    def _raise_typed_nim_error(self, err: Exception) -> NoReturn:
        """Translate lower-level exceptions into typed NIMError sub-exceptions."""
        err_msg = str(err).lower()
        if isinstance(err, NIMRateLimitError | NIMTimeoutError | NIMSchemaValidationError):
            raise err
        if "429" in err_msg or "rate limit" in err_msg:
            raise NIMRateLimitError(f"NVIDIA NIM rate limit exceeded: {err}") from err
        if "timeout" in err_msg or "timed out" in err_msg:
            raise NIMTimeoutError(f"NVIDIA NIM request timed out: {err}") from err
        if isinstance(err, ValidationError | ValueError | json.JSONDecodeError):
            raise NIMSchemaValidationError(
                f"NVIDIA NIM structured output schema validation failed: {err}"
            ) from err
        raise NIMError(f"NVIDIA NIM operation failed: {err}") from err
