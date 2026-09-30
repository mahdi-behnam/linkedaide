"""Multimodal Vision Analysis for Diagrams, Infographics, and Code Screenshots.

Architecture Invariants:
- Inspects post media (image, carousel slide, document preview).
- Invokes vision-capable model (Gemini 2.0 Flash, GPT-4o, Claude 3.5) if API key is configured.
- Gracefully falls back to local heuristic analysis when no vision API key is configured or on failure.
- Returns validated VisualContext Pydantic domain models.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import Settings
from agent.llm.models import build_chat_model
from agent.models import PostRecord, VisualContext

logger = logging.getLogger(__name__)

VISION_ANALYSIS_SYSTEM_PROMPT = """You are an expert multimodal AI specialized in analyzing technical architecture diagrams, system designs, benchmark charts, code screenshots, and infographics in software engineering posts.

Your task:
Analyze the provided image and extract structured technical visual context.

Output Requirements:
Return a JSON object conforming to:
- has_diagram (bool): true if the image contains a technical diagram, architecture layout, benchmark chart, code snippet, or technical infographic; false if it is a general photo, selfie, marketing meme, or non-technical image.
- diagram_type (string): exactly one of "architecture", "benchmark_chart", "code_snippet", "infographic", "photo_or_other".
- key_components (list of strings): list of 2 to 8 prominent subsystems, services, components, libraries, or metrics clearly visible (e.g. ["Kafka", "Postgres", "Redis cache", "Worker pool"]).
- visual_summary (string): concise, 1-2 sentence description of what is visually depicted and the relationship/data flow between components.
"""

KNOWN_TECH_COMPONENTS = [
    "Kafka",
    "Postgres",
    "Redis cache",
    "Redis",
    "Worker pool",
    "Kubernetes",
    "Docker",
    "FastAPI",
    "Go",
    "Python",
    "Rust",
    "gRPC",
    "GraphQL",
    "RabbitMQ",
    "Elasticsearch",
    "Cassandra",
    "MongoDB",
    "DynamoDB",
    "S3",
    "Cloudflare",
    "Nginx",
    "Envoy",
    "Prometheus",
    "Grafana",
    "Celery",
    "Temporal",
    "Flink",
    "Spark",
]


def format_visual_evidence(visual_context: VisualContext | None) -> str:
    """Format structured VisualContext into a prompt-ready visual evidence string.

    Returns empty string if visual_context is None or has_diagram is False.
    """
    if not visual_context or not visual_context.has_diagram:
        return ""

    diagram_name = visual_context.diagram_type.replace("_", " ").title()
    lines = [
        f"\nVisual Evidence ({diagram_name} Diagram):",
        f"- Summary: {visual_context.visual_summary}",
    ]
    if visual_context.key_components:
        lines.append(f"- Key Visual Components: {', '.join(visual_context.key_components)}")
    lines.append(
        "- Grounding Requirement: Explicitly ground your technical observation in these specific visual elements "
        "(e.g. referencing specific boxes, connecting arrows, data boundaries, or latency/benchmark metrics from the diagram)."
    )
    return "\n".join(lines) + "\n"


class MultimodalAnalyzer:
    """Analyzes images in LinkedIn posts for architecture diagrams, charts, and code snippets."""

    def __init__(self, settings: Settings, vision_model: Any | None = None) -> None:
        self._settings = settings
        self._vision_model = vision_model
        if self._vision_model is None:
            self._vision_model = self._init_vision_model(settings)

    def _init_vision_model(self, settings: Settings) -> Any | None:
        """Initialize a vision-capable chat model based on configured API keys."""
        # 1. Google Gemini (primary preference: gemini-2.0-flash)
        if settings.gemini_api_key:
            try:
                from agent.llm.models import ChatGoogleGenerativeAI

                if ChatGoogleGenerativeAI is not None:
                    api_key = settings.gemini_api_key
                    key_str = (
                        api_key.get_secret_value()
                        if hasattr(api_key, "get_secret_value")
                        else str(api_key)
                    )
                    return ChatGoogleGenerativeAI(
                        model="gemini-2.0-flash",
                        google_api_key=key_str,
                        temperature=0.1,
                    )
            except Exception as e:
                logger.debug("Failed initializing Gemini vision model: %s", e)

        # 2. OpenAI (gpt-4o)
        if settings.openai_api_key:
            try:
                from agent.llm.models import ChatOpenAI

                if ChatOpenAI is not None:
                    api_key = settings.openai_api_key
                    key_str = (
                        api_key.get_secret_value()
                        if hasattr(api_key, "get_secret_value")
                        else str(api_key)
                    )
                    return ChatOpenAI(
                        model="gpt-4o",
                        api_key=key_str,
                        temperature=0.1,
                    )
            except Exception as e:
                logger.debug("Failed initializing OpenAI vision model: %s", e)

        # 3. Anthropic (claude-3-5-sonnet-latest)
        if settings.anthropic_api_key:
            try:
                from agent.llm.models import ChatAnthropic

                if ChatAnthropic is not None:
                    api_key = settings.anthropic_api_key
                    key_str = (
                        api_key.get_secret_value()
                        if hasattr(api_key, "get_secret_value")
                        else str(api_key)
                    )
                    return ChatAnthropic(
                        model="claude-3-5-sonnet-latest",
                        api_key=key_str,
                        temperature=0.1,
                    )
            except Exception as e:
                logger.debug("Failed initializing Anthropic vision model: %s", e)

        # 4. Check if LLM provider is configured with fallback or primary
        if settings.llm_provider in ("openai", "gemini", "anthropic"):
            try:
                return build_chat_model(settings, role="generation")
            except Exception as e:
                logger.debug("Failed initializing provider chat model for vision: %s", e)

        logger.info(
            "No vision API key configured. MultimodalAnalyzer will use local heuristic fallback."
        )
        return None

    async def analyze(self, post: PostRecord) -> VisualContext:
        """Inspect scraped post and extract structured visual context."""
        image_url = (post.image_url or "").strip()
        if not image_url:
            return VisualContext(
                has_diagram=False,
                diagram_type="photo_or_other",
                key_components=[],
                visual_summary="",
            )

        # If a vision model is available, attempt remote multimodal analysis
        if self._vision_model is not None:
            try:
                return await self._analyze_with_model(post, image_url)
            except Exception as err:
                logger.warning(
                    "Vision model analysis failed for post %s (%s). Falling back to heuristic analysis.",
                    post.post_urn,
                    err,
                )

        # Local deterministic heuristic fallback
        return self._heuristic_fallback(post)

    async def analyze_card(self, card: PostRecord) -> VisualContext:
        """Alias for analyze accepting ScrapedPostCard."""
        return await self.analyze(card)

    async def _analyze_with_model(self, post: PostRecord, image_url: str) -> VisualContext:
        """Invoke vision model with multimodal user prompt and structured output extraction."""
        messages = [
            SystemMessage(content=VISION_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            f"Post Author: {post.author_name}\n"
                            f'Post Text: """{post.post_text}"""\n\n'
                            "Analyze the attached image and return structured visual context JSON."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ]
            ),
        ]

        # Try structured output first if supported
        if hasattr(self._vision_model, "with_structured_output"):
            try:
                structured_model = self._vision_model.with_structured_output(VisualContext)
                res = await structured_model.ainvoke(messages)
                if isinstance(res, VisualContext):
                    return res
                if isinstance(res, dict):
                    return VisualContext.model_validate(res)
            except Exception as struct_err:
                logger.debug("with_structured_output failed in vision model: %s", struct_err)

        # Fallback to direct invocation and JSON parsing
        response = await self._vision_model.ainvoke(messages)
        if isinstance(response, VisualContext):
            return response
        if isinstance(response, dict):
            return VisualContext.model_validate(response)

        raw_text = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw_text, list):
            raw_text = " ".join(str(p) for p in raw_text)

        cleaned = str(raw_text).strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        elif not (cleaned.startswith("{") and cleaned.endswith("}")):
            json_match = re.search(r"(\{[\s\S]*\})", cleaned)
            if json_match:
                cleaned = json_match.group(1).strip()

        parsed = json.loads(cleaned)
        return VisualContext.model_validate(parsed)

    def _heuristic_fallback(self, post: PostRecord) -> VisualContext:
        """Local heuristic classification and component extraction when no vision API is configured."""
        text = (post.post_text or "").lower()
        url = (post.image_url or "").lower()
        media_type = (post.media_type or "").lower()

        # Dedicated code snippet indicators
        code_specific = ["code snippet", "code screenshot", "syntax highlight", "clean code"]

        # Architecture keywords
        arch_markers = [
            "architecture",
            "system design",
            "microservice",
            "distributed",
            "topology",
            "pipeline",
            "infra",
            "aws",
            "gcp",
            "azure",
            "kubernetes",
            "k8s",
            "kafka",
            "redis",
            "postgres",
            "database",
            "cache",
            "load balancer",
            "worker pool",
            "flowchart",
            "diagram",
            "event-driven",
        ]

        # Benchmark/chart keywords
        chart_markers = [
            "benchmark",
            "latency",
            "throughput",
            "qps",
            "rps",
            "p99",
            "p95",
            "chart",
            "graph",
            "performance",
            "speedup",
            "results",
            "comparison",
        ]

        # General code syntax markers
        code_markers = [
            "def ",
            "class ",
            "async def",
            "function",
            "github.com",
            "typescript",
            "python",
            "golang",
            "rust",
            "npm install",
            "pip install",
            "repo",
        ]

        # Infographic / Carousel markers
        infographic_markers = [
            "infographic",
            "cheatsheet",
            "cheat sheet",
            "roadmap",
            "guide",
            "overview",
            "summary card",
        ]

        # Extract known components mentioned in post text
        components: list[str] = []
        for comp in KNOWN_TECH_COMPONENTS:
            pattern = rf"\b{re.escape(comp.lower())}\b"
            if re.search(pattern, text):
                if comp not in components:
                    components.append(comp)

        # Deduplicate and sort components nicely
        if "Redis cache" in components and "Redis" in components:
            components.remove("Redis")

        # Classify diagram type
        if any(marker in text or marker in url for marker in code_specific):
            diagram_type = "code_snippet"
            has_diagram = True
            visual_summary = (
                "Code snippet demonstrating implementation logic and technical patterns"
            )
        elif any(marker in text or marker in url for marker in arch_markers):
            diagram_type = "architecture"
            has_diagram = True
            comp_str = ", ".join(components[:4]) if components else "distributed services"
            visual_summary = f"Architecture layout depicting interaction between {comp_str}"
        elif any(marker in text or marker in url for marker in chart_markers):
            diagram_type = "benchmark_chart"
            has_diagram = True
            metric_str = (
                "latency and throughput metrics"
                if "latency" in text
                else "performance benchmark results"
            )
            visual_summary = f"Benchmark comparison chart illustrating {metric_str}"
        elif any(marker in text or marker in url for marker in code_markers):
            diagram_type = "code_snippet"
            has_diagram = True
            visual_summary = (
                "Code snippet demonstrating implementation logic and technical patterns"
            )
        elif any(
            marker in text or marker in url for marker in infographic_markers
        ) or media_type in (
            "carousel",
            "document",
        ):
            diagram_type = "infographic"
            has_diagram = True
            visual_summary = (
                f"Technical infographic/slide deck illustrating key engineering principles: {', '.join(components[:3])}"
                if components
                else "Technical infographic summarizing engineering workflow and best practices"
            )
        else:
            diagram_type = "photo_or_other"
            has_diagram = False
            visual_summary = ""
            components = []

        return VisualContext(
            has_diagram=has_diagram,
            diagram_type=diagram_type,  # type: ignore[arg-type]
            key_components=components[:6],
            visual_summary=visual_summary,
        )


__all__ = [
    "KNOWN_TECH_COMPONENTS",
    "MultimodalAnalyzer",
    "format_visual_evidence",
]
