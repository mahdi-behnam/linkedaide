"""Resilience abstractions for NVIDIA NIM LLM operations.

Architecture Invariants:
- Concurrency control: Enforces semaphore concurrency bounding across calls.
- Transient resilience: Exponential backoff with full jitter on rate limits, timeouts, and server errors.
- Schema repair: Exactly one bounded corrective repair turn on validation/JSON errors.
- Fallback chain: Seamless fallback to secondary model on primary chain exhaustion.
- Typed errors: Strict mapping of unhandled errors to typed NIMError exceptions.
"""

from __future__ import annotations

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
from agent.llm.chains import LLMChains
from agent.llm.models import build_chat_model
from agent.llm.prompts import (
    build_repair_prompt,
    build_thread_reply_prompt,
    build_thread_triage_prompt,
)
from agent.models import (
    CommentDraft,
    ReplyTriageResult,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def is_transient_error(err: Exception) -> bool:
    """Check if an exception represents a transient failure eligible for retry."""
    if isinstance(err, NIMRateLimitError | NIMTimeoutError | TimeoutError | asyncio.TimeoutError):
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


def raise_typed_nim_error(err: Exception) -> NoReturn:
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


async def attempt_schema_repair(
    repair_model: BaseChatModel | Any | None,
    repair_prompt: Any,
    raw_output: str,
    target_schema: type[T],
    error_details: str,
) -> T | None:
    """Attempt exactly ONE repair turn using the repair prompt and schema validation."""
    if repair_model is None:
        return None

    try:
        repair_input = {
            "schema_name": target_schema.__name__,
            "error_details": error_details,
            "raw_output": raw_output,
        }
        messages = repair_prompt.format_messages(**repair_input)
        response = await repair_model.ainvoke(messages)
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

        parsed_dict = json.loads(cleaned)
        return target_schema.model_validate(parsed_dict)
    except Exception as e:
        logger.warning(f"Schema repair attempt failed: {e}")
        return None


def get_chain(
    chains: LLMChains,
    chain_name: str,
    settings: Settings | None = None,
    repair_model: Any | None = None,
) -> Any:
    """Resolve chain by name from an LLMChains bundle."""
    if chain_name == "triage":
        return chains.triage
    if chain_name == "comment":
        return chains.comment
    if chain_name == "post_idea":
        return chains.post_idea
    if chain_name == "thread_triage":
        if getattr(chains, "thread_triage", None) is not None:
            return chains.thread_triage
        prompt = build_thread_triage_prompt()
        model = repair_model or (build_chat_model(settings, role="triage") if settings else None)
        if model is None:
            raise ValueError("No model available for thread_triage chain")
        return prompt | model.with_structured_output(ReplyTriageResult)
    if chain_name == "thread_reply":
        if getattr(chains, "thread_reply", None) is not None:
            return chains.thread_reply
        prompt = build_thread_reply_prompt()
        model = repair_model or (
            build_chat_model(settings, role="generation") if settings else None
        )
        if model is None:
            raise ValueError("No model available for thread_reply chain")
        return prompt | model.with_structured_output(CommentDraft)
    raise ValueError(f"Unknown chain name '{chain_name}'")


class ResilienceRunner:
    """Manages concurrency, retry backoff, schema repair, and fallback execution."""

    def __init__(
        self,
        settings: Settings,
        chains: LLMChains,
        fallback_chains: LLMChains,
        repair_model: BaseChatModel | Any | None = None,
        repair_prompt: Any | None = None,
        backoff_base: float = 1.5,
        max_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.chains = chains
        self.fallback_chains = fallback_chains
        self.repair_model = repair_model
        self.repair_prompt = repair_prompt or build_repair_prompt()
        self.backoff_base = backoff_base
        self.max_attempts = max_attempts
        self.semaphore = asyncio.Semaphore(settings.nim_max_concurrency)

        # Operational telemetry and health tracking
        self.primary_failure_count: int = 0
        self.last_primary_error: str | None = None
        self.has_primary_404: bool = False
        self.fallback_invocations: int = 0

    @property
    def has_primary_failure(self) -> bool:
        """Return True if the primary model failed at least once during this runner's lifecycle."""
        return self.primary_failure_count > 0

    @property
    def fallback_used(self) -> bool:
        """Return True if the fallback model was invoked at least once."""
        return self.fallback_invocations > 0

    def get_health_report(self) -> dict[str, Any]:
        """Compile a dynamic health report for the LLM runner without hardcoded model strings."""
        is_degraded = self.has_primary_failure
        return {
            "status": "degraded" if is_degraded else "healthy",
            "primary_model": self.settings.effective_primary_model,
            "fallback_model": self.settings.effective_fallback_model,
            "primary_failure_count": self.primary_failure_count,
            "fallback_invocations": self.fallback_invocations,
            "has_primary_404": self.has_primary_404,
            "last_primary_error": self.last_primary_error,
        }

    async def execute(
        self,
        chain_name: str,
        input_data: dict[str, Any],
        target_schema: type[T],
    ) -> T:
        """Execute a chain with semaphore concurrency, retry with jitter, schema repair, and fallback."""
        async with self.semaphore:
            # Step 1: Attempt execution with primary chain
            try:
                primary_chain = get_chain(
                    self.chains,
                    chain_name,
                    settings=self.settings,
                    repair_model=self.repair_model,
                )
                return await self.run_chain_with_retry(
                    primary_chain,
                    input_data,
                    target_schema,
                )
            except Exception as primary_err:
                self.primary_failure_count += 1
                self.last_primary_error = str(primary_err)
                if "404" in str(primary_err).lower():
                    self.has_primary_404 = True
                logger.warning(
                    f"Primary chain '{chain_name}' failed ({type(primary_err).__name__}: {primary_err}). "
                    "Attempting fallback model..."
                )

            # Step 2: Attempt fallback chain
            self.fallback_invocations += 1
            try:
                fallback_chain = get_chain(
                    self.fallback_chains,
                    chain_name,
                    settings=self.settings,
                    repair_model=self.repair_model,
                )
                return await self.run_chain_with_retry(
                    fallback_chain,
                    input_data,
                    target_schema,
                )
            except Exception as fallback_err:
                logger.error(
                    f"Fallback chain '{chain_name}' also failed ({type(fallback_err).__name__}: {fallback_err})."
                )
                raise_typed_nim_error(fallback_err)

    async def run_chain_with_retry(
        self,
        chain: Any,
        input_data: dict[str, Any],
        target_schema: type[T],
    ) -> T:
        """Run chain with exponential backoff + jitter for transient errors, and 1-turn repair for schema errors."""
        last_error: Exception | None = None

        for attempt in range(self.max_attempts):
            try:
                result = await chain.ainvoke(input_data)
                if isinstance(result, target_schema):
                    return result
                if isinstance(result, dict):
                    return target_schema.model_validate(result)
                if isinstance(result, str):
                    repaired = await attempt_schema_repair(
                        self.repair_model,
                        self.repair_prompt,
                        result,
                        target_schema,
                        "Model returned raw string",
                    )
                    if repaired is not None:
                        return repaired
                    raise ValidationError.from_exception_data("Schema validation error", [])
                return target_schema.model_validate(result)
            except (ValidationError, ValueError, json.JSONDecodeError) as schema_err:
                logger.info(
                    f"Schema validation error on attempt {attempt + 1}: {schema_err}. Attempting repair..."
                )
                repaired = await attempt_schema_repair(
                    self.repair_model,
                    self.repair_prompt,
                    str(schema_err),
                    target_schema,
                    str(schema_err),
                )
                if repaired is not None:
                    return repaired
                last_error = schema_err
                # Schema repair failed, do not loop transient retries for static schema error
                break
            except Exception as transient_err:
                last_error = transient_err
                if not is_transient_error(transient_err) or attempt == self.max_attempts - 1:
                    break
                # Exponential backoff with full jitter
                sleep_seconds = random.uniform(0, self.backoff_base * (2**attempt))
                logger.debug(
                    f"Transient error ({transient_err}). Retrying in {sleep_seconds:.2f}s..."
                )
                await asyncio.sleep(sleep_seconds)

        assert last_error is not None
        raise last_error
