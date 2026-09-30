"""Unit tests for Persona Voice Vector Memory and Dynamic Few-Shot Prompt Injection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda

from agent.config import Settings
from agent.llm.chains import LLMChains
from agent.llm.prompts import build_comment_prompt
from agent.llm.service import LLMService
from agent.llm.voice_memory import (
    DEFAULT_PROFILE,
    DEFAULT_STYLE_GUIDE,
    DEFAULT_WRITING_SAMPLES,
    VoiceMemoryStore,
    cosine_similarity,
    tokenize,
)
from agent.models import (
    CommentDraft,
    EngagementStyle,
    PostIdea,
    PostRecord,
    TriageResult,
)


@pytest.fixture
def test_settings() -> Settings:
    """Settings fixture for voice memory testing."""
    return Settings(
        nvidia_nim_api_key="nvapi-mock-test-key",
        nim_model_primary="nvidia/mock-model",
        nim_model_fallback="openai/mock-fallback",
        telegram_bot_token="123456:MOCK_TOKEN",
        telegram_authorized_chat_id=123456789,
        max_comment_words=80,
    )


@pytest.fixture
def sample_post_consensus() -> PostRecord:
    """Post fixture about distributed consensus."""
    return PostRecord(
        post_urn="urn:li:activity:1001",
        post_url="https://linkedin.com/feed/update/urn:li:activity:1001",
        author_name="Bob Architect",
        post_text="Exploring Raft vs Paxos for distributed consensus in high-throughput databases.",
        content_hash="hash_1001",
        scraped_at=datetime.now(UTC),
    )


class TestVoiceMemoryBasics:
    """Tests for loading, safe defaults, and text tokenization."""

    def test_tokenize_stopwords_and_length(self) -> None:
        text = "The quick brown fox is running into a distributed consensus partition!"
        tokens = tokenize(text)
        assert "the" not in tokens
        assert "is" not in tokens
        assert "into" not in tokens
        assert "distributed" in tokens
        assert "consensus" in tokens
        assert "partition" in tokens

    def test_cosine_similarity_edge_cases(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
        assert cosine_similarity([1.0, 2.0], [1.0, 2.0]) == pytest.approx(1.0)
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_safe_defaults_when_directory_absent(self, tmp_path: Any) -> None:
        non_existent = tmp_path / "missing_dir"
        store = VoiceMemoryStore(persona_dir=non_existent)

        assert store.profile["name"] == DEFAULT_PROFILE["name"]
        assert store.style_guide == DEFAULT_STYLE_GUIDE
        assert len(store.writing_samples) == len(DEFAULT_WRITING_SAMPLES)

        context = store.get_voice_context("Raft consensus")
        assert "Principal Software Engineer" in context["operator_bio"]
        assert "Technical Depth Over Generalities" in context["style_guidelines"]
        assert "Raft is easier to reason about" in context["few_shot_examples"]

    def test_load_persona_corpus_from_repo(self) -> None:
        store = VoiceMemoryStore()
        assert store.profile["name"] == "Mahdi Behnam"
        assert "enterprise AI" in store.profile["core_domains"]
        assert len(store.profile["contrarian_engineering_stances"]) >= 3
        assert len(store.profile["non_negotiable_opinions"]) >= 3
        assert len(store.writing_samples) >= 10
        assert "Technical Depth Over Generalities" in store.style_guide

    def test_load_custom_persona_directory(self, tmp_path: Any) -> None:
        custom_dir = tmp_path / "custom_persona"
        custom_dir.mkdir()

        (custom_dir / "profile.yaml").write_text(
            """name: "Custom Lead"
role: "Staff Engineer"
bio: "Staff engineer focusing on database engines."
core_domains:
  - "databases"
  - "storage engines"
contrarian_engineering_stances:
  - "LSM trees are overused."
non_negotiable_opinions:
  - "Always benchmark before optimizing."
""",
            encoding="utf-8",
        )

        (custom_dir / "style_guide.md").write_text(
            "Custom style guide: Be extremely concise.", encoding="utf-8"
        )

        (custom_dir / "writing_samples.json").write_text(
            json.dumps(
                [
                    {
                        "id": "c-01",
                        "topic": "lsm trees",
                        "tags": ["lsm", "storage"],
                        "context": "Discussion on write amplification in LSM trees.",
                        "sample": "Write amplification in LSM trees degrades NVMe endurance rapidly.",
                    }
                ]
            ),
            encoding="utf-8",
        )

        store = VoiceMemoryStore(persona_dir=custom_dir)
        assert store.profile["name"] == "Custom Lead"
        assert store.profile["role"] == "Staff Engineer"
        assert store.style_guide == "Custom style guide: Be extremely concise."
        assert len(store.writing_samples) == 1
        assert store.writing_samples[0]["id"] == "c-01"


class TestSimilarityRetrieval:
    """Tests for semantic and normalized token similarity retrieval."""

    def test_retrieval_distributed_consensus(self) -> None:
        store = VoiceMemoryStore()
        query = "Deep dive into consensus algorithms, leader election, and Raft vs Paxos."
        samples = store.retrieve_samples(query, top_k=2)

        assert len(samples) == 2
        top_sample = samples[0]
        assert "consensus" in top_sample["topic"].lower() or "raft" in top_sample["sample"].lower()
        assert "ws-01" in top_sample["id"] or "consensus" in top_sample["tags"]

    def test_retrieval_vector_memory_and_rag(self) -> None:
        store = VoiceMemoryStore()
        query = (
            "Evaluating dense vector embeddings and BM25 hybrid search in enterprise RAG systems."
        )
        samples = store.retrieve_samples(query, top_k=2)

        assert len(samples) == 2
        top_sample = samples[0]
        assert "vector" in top_sample["topic"].lower() or "vector" in top_sample["sample"].lower()
        assert "ws-04" in top_sample["id"] or "rag" in top_sample["tags"]

    def test_retrieval_agentic_workflows(self) -> None:
        store = VoiceMemoryStore()
        query = "Autonomous agent loops vs human in the loop approval workflows."
        samples = store.retrieve_samples(query, top_k=2)

        assert len(samples) == 2
        top_sample = samples[0]
        assert "agentic" in top_sample["topic"].lower() or "hitl" in top_sample["tags"]

    def test_retrieval_edge_cases(self) -> None:
        store = VoiceMemoryStore()
        # top_k <= 0
        assert store.retrieve_samples("distributed", top_k=0) == []
        assert store.retrieve_samples("distributed", top_k=-1) == []

        # query with zero keyword matches falls back safely to top available samples
        fallback_samples = store.retrieve_samples("zzqxj12345 nonmatchinggibberish", top_k=2)
        assert len(fallback_samples) == 2

    def test_custom_embeddings_integration(self) -> None:
        mock_embeddings = MagicMock(spec=Embeddings)
        # Mock embed_documents returning unit vectors
        mock_embeddings.embed_documents.return_value = [[1.0, 0.0, 0.0] for _ in range(13)]
        # Mock embed_query returning a vector aligned with the first embedding
        mock_embeddings.embed_query.return_value = [1.0, 0.0, 0.0]

        store = VoiceMemoryStore(embeddings=mock_embeddings)
        samples = store.retrieve_samples("arbitrary query", top_k=2)
        assert len(samples) == 2
        mock_embeddings.embed_query.assert_called_once_with("arbitrary query")

    def test_embeddings_failure_falls_back_to_token_similarity(self) -> None:
        mock_embeddings = MagicMock(spec=Embeddings)
        mock_embeddings.embed_documents.return_value = [[1.0, 0.0, 0.0] for _ in range(13)]
        mock_embeddings.embed_query.side_effect = RuntimeError("Embeddings API unavailable")

        store = VoiceMemoryStore(embeddings=mock_embeddings)
        # Should gracefully fall back to token similarity without raising
        samples = store.retrieve_samples("Raft consensus algorithms", top_k=2)
        assert len(samples) == 2
        assert "consensus" in samples[0]["topic"].lower() or "raft" in samples[0]["sample"].lower()


class TestHistoryIndexingAndContinuousLearning:
    """Tests for indexing operator-approved executed comments into voice memory."""

    def test_index_executed_comment(self) -> None:
        store = VoiceMemoryStore()
        initial_count = len(store.writing_samples)

        store.index_executed_comment(
            item_id="act-987",
            comment_text="Monotonic clock timestamps prevent clock skew race conditions in distributed leases.",
            post_excerpt="Post exploring server clock drift and NTP synchronization in cloud datacenters.",
        )

        assert len(store.writing_samples) == initial_count + 1

        # Query specifically for clock skew / monotonic leases
        context = store.get_voice_context("server clock drift and monotonic clock synchronization")
        assert "Monotonic clock timestamps prevent clock skew" in context["few_shot_examples"]

    def test_index_executed_comment_empty_text_ignored(self) -> None:
        store = VoiceMemoryStore()
        initial_count = len(store.writing_samples)

        store.index_executed_comment(item_id="act-empty", comment_text="   ", post_excerpt="")
        assert len(store.writing_samples) == initial_count


class TestPromptAndServiceIntegration:
    """Tests for dynamic few-shot prompt injection and LLMService integration."""

    def test_build_comment_prompt_renders_with_voice_memory_context(self) -> None:
        store = VoiceMemoryStore()
        voice_context = store.get_voice_context(
            "Raft consensus and split-brain scenarios under network partitions."
        )

        prompt = build_comment_prompt()
        messages = prompt.format_messages(
            max_words=80,
            author_name="Alice Engineer",
            post_url="https://linkedin.com/123",
            post_text="Raft consensus post.",
            triage_reasoning="High technical relevance.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE.value,
            operator_bio=voice_context["operator_bio"],
            style_guidelines=voice_context["style_guidelines"],
            few_shot_examples=voice_context["few_shot_examples"],
        )

        assert len(messages) == 2
        system_content = messages[0].content
        # Check operator bio injected
        assert "Mahdi Behnam" in system_content or "Operator:" in system_content
        assert "Contrarian Engineering Stances:" in system_content

        # Check style guidelines injected
        assert "Technical Depth Over Generalities" in system_content
        assert "NEVER open with congratulatory platitudes" in system_content

        # Check few-shot examples injected
        assert "### Example 1" in system_content
        assert "Approved Comment:" in system_content

    @pytest.mark.asyncio
    async def test_llm_service_draft_comment_injects_voice_context(
        self,
        test_settings: Settings,
        sample_post_consensus: PostRecord,
    ) -> None:
        captured_inputs: dict[str, Any] = {}

        def mock_comment_chain(inputs: dict[str, Any]) -> CommentDraft:
            nonlocal captured_inputs
            captured_inputs = inputs
            return CommentDraft(
                draft_comment="Leader lease renewals with monotonic clocks ensure split-brain safety under network partitions.",
                topic_tags=["consensus", "raft"],
                engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
            )

        mock_chains = LLMChains(
            triage=RunnableLambda(
                lambda x: TriageResult(
                    recommendation="comment",
                    confidence=0.95,
                    reasoning="High value technical post on Raft.",
                    risk_flags=[],
                    engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
                )
            ),
            comment=RunnableLambda(mock_comment_chain),
            post_idea=RunnableLambda(
                lambda x: PostIdea(
                    should_post=True,
                    headline="Distributed Consensus In Production",
                    draft_post_text="Raft edge cases under partitions.",
                    hashtags=["#DistributedSystems"],
                    reasoning="Timely.",
                )
            ),
        )

        custom_store = VoiceMemoryStore()
        service = LLMService(
            test_settings,
            chains=mock_chains,
            voice_memory=custom_store,
            backoff_base=0.01,
        )

        triage = TriageResult(
            recommendation="comment",
            confidence=0.9,
            reasoning="Valid technical discussion",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )

        draft = await service.draft_comment(sample_post_consensus, triage)

        assert isinstance(draft, CommentDraft)
        assert "Leader lease renewals" in draft.draft_comment

        # Verify voice context parameters were passed into the chain
        assert "operator_bio" in captured_inputs
        assert "Mahdi Behnam" in captured_inputs["operator_bio"]
        assert "style_guidelines" in captured_inputs
        assert "Technical Depth Over Generalities" in captured_inputs["style_guidelines"]
        assert "few_shot_examples" in captured_inputs
        assert "Raft is easier to reason about" in captured_inputs["few_shot_examples"]

    def test_llm_service_index_executed_comment_delegation(
        self,
        test_settings: Settings,
    ) -> None:
        service = LLMService(test_settings, backoff_base=0.01)
        initial_len = len(service.voice_memory.writing_samples)

        service.index_executed_comment(
            item_id="exec-555",
            comment_text="Production orchestrators must decouple state checkpoints from process lifetimes.",
            post_excerpt="Discussion on orchestrator restart failure modes.",
        )

        assert len(service.voice_memory.writing_samples) == initial_len + 1
        ctx = service.voice_memory.get_voice_context("orchestrator state checkpoints")
        assert "decouple state checkpoints" in ctx["few_shot_examples"]
