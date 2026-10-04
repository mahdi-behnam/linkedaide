"""Unit tests for multimodal vision analysis, DOM media scraping, and diagram-grounded drafting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from agent.browser.scraper import FeedScraper
from agent.config import Settings
from agent.llm.chains import LLMChains
from agent.llm.multimodal import MultimodalAnalyzer, format_visual_evidence
from agent.llm.prompts import build_comment_prompt
from agent.llm.service import LLMService
from agent.models import (
    CommentDraft,
    EngagementStyle,
    PostRecord,
    ScrapedPost,
    ScrapedPostCard,
    TriageResult,
    VisualContext,
)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123456:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["Distributed Systems", "AI Agents", "Python"],
        max_suggestions_per_run=3,
        max_comment_words=80,
    )


# ==============================================================================
# 1. Scraper Extraction of Media, Image URLs, and Carousel Indicators
# ==============================================================================


@pytest.mark.asyncio
async def test_scraper_extracts_standalone_image_url(
    test_settings: Settings, tmp_path: Path
) -> None:
    """FeedScraper should extract high-resolution image URL from image elements."""
    page = MagicMock()
    scraper = FeedScraper(page, test_settings, debug_dir=tmp_path)

    card = MagicMock()
    img_element = MagicMock()
    img_element.count = AsyncMock(return_value=1)
    img_element.get_attribute = AsyncMock(
        side_effect=lambda attr: {
            "src": "https://media.licdn.com/dms/image/v2/high_res_arch.jpg",
            "data-delayed-url": None,
            "data-src": None,
        }.get(attr)
    )

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if ".update-components-image__image" in selector:
            loc.first = img_element
            loc.count = AsyncMock(return_value=1)
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    card.locator = MagicMock(side_effect=locator_mock)

    image_url, media_type = await scraper.extract_media_from_card(card)
    assert image_url == "https://media.licdn.com/dms/image/v2/high_res_arch.jpg"
    assert media_type == "image"


@pytest.mark.asyncio
async def test_scraper_prefers_data_delayed_url_over_placeholder(
    test_settings: Settings, tmp_path: Path
) -> None:
    """FeedScraper prefers real CDN delayed URL if src is a placeholder data URI."""
    page = MagicMock()
    scraper = FeedScraper(page, test_settings, debug_dir=tmp_path)

    card = MagicMock()
    img_element = MagicMock()
    img_element.count = AsyncMock(return_value=1)
    img_element.get_attribute = AsyncMock(
        side_effect=lambda attr: {
            "src": "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
            "data-delayed-url": "https://media.licdn.com/dms/image/real_diagram.png",
            "data-src": None,
        }.get(attr)
    )

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if "feed-shared-image" in selector:
            loc.first = img_element
            loc.count = AsyncMock(return_value=1)
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    card.locator = MagicMock(side_effect=locator_mock)

    image_url, media_type = await scraper.extract_media_from_card(card)
    assert image_url == "https://media.licdn.com/dms/image/real_diagram.png"
    assert media_type == "image"


@pytest.mark.asyncio
async def test_scraper_detects_carousel_and_slide_image(
    test_settings: Settings, tmp_path: Path
) -> None:
    """FeedScraper should identify carousel slide elements and extract the slide image."""
    page = MagicMock()
    scraper = FeedScraper(page, test_settings, debug_dir=tmp_path)

    card = MagicMock()
    carousel_element = MagicMock()
    carousel_element.count = AsyncMock(return_value=1)

    slide_img = MagicMock()
    slide_img.count = AsyncMock(return_value=1)
    slide_img.get_attribute = AsyncMock(
        side_effect=lambda attr: {
            "src": "https://media.licdn.com/dms/image/carousel_slide_1.png",
            "data-delayed-url": None,
        }.get(attr)
    )

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if ".feed-shared-carousel" in selector:
            loc.first = carousel_element
            loc.count = AsyncMock(return_value=1)
        elif ".update-components-image__image" in selector:
            loc.first = slide_img
            loc.count = AsyncMock(return_value=1)
        elif "carousel img" in selector:
            loc.first = slide_img
            loc.count = AsyncMock(return_value=1)
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    card.locator = MagicMock(side_effect=locator_mock)

    image_url, media_type = await scraper.extract_media_from_card(card)
    assert media_type == "carousel"
    assert image_url == "https://media.licdn.com/dms/image/carousel_slide_1.png"


@pytest.mark.asyncio
async def test_scraper_detects_document_preview(test_settings: Settings, tmp_path: Path) -> None:
    """FeedScraper should identify document preview elements and extract preview image."""
    page = MagicMock()
    scraper = FeedScraper(page, test_settings, debug_dir=tmp_path)

    card = MagicMock()
    doc_element = MagicMock()
    doc_element.count = AsyncMock(return_value=1)

    doc_img = MagicMock()
    doc_img.count = AsyncMock(return_value=1)
    doc_img.get_attribute = AsyncMock(
        side_effect=lambda attr: {
            "src": "https://media.licdn.com/dms/image/doc_preview.png",
            "data-delayed-url": None,
        }.get(attr)
    )

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if ".feed-shared-document-preview img" in selector:
            loc.first = doc_img
            loc.count = AsyncMock(return_value=1)
        elif ".feed-shared-document-preview" in selector:
            loc.first = doc_element
            loc.count = AsyncMock(return_value=1)
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    card.locator = MagicMock(side_effect=locator_mock)

    image_url, media_type = await scraper.extract_media_from_card(card)
    assert media_type == "document"
    assert image_url == "https://media.licdn.com/dms/image/doc_preview.png"


@pytest.mark.asyncio
async def test_scraper_no_media_returns_none(test_settings: Settings, tmp_path: Path) -> None:
    """FeedScraper should return (None, None) for posts without media."""
    page = MagicMock()
    scraper = FeedScraper(page, test_settings, debug_dir=tmp_path)

    card = MagicMock()
    loc = MagicMock()
    loc.first = MagicMock(count=AsyncMock(return_value=0))
    loc.count = AsyncMock(return_value=0)
    card.locator = MagicMock(return_value=loc)

    image_url, media_type = await scraper.extract_media_from_card(card)
    assert image_url is None
    assert media_type is None


# ==============================================================================
# 2. MultimodalAnalyzer Classification and Component Extraction
# ==============================================================================


@pytest.mark.asyncio
async def test_multimodal_analyzer_empty_image_url_returns_default(test_settings: Settings) -> None:
    """MultimodalAnalyzer returns empty VisualContext when image_url is missing."""
    analyzer = MultimodalAnalyzer(test_settings)
    post = PostRecord(
        post_urn="urn:li:activity:1",
        post_url="https://linkedin.com/1",
        author_name="Alice",
        post_text="Text only post about algorithms.",
        content_hash="hash1",
        image_url=None,
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is False
    assert result.diagram_type == "photo_or_other"
    assert result.key_components == []
    assert result.visual_summary == ""


@pytest.mark.asyncio
async def test_multimodal_analyzer_heuristic_architecture_diagram(test_settings: Settings) -> None:
    """Heuristic fallback identifies architecture diagrams and extracts known components."""
    analyzer = MultimodalAnalyzer(test_settings, vision_model=None)
    post = ScrapedPost(
        post_urn="urn:li:activity:2",
        post_url="https://linkedin.com/2",
        author_name="Bob Engineer",
        post_text=(
            "Here is our production distributed architecture topology showing async replication "
            "between Kafka, Postgres, and Redis cache across a dynamic worker pool."
        ),
        content_hash="hash2",
        image_url="https://media.licdn.com/dms/image/arch_diagram.png",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is True
    assert result.diagram_type == "architecture"
    assert "Kafka" in result.key_components
    assert "Postgres" in result.key_components
    assert "Redis cache" in result.key_components
    assert "Worker pool" in result.key_components
    assert "architecture" in result.visual_summary.lower()


@pytest.mark.asyncio
async def test_multimodal_analyzer_heuristic_benchmark_chart(test_settings: Settings) -> None:
    """Heuristic fallback identifies benchmark and latency performance charts."""
    analyzer = MultimodalAnalyzer(test_settings, vision_model=None)
    post = ScrapedPostCard(
        post_urn="urn:li:activity:3",
        post_url="https://linkedin.com/3",
        author_name="Carol Systems",
        post_text=(
            "Benchmark comparison chart illustrating p99 latency and throughput speedup with FastAPI and Go."
        ),
        content_hash="hash3",
        image_url="https://media.licdn.com/dms/image/benchmark_results.png",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is True
    assert result.diagram_type == "benchmark_chart"
    assert "FastAPI" in result.key_components
    assert "Go" in result.key_components
    assert (
        "latency" in result.visual_summary.lower() or "benchmark" in result.visual_summary.lower()
    )


@pytest.mark.asyncio
async def test_multimodal_analyzer_heuristic_code_snippet(test_settings: Settings) -> None:
    """Heuristic fallback identifies code screenshots and snippets."""
    analyzer = MultimodalAnalyzer(test_settings, vision_model=None)
    post = PostRecord(
        post_urn="urn:li:activity:4",
        post_url="https://linkedin.com/4",
        author_name="Dave Dev",
        post_text="Clean code snippet showing async def pipeline in Python.",
        content_hash="hash4",
        image_url="https://media.licdn.com/dms/image/code_screenshot.png",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is True
    assert result.diagram_type == "code_snippet"
    assert "Python" in result.key_components


@pytest.mark.asyncio
async def test_multimodal_analyzer_heuristic_photo_or_other(test_settings: Settings) -> None:
    """Heuristic fallback correctly treats non-technical photos as photo_or_other."""
    analyzer = MultimodalAnalyzer(test_settings, vision_model=None)
    post = PostRecord(
        post_urn="urn:li:activity:5",
        post_url="https://linkedin.com/5",
        author_name="Eve Marketer",
        post_text="Had a wonderful coffee chat today at the company picnic!",
        content_hash="hash5",
        image_url="https://media.licdn.com/dms/image/picnic_selfie.jpg",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is False
    assert result.diagram_type == "photo_or_other"
    assert result.key_components == []
    assert result.visual_summary == ""


@pytest.mark.asyncio
async def test_multimodal_analyzer_with_mock_vision_model(test_settings: Settings) -> None:
    """MultimodalAnalyzer properly parses structured output from a vision-capable model."""
    mock_model = MagicMock()
    expected_vc = VisualContext(
        has_diagram=True,
        diagram_type="architecture",
        key_components=["Kafka", "Postgres", "Redis cache", "Worker pool"],
        visual_summary="Distributed cache topology showing async replication across regions",
    )

    # Mock structured output
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=expected_vc)
    mock_model.with_structured_output.return_value = mock_structured

    analyzer = MultimodalAnalyzer(test_settings, vision_model=mock_model)
    post = PostRecord(
        post_urn="urn:li:activity:6",
        post_url="https://linkedin.com/6",
        author_name="Frank Architect",
        post_text="New architecture blueprint.",
        content_hash="hash6",
        image_url="https://media.licdn.com/dms/image/blueprint.png",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is True
    assert result.diagram_type == "architecture"
    assert result.key_components == ["Kafka", "Postgres", "Redis cache", "Worker pool"]
    assert (
        result.visual_summary
        == "Distributed cache topology showing async replication across regions"
    )


@pytest.mark.asyncio
async def test_multimodal_analyzer_vision_model_json_fallback(test_settings: Settings) -> None:
    """MultimodalAnalyzer parses JSON string from model response if structured output is not used."""
    mock_model = MagicMock()
    # No with_structured_output attribute
    del mock_model.with_structured_output
    json_response = """```json
    {
        "has_diagram": true,
        "diagram_type": "benchmark_chart",
        "key_components": ["Kafka", "Flink"],
        "visual_summary": "Streaming throughput metrics"
    }
    ```"""
    mock_model.ainvoke = AsyncMock(return_value=AIMessage(content=json_response))

    analyzer = MultimodalAnalyzer(test_settings, vision_model=mock_model)
    post = PostRecord(
        post_urn="urn:li:activity:7",
        post_url="https://linkedin.com/7",
        author_name="Grace Data",
        post_text="Streaming benchmark results.",
        content_hash="hash7",
        image_url="https://media.licdn.com/dms/image/stream_chart.png",
    )

    result = await analyzer.analyze(post)
    assert result.has_diagram is True
    assert result.diagram_type == "benchmark_chart"
    assert result.key_components == ["Kafka", "Flink"]
    assert result.visual_summary == "Streaming throughput metrics"


@pytest.mark.asyncio
async def test_multimodal_analyzer_failure_falls_back_to_heuristic(test_settings: Settings) -> None:
    """MultimodalAnalyzer falls back to heuristic if the vision model call throws an exception."""
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(side_effect=RuntimeError("API quota exceeded"))
    if hasattr(mock_model, "with_structured_output"):
        mock_model.with_structured_output.side_effect = RuntimeError("API quota exceeded")

    analyzer = MultimodalAnalyzer(test_settings, vision_model=mock_model)
    post = PostRecord(
        post_urn="urn:li:activity:8",
        post_url="https://linkedin.com/8",
        author_name="Henry Infra",
        post_text="System design flowchart featuring Kubernetes, Docker, and Nginx gateway.",
        content_hash="hash8",
        image_url="https://media.licdn.com/dms/image/k8s_flow.png",
    )

    result = await analyzer.analyze(post)
    # Should safely fallback to heuristic without crashing
    assert result.has_diagram is True
    assert result.diagram_type == "architecture"
    assert "Kubernetes" in result.key_components
    assert "Docker" in result.key_components


# ==============================================================================
# 3. Drafting Grounding: Visual Evidence Injection & Prompt Formatting
# ==============================================================================


def test_format_visual_evidence_helper() -> None:
    """format_visual_evidence should produce structured prompt text when diagram is present."""
    assert format_visual_evidence(None) == ""

    no_diagram_vc = VisualContext(has_diagram=False, diagram_type="photo_or_other")
    assert format_visual_evidence(no_diagram_vc) == ""

    vc = VisualContext(
        has_diagram=True,
        diagram_type="architecture",
        key_components=["Kafka", "Postgres", "Redis cache", "Worker pool"],
        visual_summary="Distributed cache topology showing async replication across regions",
    )
    formatted = format_visual_evidence(vc)
    assert "Visual Evidence (Architecture Diagram):" in formatted
    assert "Distributed cache topology showing async replication across regions" in formatted
    assert "Kafka, Postgres, Redis cache, Worker pool" in formatted
    assert "Grounding Requirement:" in formatted


def test_comment_prompt_rendering_with_visual_evidence() -> None:
    """build_comment_prompt renders with visual_evidence when provided, and defaults gracefully."""
    prompt = build_comment_prompt()

    # 1. With visual evidence
    evidence = "Visual Evidence (Architecture Diagram):\n- Summary: Kafka to Redis replication"
    messages = prompt.format_messages(
        max_words=80,
        author_name="Ivan",
        post_url="https://linkedin.com/9",
        post_text="Check out our system architecture.",
        triage_reasoning="High engineering value.",
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE.value,
        visual_evidence=evidence,
    )
    assert len(messages) == 2
    assert "Grounded in Context" in messages[0].content
    assert "When visual evidence or a diagram is provided" in messages[0].content
    assert evidence in messages[1].content

    # 2. Without visual evidence (defaults to empty string)
    messages_no_ev = prompt.format_messages(
        max_words=80,
        author_name="Ivan",
        post_url="https://linkedin.com/9",
        post_text="Check out our system architecture.",
        triage_reasoning="High engineering value.",
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE.value,
    )
    assert len(messages_no_ev) == 2
    assert "Ivan" in messages_no_ev[1].content


@pytest.mark.asyncio
async def test_llm_service_draft_comment_injects_visual_evidence(test_settings: Settings) -> None:
    """LLMService.draft_comment should format and inject visual evidence into chain inputs."""
    mock_comment_chain = MagicMock()
    mock_comment_draft = CommentDraft(
        draft_comment=(
            "The asynchronous replication between Kafka and Redis cache in this topology "
            "effectively decouples ingestion from query latency, though worker pool failover needs fencing."
        ),
        topic_tags=["distributed-systems", "kafka", "redis"],
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )
    mock_comment_chain.ainvoke = AsyncMock(return_value=mock_comment_draft)

    chains = LLMChains(
        triage=MagicMock(),
        comment=mock_comment_chain,
        post_idea=MagicMock(),
    )

    service = LLMService(test_settings, chains=chains)

    vc = VisualContext(
        has_diagram=True,
        diagram_type="architecture",
        key_components=["Kafka", "Postgres", "Redis cache", "Worker pool"],
        visual_summary="Distributed cache topology showing async replication across regions",
    )
    post = PostRecord(
        post_urn="urn:li:activity:10",
        post_url="https://linkedin.com/10",
        author_name="Julia Cloud",
        post_text="Architecture overview of our real-time processing stack.",
        content_hash="hash10",
        image_url="https://media.licdn.com/dms/image/realtime_stack.png",
        visual_context=vc,
    )
    triage = TriageResult(
        recommendation="comment",
        confidence=0.95,
        reasoning="Substantive architecture post.",
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )

    draft = await service.draft_comment(post, triage, visual_context=vc)

    assert draft.draft_comment == mock_comment_draft.draft_comment
    assert mock_comment_chain.ainvoke.called

    call_arg = mock_comment_chain.ainvoke.call_args[0][0]
    assert "visual_evidence" in call_arg
    assert "Visual Evidence (Architecture Diagram):" in call_arg["visual_evidence"]
    assert "Kafka, Postgres, Redis cache, Worker pool" in call_arg["visual_evidence"]
    assert "Grounding Requirement:" in call_arg["visual_evidence"]


@pytest.mark.asyncio
async def test_llm_service_draft_comment_auto_analyzes_image_if_visual_context_unset(
    test_settings: Settings,
) -> None:
    """When visual_context is not pre-set on post, draft_comment invokes MultimodalAnalyzer."""
    mock_analyzer = MagicMock()
    mock_vc = VisualContext(
        has_diagram=True,
        diagram_type="architecture",
        key_components=["Kafka", "Postgres"],
        visual_summary="Data pipeline topology",
    )
    mock_analyzer.analyze = AsyncMock(return_value=mock_vc)

    mock_comment_chain = MagicMock()
    mock_comment_draft = CommentDraft(
        draft_comment="The pipeline topology nicely isolates the Postgres ingestion tier.",
        topic_tags=["postgres", "pipeline"],
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )
    mock_comment_chain.ainvoke = AsyncMock(return_value=mock_comment_draft)

    chains = LLMChains(
        triage=MagicMock(),
        comment=mock_comment_chain,
        post_idea=MagicMock(),
    )

    service = LLMService(test_settings, chains=chains, multimodal_analyzer=mock_analyzer)

    post = PostRecord(
        post_urn="urn:li:activity:11",
        post_url="https://linkedin.com/11",
        author_name="Kevin Architect",
        post_text="Pipeline architecture with Postgres and Kafka.",
        content_hash="hash11",
        image_url="https://media.licdn.com/dms/image/pipeline.png",
        visual_context=None,
    )
    triage = TriageResult(
        recommendation="comment",
        confidence=0.9,
        reasoning="Good architecture post.",
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )

    draft = await service.draft_comment(post, triage)
    assert mock_analyzer.analyze.called
    assert post.visual_context == mock_vc
    assert draft.draft_comment == mock_comment_draft.draft_comment

    call_arg = mock_comment_chain.ainvoke.call_args[0][0]
    assert "Visual Evidence (Architecture Diagram):" in call_arg["visual_evidence"]
    assert "Kafka, Postgres" in call_arg["visual_evidence"]


def test_multimodal_analyzer_initializes_nvidia_nim_vision_model(test_settings: Settings) -> None:
    """MultimodalAnalyzer initializes ChatNVIDIA vision model when nvidia_nim_api_key is set."""
    with patch("agent.llm.models.ChatNVIDIA") as mock_chat_nvidia:
        analyzer = MultimodalAnalyzer(test_settings)
        assert analyzer._vision_model is not None
        mock_chat_nvidia.assert_called_once_with(
            model=test_settings.nim_model_vision,
            nvidia_api_key="nvapi-test",
            temperature=0.1,
        )
