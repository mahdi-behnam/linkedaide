"""Unit tests for deterministic anti-cliché guardrails and LLMService bounded repair."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from agent.config import Settings
from agent.llm.chains import LLMChains
from agent.llm.service import LLMService
from agent.models import (
    CommentDraft,
    PostIdea,
    PostIdeationContext,
    PostRecord,
    ReplyTriageResult,
    ThreadReplyItem,
    TriageResult,
)
from agent.safety.anti_cliche import (
    BANNED_BUZZWORDS,
    AntiClicheScanner,
)


@pytest.fixture
def scanner() -> AntiClicheScanner:
    """Fixture providing a default AntiClicheScanner instance."""
    return AntiClicheScanner()


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture providing mock settings."""
    return Settings(
        nvidia_nim_api_key="nvapi-mock-key-12345",
        nim_model_primary="nvidia/nemotron-3-super-120b-a12b",
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
    """Fixture providing a sample PostRecord."""
    return PostRecord(
        post_urn="urn:li:activity:7890123456",
        post_url="https://linkedin.com/feed/update/urn:li:activity:7890123456",
        author_name="Alice Engineer",
        post_text="Exploring the trade-offs of Raft vs Paxos in distributed state machines.",
        content_hash="mock_hash_123",
        scraped_at=datetime.now(UTC),
    )


class TestBannedOpeners:
    """Comprehensive test suite covering 15+ variations of banned AI openers."""

    BANNED_OPENER_SAMPLES: list[str] = [
        "In today's fast-paced world, distributed consensus is critical.",
        "In today's rapidly evolving tech landscape, developers must adapt.",
        "In today's modern world, reliable queues matter.",
        "In todays fast-paced world, speed is everything.",
        "In today’s rapidly evolving tech, systems change quickly.",
        "In today's modern landscape, microservices dominate.",
        "Great post! The points on latency are crucial.",
        "Great read on distributed systems and Paxos.",
        "Great share! Appreciate the detailed breakdown.",
        "Great article regarding database connection pools.",
        "Great insight on event loop scheduling.",
        "Great insights into Paxos vs Raft.",
        "Kudos! Really enjoyed the architecture breakdown.",
        "Spot on. Two-phase commits are difficult in production.",
        "100% this! Observability should never be an afterthought.",
        "Couldn't agree more with your perspective on microservices.",
        "Couldn’t agree more. Thread pools need careful tuning.",
        "Fascinating read on garbage collection overhead.",
        "Fascinating perspective on vector search indexing.",
        "Fascinating take on asynchronous event loops.",
        "Love this! The comparison benchmark is very useful.",
        "Thanks for sharing! We observed similar results with Redis.",
        "This is a game changer for local LLM inference pipelines.",
        "This is a game-changer in AI agent architecture.",
        "This is a must-read for distributed systems engineers.",
        "This is a must-read!",
    ]

    def test_banned_openers_count(self) -> None:
        """Verify we test at least 15 distinct banned opener variations."""
        assert len(self.BANNED_OPENER_SAMPLES) >= 15

    @pytest.mark.parametrize("opener_text", BANNED_OPENER_SAMPLES)
    def test_banned_openers_detected(self, scanner: AntiClicheScanner, opener_text: str) -> None:
        result = scanner.scan(opener_text)
        assert result.passed is False
        assert any("Banned AI opener" in v for v in result.violations)

    def test_banned_openers_with_leading_quotes_and_markdown(
        self, scanner: AntiClicheScanner
    ) -> None:
        quotes_sample = '"Great post! The latency difference is real."'
        result_quotes = scanner.scan(quotes_sample)
        assert result_quotes.passed is False
        assert any("Banned AI opener" in v for v in result_quotes.violations)

        md_sample = "**Great read** on cache invalidation strategies."
        result_md = scanner.scan(md_sample)
        assert result_md.passed is False
        assert any("Banned AI opener" in v for v in result_md.violations)


class TestBannedBuzzwords:
    """Test suite covering banned AI buzzwords detection and case-insensitivity."""

    BUZZWORD_CASES: list[tuple[str, str]] = [
        ("Let us delve into the memory model.", "delve"),
        ("This is a major game changer for serverless.", "game changer"),
        ("A true game-changer in distributed systems.", "game-changer"),
        ("The complex tapestry of microservices.", "tapestry"),
        ("A beacon of software reliability.", "beacon"),
        ("A testament to solid architectural design.", "testament"),
        ("We are witnessing a paradigm shift in computing.", "paradigm shift"),
        ("This tool will supercharge your daily workflow.", "supercharge"),
        ("We must harness the power of asynchronous I/O.", "harness the power"),
        ("A holistic approach to infrastructure.", "holistic approach"),
        ("Creating organizational synergies across teams.", "synergies"),
        ("In conclusion, the benchmark shows 2x improvement.", "in conclusion"),
        ("Furthermore, memory consumption dropped significantly.", "furthermore"),
        ("Moreover, network latency was reduced.", "moreover"),
        ("It's important to remember that network calls fail.", "it's important to remember"),
        ("It’s important to remember that timeouts matter.", "it's important to remember"),
        ("It is important to remember that disk I/O is slow.", "it's important to remember"),
        ("Replication plays a vital role in high availability.", "vital role"),
        ("A pivotal decision in database schema design.", "pivotal"),
        ("A groundbreaking benchmark on NVMe drives.", "groundbreaking"),
        ("It was an absolute pleasure to read this piece.", "pleasure to read"),
    ]

    def test_all_buzzwords_covered(self) -> None:
        """Verify that every buzzword in BANNED_BUZZWORDS is explicitly tested."""
        tested_buzzwords = {expected for _, expected in self.BUZZWORD_CASES}
        assert BANNED_BUZZWORDS.issubset(tested_buzzwords)

    @pytest.mark.parametrize(("text", "expected_buzzword"), BUZZWORD_CASES)
    def test_banned_buzzwords_detected(
        self, scanner: AntiClicheScanner, text: str, expected_buzzword: str
    ) -> None:
        result = scanner.scan(text)
        assert result.passed is False
        assert any(expected_buzzword in v.lower() for v in result.violations)

    def test_buzzwords_case_insensitivity(self, scanner: AntiClicheScanner) -> None:
        text = "We DELVE into this GAME CHANGER with a PARADIGM SHIFT."
        result = scanner.scan(text)
        assert result.passed is False
        violations_str = " ".join(result.violations).lower()
        assert "delve" in violations_str
        assert "game changer" in violations_str
        assert "paradigm shift" in violations_str


class TestStylometricLimits:
    """Test suite covering emoji limits, exclamation mark limits, and sycophantic first sentences."""

    def test_emoji_limits(self, scanner: AntiClicheScanner) -> None:
        # 0 emojis: pass
        res_0 = scanner.scan("Raft provides deterministic leader election.")
        assert not any("emoji" in v.lower() for v in res_0.violations)

        # 1 emoji: pass
        res_1 = scanner.scan("Raft provides deterministic leader election. 🚀")
        assert not any("emoji" in v.lower() for v in res_1.violations)

        # 2 emojis: fail
        res_2 = scanner.scan("Leader election succeeded 🚀 with zero downtime 🔥")
        assert res_2.passed is False
        assert any("emoji limit" in v.lower() for v in res_2.violations)

        # 3 emojis: fail
        res_3 = scanner.scan("High throughput 🚀 low latency 🔥 rock solid 💡")
        assert res_3.passed is False
        assert any("emoji limit" in v.lower() for v in res_3.violations)

    def test_compound_emoji_counted_as_one(self, scanner: AntiClicheScanner) -> None:
        # ZWJ emoji (e.g. technologist 👨‍💻 or skin tone modifier 👍🏽)
        res_zwj = scanner.scan("Engineers 👨‍💻 often tune garbage collector parameters.")
        assert not any("emoji" in v.lower() for v in res_zwj.violations)

    def test_exclamation_mark_limits(self, scanner: AntiClicheScanner) -> None:
        # 0 exclamations: pass
        res_0 = scanner.scan("LSM trees minimize write amplification.")
        assert not any("exclamation" in v.lower() for v in res_0.violations)

        # 1 exclamation: pass
        res_1 = scanner.scan("LSM trees minimize write amplification!")
        assert not any("exclamation" in v.lower() for v in res_1.violations)

        # 2 exclamations: fail
        res_2 = scanner.scan("LSM trees minimize write amplification! Throughput is incredible!")
        assert res_2.passed is False
        assert any("exclamation mark limit" in v.lower() for v in res_2.violations)

        # Multiple consecutive exclamations: fail
        res_mult = scanner.scan("Incredible results!!!")
        assert res_mult.passed is False
        assert any("exclamation mark limit" in v.lower() for v in res_mult.violations)

    def test_sycophantic_first_sentence_detection(self, scanner: AntiClicheScanner) -> None:
        sycophantic_examples = [
            "I completely agree with this analysis.",
            "Totally agree with your points.",
            "Well said! Clear breakdown.",
            "Nailed it! Exactly what happens in production.",
            "This is so true.",
            "Such an insightful post.",
            "Awesome read, totally agree!",
            "Agreed 100%.",
        ]
        for example in sycophantic_examples:
            result = scanner.scan(example)
            assert result.passed is False
            assert any("sycophantic" in v.lower() for v in result.violations)

    def test_technical_first_sentence_not_flagged_as_sycophantic(
        self, scanner: AntiClicheScanner
    ) -> None:
        technical_examples = [
            "Raft decomposes consensus into leader election and log replication.",
            "In our Redis deployment, we observed 25ms p99 latency spikes during snapshotting.",
            "Have you benchmarked throughput differences when write amplification increases?",
            "While event sourcing provides great auditability, it introduces schema migration overhead.",
            "Two-phase commit works well for small topologies, but falls apart at scale.",
            "We solved this exact bottleneck using ring buffers in shared memory.",
            "One trade-off not mentioned here is memory pressure under bursty workloads.",
        ]
        for example in technical_examples:
            result = scanner.scan(example)
            assert not any("sycophantic" in v.lower() for v in result.violations)


class TestCleanHumanWrittenComments:
    """Test suite ensuring high-signal technical comments pass all guardrails cleanly."""

    CLEAN_COMMENTS: list[str] = [
        (
            "The trade-off between write amplification and read latency in LSM-trees is often underestimated. "
            "Compaction storms can severely impact p99 response times unless rate limiting is applied to background flushes."
        ),
        (
            "Have you tested how this failover mechanism behaves during split-brain network partitions? "
            "In our benchmarks, partition tolerance required an odd number of voting replicas."
        ),
        (
            "While microservices offer organizational boundaries, the distributed tracing overhead "
            "and network serialization costs often negate performance gains for sub-10ms SLAs."
        ),
        (
            "Combining token bucket rate limiting with adaptive concurrency limits on client side "
            "gave us much better resilience against cascading backend failures."
        ),
        (
            "Curious about the memory overhead of maintaining this in-memory index under write-heavy loads. "
            "Did you profile GC pause times with large heap allocations?"
        ),
    ]

    @pytest.mark.parametrize("comment", CLEAN_COMMENTS)
    def test_clean_comments_pass_unmodified(self, scanner: AntiClicheScanner, comment: str) -> None:
        result = scanner.scan(comment)
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.cleaned_text == comment.strip()


class TestSanitization:
    """Test suite for deterministic anti-cliché sanitization."""

    def test_sanitize_strips_opener_and_preserves_technical_insight(
        self, scanner: AntiClicheScanner
    ) -> None:
        text = "Great post! The latency difference between Raft and Paxos is substantial."
        sanitized = scanner.sanitize(text)
        assert sanitized == "The latency difference between Raft and Paxos is substantial."
        # Sanitized text must pass the scanner
        assert scanner.scan(sanitized).passed is True

    def test_sanitize_trims_excessive_exclamation_marks(self, scanner: AntiClicheScanner) -> None:
        text = "Cache invalidation is hard! Really hard! Absolutely critical!"
        sanitized = scanner.sanitize(text)
        assert sanitized is not None
        assert sanitized.count("!") <= 1
        assert scanner.scan(sanitized).passed is True

    def test_sanitize_trims_excessive_emojis(self, scanner: AntiClicheScanner) -> None:
        text = "Throughput surged 🚀 and latency dropped 🔥 across all nodes 💡."
        sanitized = scanner.sanitize(text)
        assert sanitized is not None
        assert len(scanner.scan(sanitized).violations) == 0

    def test_sanitize_replaces_buzzwords(self, scanner: AntiClicheScanner) -> None:
        text = "Furthermore, we delve into caching to supercharge system performance."
        sanitized = scanner.sanitize(text)
        assert sanitized is not None
        assert "furthermore" not in sanitized.lower()
        assert "delve" not in sanitized.lower()
        assert "supercharge" not in sanitized.lower()
        assert scanner.scan(sanitized).passed is True

    def test_sanitize_pure_hollow_praise_returns_none(self, scanner: AntiClicheScanner) -> None:
        assert scanner.sanitize("Great post!") is None
        assert scanner.sanitize("100% this!") is None
        assert scanner.sanitize("   ") is None


class TestLLMServiceRepairLoop:
    """Test suite for LLMService anti-cliché scanning and bounded 1-turn repair integration."""

    def _create_mock_chains(self, comment_fn: Any) -> LLMChains:
        """Create mock chains with custom comment handler."""
        return LLMChains(
            triage=RunnableLambda(
                lambda x: TriageResult(
                    recommendation="comment",
                    confidence=0.95,
                    reasoning="High relevance to distributed systems.",
                )
            ),
            comment=RunnableLambda(comment_fn),
            post_idea=RunnableLambda(lambda x: None),
        )

    @pytest.mark.asyncio
    async def test_clean_draft_returns_immediately_without_repair(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        clean_comment = (
            "Raft simplifies consensus by decomposing leader election and log replication."
        )
        chains = self._create_mock_chains(
            lambda x: CommentDraft(
                draft_comment=clean_comment,
                topic_tags=["distributed-systems", "raft"],
            )
        )
        mock_repair_model = AsyncMock()
        service = LLMService(
            mock_settings,
            chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")

        draft = await service.draft_comment(sample_post, triage)
        assert draft.draft_comment == clean_comment
        # Verify repair model was never called
        mock_repair_model.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_violating_draft_triggers_single_repair_turn_success(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        # Primary chain returns a draft with a banned opener
        banned_comment = "Great post! Raft simplifies consensus by separating leader election."
        chains = self._create_mock_chains(
            lambda x: CommentDraft(
                draft_comment=banned_comment,
                topic_tags=["distributed-systems"],
            )
        )

        repaired_clean_comment = (
            "Raft simplifies consensus by separating leader election from log replication."
        )
        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.return_value = AIMessage(
            content=f'{{"draft_comment": "{repaired_clean_comment}", "topic_tags": ["raft"]}}'
        )

        service = LLMService(
            mock_settings,
            chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")

        draft = await service.draft_comment(sample_post, triage)
        assert draft.draft_comment == repaired_clean_comment
        # Verify exactly one repair turn occurred
        assert mock_repair_model.ainvoke.call_count == 1

        # Verify the prompt sent to the LLM matches the requested format
        call_args = mock_repair_model.ainvoke.call_args[0][0]
        human_msg = call_args[1].content
        assert "Your previous draft was rejected by the anti-cliché safety guardrail" in human_msg
        assert "Rewrite the comment strictly avoiding these phrases" in human_msg

    @pytest.mark.asyncio
    async def test_violating_draft_repaired_still_fails_sanitizes_deterministically(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        # Primary draft has banned opener
        banned_comment = "Great post! The throughput gain is 35% under write pressure."
        chains = self._create_mock_chains(
            lambda x: CommentDraft(
                draft_comment=banned_comment,
                topic_tags=["performance"],
            )
        )

        # Repaired draft still has a banned opener: "Kudos! The throughput gain is 35% under write pressure."
        still_violating = "Kudos! The throughput gain is 35% under write pressure."
        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.return_value = AIMessage(
            content=f'{{"draft_comment": "{still_violating}", "topic_tags": ["performance"]}}'
        )

        service = LLMService(
            mock_settings,
            chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")

        draft = await service.draft_comment(sample_post, triage)
        # Deterministic sanitization strips the opener
        assert "The throughput gain is 35% under write pressure." in draft.draft_comment
        assert "kudos" not in draft.draft_comment.lower()
        # Verify scanner passes on final draft
        assert service.anti_cliche_scanner.scan(draft.draft_comment).passed is True

    @pytest.mark.asyncio
    async def test_violating_draft_repair_throws_recovers_deterministically(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        # Primary draft has banned opener + buzzword
        banned_comment = "Great post! We examine how caching supercharges throughput."
        chains = self._create_mock_chains(
            lambda x: CommentDraft(
                draft_comment=banned_comment,
                topic_tags=["performance"],
            )
        )

        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.side_effect = RuntimeError("NIM connection timeout")

        service = LLMService(
            mock_settings,
            chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")

        draft = await service.draft_comment(sample_post, triage)
        assert service.anti_cliche_scanner.scan(draft.draft_comment).passed is True
        assert "great post" not in draft.draft_comment.lower()

    @pytest.mark.asyncio
    async def test_unsalvageable_hollow_draft_uses_clean_fallback(
        self, mock_settings: Settings, sample_post: PostRecord
    ) -> None:
        # Draft is only pure praise
        chains = self._create_mock_chains(
            lambda x: CommentDraft(
                draft_comment="Great post! 100% this!",
                topic_tags=[],
            )
        )

        mock_repair_model = AsyncMock()
        mock_repair_model.ainvoke.return_value = AIMessage(
            content='{"draft_comment": "Kudos! Love this!", "topic_tags": []}'
        )

        service = LLMService(
            mock_settings,
            chains=chains,
            repair_model=mock_repair_model,
            backoff_base=0.01,
        )
        triage = TriageResult(recommendation="comment", confidence=0.9, reasoning="Good post")

        draft = await service.draft_comment(sample_post, triage)
        # Should cleanly fallback to grounded technical comment
        assert service.anti_cliche_scanner.scan(draft.draft_comment).passed is True
        assert (
            "Alice Engineer" in draft.draft_comment
            or "architecture trade-offs" in draft.draft_comment
        )

    @pytest.mark.asyncio
    async def test_draft_post_idea_anti_cliche_sanitized(self, mock_settings: Settings) -> None:
        chains = LLMChains(
            triage=RunnableLambda(lambda x: None),
            comment=RunnableLambda(lambda x: None),
            post_idea=RunnableLambda(
                lambda x: PostIdea(
                    should_post=True,
                    headline="Distributed queues in production",
                    draft_post_text="In today's fast-paced world, building distributed queues requires attention to backpressure.",
                    hashtags=["systems"],
                    reasoning="Fresh angle",
                )
            ),
        )
        service = LLMService(mock_settings, chains=chains)
        context = PostIdeationContext(user_focus_areas=["Distributed Systems"])
        idea = await service.draft_post_idea(context)
        assert idea is not None
        assert "In today's fast-paced world" not in idea.draft_post_text
        assert (
            "Building distributed queues requires attention to backpressure."
            in idea.draft_post_text
        )
        assert service.anti_cliche_scanner.scan(idea.draft_post_text).passed is True

    @pytest.mark.asyncio
    async def test_draft_thread_reply_anti_cliche_sanitized(self, mock_settings: Settings) -> None:
        chains = LLMChains(
            triage=RunnableLambda(lambda x: None),
            comment=RunnableLambda(lambda x: None),
            post_idea=RunnableLambda(lambda x: None),
            thread_reply=RunnableLambda(
                lambda x: CommentDraft(
                    draft_comment="Great read! We benchmarked throughput under zipfian skew.",
                    topic_tags=["benchmarks"],
                )
            ),
        )
        service = LLMService(mock_settings, chains=chains)
        reply = ThreadReplyItem(
            reply_urn="urn:li:reply:1",
            parent_comment_urn="urn:li:comment:1",
            author_name="Alice Vance",
            reply_text="How did you measure contention?",
        )
        triage = ReplyTriageResult(
            recommendation="reply",
            confidence=0.95,
            reasoning="Technical question",
        )
        draft = await service.draft_thread_reply(
            reply=reply,
            our_comment="Our comment",
            original_post="Original post",
            triage=triage,
        )
        assert "great read" not in draft.draft_comment.lower()
        assert "We benchmarked throughput under zipfian skew." in draft.draft_comment
        assert service.anti_cliche_scanner.scan(draft.draft_comment).passed is True
