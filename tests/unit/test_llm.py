"""Unit tests for LangChain and NVIDIA NIM integration (models, prompts, chains, service)."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from agent.config import Settings
from agent.errors import (
    ConfigError,
    NIMError,
    NIMRateLimitError,
    NIMSchemaValidationError,
    NIMTimeoutError,
)
from agent.llm.chains import LLMChains, build_structured_chains
from agent.llm.models import build_chat_model
from agent.llm.prompts import (
    build_comment_prompt,
    build_post_idea_prompt,
    build_repair_prompt,
    build_triage_prompt,
)
from agent.llm.resilience import get_chain, raise_typed_nim_error
from agent.llm.service import LLMService
from agent.models import (
    CommentDraft,
    EngagementStyle,
    PostIdea,
    PostIdeationContext,
    PostRecord,
    RiskFlag,
    TriageResult,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create test settings fixture."""
    return Settings(
        nvidia_nim_api_key="nvapi-mock-key-12345",
        nim_model_primary="nvidia/nemotron-3-ultra-550b-a55b",
        nim_model_fallback="openai/gpt-oss-20b",
        nim_model_triage="openai/gpt-oss-20b-triage",
        nim_temperature=0.2,
        nim_top_p=0.95,
        nim_timeout_seconds=30.0,
        nim_max_tokens=512,
        nim_base_url="https://integrate.api.nvidia.com/v1",
        nim_max_concurrency=2,
        telegram_bot_token="123456:MOCK_TOKEN",
        telegram_authorized_chat_id=123456789,
        user_focus_areas=["Distributed Systems", "AI Agents", "Python"],
        max_comment_words=80,
    )


@pytest.fixture
def sample_post() -> PostRecord:
    """Create sample post fixture."""
    return PostRecord(
        post_urn="urn:li:activity:7890123456",
        post_url="https://linkedin.com/feed/update/urn:li:activity:7890123456",
        author_name="Alice Engineer",
        post_text="Deep dive into consensus algorithms and why Raft is simpler than Paxos.",
        content_hash="mock_hash_123",
        scraped_at=datetime.now(UTC),
    )


class TestChatModelFactory:
    """Test suite for build_chat_model factory function."""

    @patch("agent.llm.models.ChatNVIDIA")
    def test_build_chat_model_roles(
        self, mock_chat_nvidia: MagicMock, mock_settings: Settings
    ) -> None:
        # Triage role
        build_chat_model(mock_settings, role="triage")
        mock_chat_nvidia.assert_called_with(
            model="openai/gpt-oss-20b-triage",
            nvidia_api_key="nvapi-mock-key-12345",
            temperature=0.2,
            max_completion_tokens=512,
            timeout=30.0,
            base_url="https://integrate.api.nvidia.com/v1",
            top_p=0.95,
        )

        # Generation role
        build_chat_model(mock_settings, role="generation")
        assert mock_chat_nvidia.call_args[1]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"

        # Fallback role
        build_chat_model(mock_settings, role="fallback")
        assert mock_chat_nvidia.call_args[1]["model"] == "openai/gpt-oss-20b"

        # Explicit model name override
        build_chat_model(mock_settings, model_name="custom/model-v1")
        assert mock_chat_nvidia.call_args[1]["model"] == "custom/model-v1"

    @patch("agent.llm.models.ChatOpenAI")
    def test_build_chat_model_openai(
        self, mock_chat_openai: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "openai")
        object.__setattr__(mock_settings, "openai_api_key", "sk-test-openai-12345")
        object.__setattr__(mock_settings, "nim_model_primary", "gpt-4o")
        object.__setattr__(mock_settings, "nim_model_fallback", "gpt-4o-mini")

        build_chat_model(mock_settings, role="generation")
        mock_chat_openai.assert_called_with(
            model="gpt-4o",
            temperature=0.2,
            max_tokens=512,
            timeout=30.0,
            api_key="sk-test-openai-12345",
            base_url="https://integrate.api.nvidia.com/v1",
            top_p=0.95,
        )

        # Triage role falls back to primary model when nim_model_triage is None
        object.__setattr__(mock_settings, "nim_model_triage", None)
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_openai.call_args[1]["model"] == "gpt-4o"

        # Explicit triage model
        object.__setattr__(mock_settings, "nim_model_triage", "gpt-4o-mini")
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_openai.call_args[1]["model"] == "gpt-4o-mini"

        # Fallback role uses nim_model_fallback
        build_chat_model(mock_settings, role="fallback")
        assert mock_chat_openai.call_args[1]["model"] == "gpt-4o-mini"

        # Explicit model name override
        build_chat_model(mock_settings, model_name="gpt-4-turbo")
        assert mock_chat_openai.call_args[1]["model"] == "gpt-4-turbo"

    @patch("agent.llm.models.ChatOpenAI")
    def test_build_chat_model_openai_compatible(
        self, mock_chat_openai: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "openai-compatible")
        object.__setattr__(mock_settings, "nim_base_url", "https://api.together.xyz/v1")
        object.__setattr__(mock_settings, "openai_api_key", "sk-compat-key")

        build_chat_model(mock_settings, model_name="meta-llama/Llama-3-70b-chat-hf")
        mock_chat_openai.assert_called_with(
            model="meta-llama/Llama-3-70b-chat-hf",
            temperature=0.2,
            max_tokens=512,
            timeout=30.0,
            api_key="sk-compat-key",
            base_url="https://api.together.xyz/v1",
            top_p=0.95,
        )

    @patch("agent.llm.models.ChatAnthropic")
    def test_build_chat_model_anthropic(
        self, mock_chat_anthropic: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "anthropic")
        object.__setattr__(mock_settings, "anthropic_api_key", "sk-ant-test-98765")
        object.__setattr__(mock_settings, "nim_model_primary", "claude-3-5-sonnet-latest")
        object.__setattr__(mock_settings, "nim_model_fallback", "claude-3-5-haiku-latest")
        object.__setattr__(mock_settings, "nim_model_triage", None)

        build_chat_model(mock_settings, role="generation")
        mock_chat_anthropic.assert_called_with(
            model="claude-3-5-sonnet-latest",
            temperature=0.2,
            max_tokens=512,
            timeout=30.0,
            api_key="sk-ant-test-98765",
            top_p=0.95,
        )

        # Triage role falls back to primary model when nim_model_triage is None
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_anthropic.call_args[1]["model"] == "claude-3-5-sonnet-latest"

        # Explicit triage model
        object.__setattr__(mock_settings, "nim_model_triage", "claude-3-5-haiku-latest")
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_anthropic.call_args[1]["model"] == "claude-3-5-haiku-latest"

        # Fallback role uses nim_model_fallback
        build_chat_model(mock_settings, role="fallback")
        assert mock_chat_anthropic.call_args[1]["model"] == "claude-3-5-haiku-latest"

    @patch("agent.llm.models.ChatGoogleGenerativeAI")
    def test_build_chat_model_gemini(
        self, mock_chat_gemini: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "gemini")
        object.__setattr__(mock_settings, "gemini_api_key", "AIzaSyFakeGeminiKey")
        object.__setattr__(mock_settings, "nim_model_primary", "gemini-2.0-flash")
        object.__setattr__(mock_settings, "nim_model_fallback", "gemini-1.5-flash")
        object.__setattr__(mock_settings, "nim_model_triage", None)

        build_chat_model(mock_settings, role="generation")
        mock_chat_gemini.assert_called_with(
            model="gemini-2.0-flash",
            temperature=0.2,
            max_output_tokens=512,
            timeout=30.0,
            google_api_key="AIzaSyFakeGeminiKey",
            top_p=0.95,
        )

        # Fallback role uses nim_model_fallback
        build_chat_model(mock_settings, role="fallback")
        assert mock_chat_gemini.call_args[1]["model"] == "gemini-1.5-flash"

        # Triage role uses nim_model_triage when configured
        object.__setattr__(mock_settings, "nim_model_triage", "gemini-1.5-flash")
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_gemini.call_args[1]["model"] == "gemini-1.5-flash"

    @patch("agent.llm.models.ChatGroq")
    def test_build_chat_model_groq(
        self, mock_chat_groq: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "groq")
        object.__setattr__(mock_settings, "groq_api_key", "gsk-test-groq-key")
        object.__setattr__(mock_settings, "nim_model_primary", "llama-3.3-70b-versatile")
        object.__setattr__(mock_settings, "nim_model_fallback", "llama-3.1-8b-instant")
        object.__setattr__(mock_settings, "nim_model_triage", None)

        build_chat_model(mock_settings, role="generation")
        mock_chat_groq.assert_called_with(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=512,
            timeout=30.0,
            groq_api_key="gsk-test-groq-key",
            top_p=0.95,
        )

        # Fallback role uses nim_model_fallback
        build_chat_model(mock_settings, role="fallback")
        assert mock_chat_groq.call_args[1]["model"] == "llama-3.1-8b-instant"

        # Triage role uses nim_model_triage when configured
        object.__setattr__(mock_settings, "nim_model_triage", "llama-3.1-8b-instant")
        build_chat_model(mock_settings, role="triage")
        assert mock_chat_groq.call_args[1]["model"] == "llama-3.1-8b-instant"

    @patch("agent.llm.models.ChatOllama")
    def test_build_chat_model_ollama(
        self, mock_chat_ollama: MagicMock, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", "ollama")
        object.__setattr__(mock_settings, "ollama_base_url", "http://localhost:11434")
        object.__setattr__(mock_settings, "nim_model_primary", "llama3.2")

        build_chat_model(mock_settings, role="generation")
        mock_chat_ollama.assert_called_with(
            model="llama3.2",
            base_url="http://localhost:11434",
            temperature=0.2,
            top_p=0.95,
        )

    def test_build_chat_model_unsupported_provider(self, mock_settings: Settings) -> None:
        object.__setattr__(mock_settings, "llm_provider", "unsupported_provider")
        with pytest.raises(ValueError, match="Unsupported LLM provider 'unsupported_provider'"):
            build_chat_model(mock_settings)

    def test_build_chat_model_unconfigured_model_raises_config_error(
        self, mock_settings: Settings
    ) -> None:
        object.__setattr__(mock_settings, "nim_model_primary", "")
        with pytest.raises(ConfigError, match="No LLM model configured for role 'generation'"):
            build_chat_model(mock_settings)

    @pytest.mark.parametrize(
        ("provider", "cls_name", "expected_package"),
        [
            ("openai", "ChatOpenAI", "langchain-openai"),
            ("anthropic", "ChatAnthropic", "langchain-anthropic"),
            ("gemini", "ChatGoogleGenerativeAI", "langchain-google-genai"),
            ("groq", "ChatGroq", "langchain-groq"),
            ("ollama", "ChatOllama", "langchain-ollama"),
        ],
    )
    def test_missing_optional_provider_package_raises_import_error(
        self,
        provider: str,
        cls_name: str,
        expected_package: str,
        mock_settings: Settings,
    ) -> None:
        object.__setattr__(mock_settings, "llm_provider", provider)
        with patch(f"agent.llm.models.{cls_name}", None):
            with pytest.raises(ImportError, match=f"uv add {expected_package}"):
                build_chat_model(mock_settings)


class TestPrompts:
    """Test suite for prompt templates."""

    def test_triage_prompt_rendering(self) -> None:
        prompt = build_triage_prompt()
        messages = prompt.format_messages(
            user_focus_areas="AI, Python",
            author_name="Bob",
            post_url="https://linkedin.com/123",
            post_text="Sample text about Python.",
        )
        assert len(messages) == 2
        assert "AI, Python" in messages[0].content
        assert "Bob" in messages[1].content
        assert "Sample text about Python." in messages[1].content

    def test_comment_prompt_rendering(self) -> None:
        prompt = build_comment_prompt()
        messages = prompt.format_messages(
            max_words=75,
            author_name="Charlie",
            post_url="https://linkedin.com/456",
            post_text="Microservices architecture post.",
            triage_reasoning="High relevance to distributed systems.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE.value,
        )
        assert len(messages) == 2
        assert "75 words" in messages[0].content
        assert "NEVER start with or include generic praise" in messages[0].content
        assert "Charlie" in messages[1].content
        assert "High relevance" in messages[1].content
        assert "technical_deep_dive" in messages[1].content

    def test_post_idea_prompt_rendering(self) -> None:
        prompt = build_post_idea_prompt()
        messages = prompt.format_messages(
            user_focus_areas="Python internals",
            recent_topics="GIL removal, asyncio queues",
        )
        assert len(messages) == 2
        assert "Python internals" in messages[0].content
        assert "GIL removal" in messages[0].content

    def test_repair_prompt_rendering(self) -> None:
        prompt = build_repair_prompt()
        messages = prompt.format_messages(
            schema_name="TriageResult",
            error_details="Field 'confidence' is required",
            raw_output='{"recommendation": "comment"}',
        )
        assert len(messages) == 2
        assert "TriageResult" in messages[0].content
        assert "Field 'confidence' is required" in messages[0].content


class TestStructuredChains:
    """Test suite for build_structured_chains."""

    def test_build_structured_chains(self, mock_settings: Settings) -> None:
        mock_model = MagicMock()
        mock_model.with_structured_output.return_value = RunnableLambda(lambda x: x)

        chains = build_structured_chains(
            mock_settings,
            triage_model=mock_model,
            generation_model=mock_model,
        )

        assert isinstance(chains, LLMChains)
        assert chains.triage is not None
        assert chains.comment is not None
        assert chains.post_idea is not None


class TestLLMService:
    """Test suite for LLMService execution, resilience, repair, and fallback."""

    def _create_mock_chains(
        self,
        triage_fn: Any = None,
        comment_fn: Any = None,
        post_idea_fn: Any = None,
    ) -> LLMChains:
        """Create mock LLMChains helper."""
        triage_chain = RunnableLambda(
            triage_fn
            or (
                lambda x: TriageResult(
                    recommendation="comment",
                    confidence=0.9,
                    reasoning="Relevant post",
                    risk_flags=[],
                )
            )
        )
        comment_chain = RunnableLambda(
            comment_fn
            or (
                lambda x: CommentDraft(
                    draft_comment="Valuable insight regarding consensus safety.",
                    topic_tags=["distributed-systems"],
                )
            )
        )
        post_idea_chain = RunnableLambda(
            post_idea_fn
            or (
                lambda x: PostIdea(
                    should_post=True,
                    headline="Why Consensus Matters",
                    draft_post_text="Consensus is fundamental in distributed state machines...",
                    hashtags=["#DistributedSystems"],
                    reasoning="Timely discussion on fault tolerance.",
                )
            )
        )
        return LLMChains(
            triage=triage_chain,
            comment=comment_chain,
            post_idea=post_idea_chain,
        )

    @pytest.mark.asyncio
    async def test_evaluate_post_empty_and_whitespace(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        service = LLMService(mock_settings, chains=self._create_mock_chains())

        # Empty text
        sample_post.post_text = ""
        result_empty = await service.evaluate_post(sample_post)
        assert result_empty.recommendation == "ignore"
        assert result_empty.confidence == 1.0
        assert RiskFlag.LOW_SIGNAL in result_empty.risk_flags

        # Whitespace text
        sample_post.post_text = "   \n\t   "
        result_ws = await service.evaluate_post(sample_post)
        assert result_ws.recommendation == "ignore"
        assert result_ws.confidence == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_post_happy_path(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        chains = self._create_mock_chains()
        service = LLMService(mock_settings, chains=chains, backoff_base=0.01)

        result = await service.evaluate_post(sample_post)
        assert isinstance(result, TriageResult)
        assert result.recommendation == "comment"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_draft_comment_happy_path(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")
        service = LLMService(mock_settings, chains=self._create_mock_chains(), backoff_base=0.01)

        draft = await service.draft_comment(sample_post, triage)
        assert isinstance(draft, CommentDraft)
        assert "consensus safety" in draft.draft_comment

    @pytest.mark.asyncio
    async def test_draft_post_idea_happy_path(self, mock_settings: Settings) -> None:
        service = LLMService(mock_settings, chains=self._create_mock_chains(), backoff_base=0.01)
        ctx = PostIdeationContext(user_focus_areas=["AI Agents"], recent_topics=["Testing"])

        idea = await service.draft_post_idea(ctx)
        assert idea is not None
        assert isinstance(idea, PostIdea)
        assert idea.should_post is True
        assert idea.headline == "Why Consensus Matters"

    @pytest.mark.asyncio
    async def test_transient_error_retry_success(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        attempts = 0

        async def flaky_triage(input_data: Any) -> TriageResult:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("HTTP 429 Rate limit encountered")
            return TriageResult(
                recommendation="comment", confidence=0.85, reasoning="Recovered after 429"
            )

        chains = self._create_mock_chains(triage_fn=flaky_triage)
        service = LLMService(mock_settings, chains=chains, backoff_base=0.01)

        result = await service.evaluate_post(sample_post)
        assert attempts == 2
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_rate_limit_exhaustion_fallback_success(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def failing_primary(input_data: Any) -> Any:
            raise RuntimeError("HTTP 429: Rate limit exceeded")

        async def successful_fallback(input_data: Any) -> TriageResult:
            return TriageResult(
                recommendation="comment", confidence=0.75, reasoning="From fallback model"
            )

        primary_chains = self._create_mock_chains(triage_fn=failing_primary)
        fallback_chains = self._create_mock_chains(triage_fn=successful_fallback)

        service = LLMService(
            mock_settings,
            chains=primary_chains,
            fallback_chains=fallback_chains,
            backoff_base=0.01,
            max_attempts=2,
        )

        result = await service.evaluate_post(sample_post)
        assert result.reasoning == "From fallback model"

    @pytest.mark.asyncio
    async def test_schema_error_repair_success(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        # Primary chain returns malformed dictionary missing required fields
        async def broken_triage(input_data: Any) -> dict[str, Any]:
            return {"recommendation": "invalid_val"}

        chains = self._create_mock_chains(triage_fn=broken_triage)

        # Mock repair model returning valid json
        mock_repair_response = AIMessage(
            content='```json\n{"recommendation": "comment", "confidence": 0.88, "reasoning": "Repaired JSON", "risk_flags": []}\n```'
        )
        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.return_value = mock_repair_response

        service = LLMService(
            mock_settings,
            chains=chains,
            fallback_chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )

        result = await service.evaluate_post(sample_post)
        assert result.recommendation == "comment"
        assert result.reasoning == "Repaired JSON"
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    async def test_schema_error_repair_failure_falls_back_to_fallback_model(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def broken_primary(input_data: Any) -> dict[str, Any]:
            return {"invalid": "payload"}

        async def valid_fallback(input_data: Any) -> TriageResult:
            return TriageResult(
                recommendation="ignore", confidence=0.6, reasoning="Fallback after failed repair"
            )

        primary_chains = self._create_mock_chains(triage_fn=broken_primary)
        fallback_chains = self._create_mock_chains(triage_fn=valid_fallback)

        service = LLMService(
            mock_settings,
            chains=primary_chains,
            fallback_chains=fallback_chains,
            backoff_base=0.01,
        )

        # Repair fails
        service.resilience.repair_model = AsyncMock()
        service.resilience.repair_model.ainvoke.side_effect = RuntimeError("Repair failed")

        result = await service.evaluate_post(sample_post)
        assert result.reasoning == "Fallback after failed repair"

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_fail_rate_limit(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def rate_limited(input_data: Any) -> Any:
            raise RuntimeError("429 Too Many Requests")

        primary_chains = self._create_mock_chains(triage_fn=rate_limited)
        fallback_chains = self._create_mock_chains(triage_fn=rate_limited)

        service = LLMService(
            mock_settings,
            chains=primary_chains,
            fallback_chains=fallback_chains,
            backoff_base=0.01,
            max_attempts=2,
        )

        with pytest.raises(NIMRateLimitError):
            await service.evaluate_post(sample_post)

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_fail_timeout(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def timed_out(input_data: Any) -> Any:
            raise TimeoutError("Request timed out after 30s")

        primary_chains = self._create_mock_chains(triage_fn=timed_out)
        fallback_chains = self._create_mock_chains(triage_fn=timed_out)

        service = LLMService(
            mock_settings,
            chains=primary_chains,
            fallback_chains=fallback_chains,
            backoff_base=0.01,
            max_attempts=2,
        )

        with pytest.raises(NIMTimeoutError):
            await service.evaluate_post(sample_post)

    @pytest.mark.asyncio
    async def test_both_primary_and_fallback_fail_schema_validation(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def invalid_schema(input_data: Any) -> dict[str, Any]:
            return {"bad_key": 123}

        primary_chains = self._create_mock_chains(triage_fn=invalid_schema)
        fallback_chains = self._create_mock_chains(triage_fn=invalid_schema)

        service = LLMService(
            mock_settings,
            chains=primary_chains,
            fallback_chains=fallback_chains,
            backoff_base=0.01,
            max_attempts=1,
        )

        # Repair always fails
        service.resilience.repair_model = AsyncMock()
        service.resilience.repair_model.ainvoke.return_value = AIMessage(content="Still invalid")

        with pytest.raises(NIMSchemaValidationError):
            await service.evaluate_post(sample_post)

    @pytest.mark.asyncio
    async def test_concurrency_semaphore_limit(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        active_calls = 0
        max_concurrent_seen = 0

        async def slow_triage(input_data: Any) -> TriageResult:
            nonlocal active_calls, max_concurrent_seen
            active_calls += 1
            max_concurrent_seen = max(max_concurrent_seen, active_calls)
            await asyncio.sleep(0.05)
            active_calls -= 1
            return TriageResult(
                recommendation="comment", confidence=0.9, reasoning="Concurrency test"
            )

        mock_settings.nim_max_concurrency = 2
        chains = self._create_mock_chains(triage_fn=slow_triage)
        service = LLMService(mock_settings, chains=chains, backoff_base=0.01)

        # Run 6 tasks concurrently
        tasks = [service.evaluate_post(sample_post) for _ in range(6)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 6
        assert max_concurrent_seen <= 2

    @pytest.mark.asyncio
    async def test_service_model_returns_raw_string_repaired(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        async def string_triage(input_data: Any) -> str:
            return '{"recommendation": "comment", "confidence": 0.9, "reasoning": "From string"}'

        mock_repair_response = AIMessage(
            content='{"recommendation": "comment", "confidence": 0.9, "reasoning": "From string", "risk_flags": []}'
        )
        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.return_value = mock_repair_response

        chains = self._create_mock_chains(triage_fn=string_triage)
        service = LLMService(
            mock_settings,
            chains=chains,
            fallback_chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )

        result = await service.evaluate_post(sample_post)
        assert result.recommendation == "comment"

    def test_service_unknown_chain_name(self, mock_settings: Settings) -> None:
        service = LLMService(mock_settings, chains=self._create_mock_chains(), backoff_base=0.01)
        with pytest.raises(ValueError, match="Unknown chain name 'invalid_chain'"):
            get_chain(service.resilience.chains, "invalid_chain")

    def test_service_raise_typed_nim_error_variants(self, mock_settings: Settings) -> None:
        # Pre-typed NIMRateLimitError
        with pytest.raises(NIMRateLimitError):
            raise_typed_nim_error(NIMRateLimitError("Already typed 429"))

        # Generic NIMError fallback
        with pytest.raises(NIMError) as exc_info:
            raise_typed_nim_error(RuntimeError("Unknown internal failure"))
        assert "NVIDIA NIM operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_draft_post_idea_empty_context(self, mock_settings: Settings) -> None:
        service = LLMService(mock_settings, chains=self._create_mock_chains(), backoff_base=0.01)
        mock_settings.user_focus_areas = []

        ctx = PostIdeationContext(user_focus_areas=[], recent_topics=[])
        idea = await service.draft_post_idea(ctx)
        assert idea is not None
