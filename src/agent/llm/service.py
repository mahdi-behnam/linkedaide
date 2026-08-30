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
    PostIdea,
    PostIdeationContext,
    PostRecord,
    RiskFlag,
    TriageResult,
)

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
        backoff_base: float = 1.5,
        max_attempts: int = 3,
    ) -> None:
        self._settings = settings
        self._backoff_base = backoff_base
        self._max_attempts = max_attempts
        self._semaphore = asyncio.Semaphore(settings.nim_max_concurrency)

        self._chains = chains or build_structured_chains(settings)
        if fallback_chains:
            self._fallback_chains = fallback_chains
        else:
            fallback_model = build_chat_model(settings, role="fallback")
            self._fallback_chains = build_structured_chains(
                settings,
                triage_model=fallback_model,
                generation_model=fallback_model,
            )

        self._repair_model = repair_model or build_chat_model(settings, role="fallback")
        self._repair_prompt = build_repair_prompt()

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

    async def draft_comment(self, post: PostRecord, triage: TriageResult) -> CommentDraft:
        """Draft a substantive, value-adding LinkedIn comment."""
        raw_text = post.post_text.strip() if post.post_text else ""
        input_data: dict[str, Any] = {
            "max_words": self._settings.max_comment_words,
            "author_name": post.author_name.strip() or "LinkedIn Author",
            "post_url": post.post_url,
            "post_text": raw_text,
            "triage_reasoning": triage.reasoning,
        }

        return await self._execute_with_resilience("comment", input_data, CommentDraft)

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
            err, (NIMRateLimitError, NIMTimeoutError, TimeoutError, asyncio.TimeoutError)
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
        if isinstance(err, (NIMRateLimitError, NIMTimeoutError, NIMSchemaValidationError)):
            raise err
        if "429" in err_msg or "rate limit" in err_msg:
            raise NIMRateLimitError(f"NVIDIA NIM rate limit exceeded: {err}") from err
        if "timeout" in err_msg or "timed out" in err_msg:
            raise NIMTimeoutError(f"NVIDIA NIM request timed out: {err}") from err
        if isinstance(err, (ValidationError, ValueError, json.JSONDecodeError)):
            raise NIMSchemaValidationError(
                f"NVIDIA NIM structured output schema validation failed: {err}"
            ) from err
        raise NIMError(f"NVIDIA NIM operation failed: {err}") from err
