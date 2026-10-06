"""Browser domain models for post cards, media attachments, and execution results.

Architecture Invariants:
- Scraped posts and browser execution results are typed Pydantic models.
- Browser layer produces these models and passes them across system boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VisualContext(BaseModel):
    """Structured visual context extracted from an image or diagram in a LinkedIn post."""

    model_config = ConfigDict(extra="ignore")

    has_diagram: bool = Field(
        default=False,
        description="Whether the image contains a technical diagram, chart, infographic, or code snippet",
    )
    diagram_type: Literal[
        "architecture",
        "benchmark_chart",
        "code_snippet",
        "infographic",
        "photo_or_other",
    ] = Field(
        default="photo_or_other",
        description="Classification of the visual content",
    )
    key_components: list[str] = Field(
        default_factory=list,
        description="Key components, systems, services, metrics, or entities identified in the visual",
    )
    visual_summary: str = Field(
        default="",
        description="Concise description or summary of what is visually depicted",
    )


class PostRecord(BaseModel):
    """Scraped feed post record used for deduplication and triage."""

    model_config = ConfigDict(extra="ignore")

    post_urn: str = Field(description="Unique LinkedIn post URN")
    post_url: str = Field(description="URL to the post")
    author_name: str = Field(description="Author name")
    author_profile_url: str | None = Field(
        default=None,
        description="Direct URL to author LinkedIn profile if extractable from card",
    )
    post_text: str = Field(description="Full text content of the post")
    content_hash: str = Field(description="SHA-256 hash of normalized post text")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when post was scraped",
    )
    image_url: str | None = Field(
        default=None,
        description="URL of primary attached media image, diagram, or carousel slide",
    )
    media_type: str | None = Field(
        default=None,
        description="Detected media type (e.g. 'image', 'carousel', 'document', 'video')",
    )
    visual_context: VisualContext | None = Field(
        default=None,
        description="Structured multimodal visual context extracted from attached media",
    )


# Aliases for flexible domain referencing
ScrapedPost = PostRecord
ScrapedPostCard = PostRecord


class ExecutionResult(BaseModel):
    """Result of a Playwright LinkedIn write execution."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(description="Whether the browser write succeeded and was DOM-verified")
    action_type: str = Field(
        description="Executed action type (e.g. approve_comment, approve_post)"
    )
    item_id: str = Field(description="Item identifier")
    post_url: str | None = Field(default=None, description="Target post URL if commenting")
    comment_text: str | None = Field(default=None, description="Submitted comment text")
    post_text: str | None = Field(default=None, description="Submitted original post text")
    comment_url: str | None = Field(
        default=None, description="Direct URL to newly posted comment with anchor/URN if available"
    )
    published_post_url: str | None = Field(
        default=None, description="Direct URL to newly published post if available"
    )
    screenshot_path: str | None = Field(
        default=None, description="Path to execution verification screenshot"
    )
    error: str | None = Field(default=None, description="Error details if execution failed")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of execution",
    )
