"""Pydantic v2 domain and persistence schemas for the LinkedIn HITL Agent.

Architecture Invariants:
- All domain payloads, triage outputs, drafts, and persistence records are typed Pydantic models.
- LLMs produce structured outputs matching these schemas.
- Telegram approval callback payloads are compact and opaque.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EngagementStyle(StrEnum):
    """Contextual engagement styles for comment triage and drafting."""

    TECHNICAL_DEEP_DIVE = "technical_deep_dive"
    INQUISITIVE_QUESTION = "inquisitive_question"
    CONTRARIAN_PERSPECTIVE = "contrarian_perspective"
    SUPPORTIVE_SYNTHESIS = "supportive_synthesis"


class RiskFlag(StrEnum):
    """Risk indicators identified during feed post triage."""

    POLITICAL = "political"
    SALES_PITCH = "sales_pitch"
    JOB_POSTING = "job_posting"
    LOW_SIGNAL = "low_signal"
    CONTROVERSIAL = "controversial"


class TriageRecommendation(StrEnum):
    """Recommendation decision produced by LLM triage."""

    COMMENT = "comment"
    IGNORE = "ignore"


class TriageResult(BaseModel):
    """Structured triage output for a scraped feed post."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["comment", "ignore"] = Field(
        description="Whether to generate a comment or ignore the post"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0",
    )
    reasoning: str = Field(
        max_length=240,
        description="Concise rationale for the triage decision (max 240 chars)",
    )
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="List of detected risk factors, if any",
    )
    engagement_style: EngagementStyle | None = Field(
        default=None,
        description="Recommended engagement style if commenting (technical_deep_dive, inquisitive_question, contrarian_perspective, supportive_synthesis)",
    )


class CommentDraft(BaseModel):
    """Structured LLM draft for engaging on a target LinkedIn post."""

    model_config = ConfigDict(extra="forbid")

    draft_comment: str = Field(
        min_length=1,
        max_length=600,
        description="Drafted comment text (1 to 600 characters)",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Key topic tags relevant to the comment (max 5)",
    )
    engagement_style: EngagementStyle | None = Field(
        default=None,
        description="Engagement style applied in the drafted comment",
    )

    @property
    def comment_text(self) -> str:
        """Alias for draft_comment providing backwards and idiomatic compatibility."""
        return self.draft_comment


class PostIdea(BaseModel):
    """Structured LLM draft for an original LinkedIn post."""

    model_config = ConfigDict(extra="forbid")

    should_post: bool = Field(description="Whether conditions warrant creating an original post")
    headline: str = Field(
        default="",
        max_length=120,
        description="Hook or working headline for the post (max 120 chars)",
    )
    draft_post_text: str = Field(
        default="",
        max_length=1200,
        description="Full drafted post text (max 1200 chars)",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Relevant hashtags (max 3)",
    )
    reasoning: str = Field(
        default="",
        max_length=240,
        description="Rationale for ideation decision (max 240 chars)",
    )


class PendingAction(BaseModel):
    """Durable pending action waiting for Telegram human approval."""

    model_config = ConfigDict(extra="ignore")

    item_id: str = Field(description="Unique deterministic identifier for the pending item")
    action_type: Literal["approve_comment", "approve_post"] = Field(
        description="Type of action requiring approval"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the suggestion was created",
    )
    post_urn: str = Field(default="", description="LinkedIn post URN (empty for original posts)")
    post_url: str = Field(default="", description="Direct URL to the target post")
    author_name: str = Field(default="", description="Author name of target post")
    author_headline: str = Field(default="", description="Headline or title of target post author")
    post_excerpt: str = Field(default="", description="Excerpt of original post for context")
    draft_text: str = Field(description="Drafted comment or post text")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Triage/generation confidence score",
    )
    reasoning: str = Field(default="", description="Rationale presented to the human approver")
    engagement_style: EngagementStyle | str | None = Field(
        default=None,
        description="Engagement style selected for this comment action",
    )
    telegram_chat_id: int | None = Field(
        default=None, description="Telegram chat ID where suggestion was sent"
    )
    telegram_message_id: int | None = Field(
        default=None, description="Telegram message ID containing inline keyboard"
    )


class HistoryStatus(StrEnum):
    """Final terminal status for an action."""

    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED_SUCCESS = "executed_success"
    EXECUTED_FAILED = "executed_failed"
    HALTED = "halted"


class HistoryEntry(BaseModel):
    """Append-only audit log entry recorded in state/history.jsonl."""

    model_config = ConfigDict(extra="ignore")

    item_id: str = Field(description="Identifier of the handled action")
    action_type: str = Field(description="Action type: comment or post")
    final_status: Literal[
        "rejected", "expired", "executed_success", "executed_failed", "halted"
    ] = Field(description="Terminal status of the action")
    decided_at: datetime | None = Field(
        default=None, description="UTC timestamp when human approval or rejection occurred"
    )
    executed_at: datetime | None = Field(
        default=None, description="UTC timestamp when execution finished"
    )
    screenshot_path: str | None = Field(
        default=None, description="Relative path to execution confirmation screenshot"
    )
    error: str | None = Field(default=None, description="Error message if execution failed")


class DailyCounters(BaseModel):
    """Daily rate limit and safety counters tracked in state/daily_counters.json."""

    model_config = ConfigDict(extra="ignore")

    date: str = Field(description="Date string in YYYY-MM-DD format")
    comments_executed: int = Field(default=0, ge=0, description="Number of comments executed today")
    posts_executed: int = Field(default=0, ge=0, description="Number of posts published today")
    suggestions_sent: int = Field(
        default=0, ge=0, description="Number of Telegram suggestions sent today"
    )


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
    screenshot_path: str | None = Field(
        default=None, description="Path to execution verification screenshot"
    )
    error: str | None = Field(default=None, description="Error details if execution failed")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of execution",
    )


class PostIdeationContext(BaseModel):
    """Contextual information provided to the LLM for original post ideation."""

    model_config = ConfigDict(extra="ignore")

    recent_topics: list[str] = Field(
        default_factory=list,
        description="Topics recently covered to prevent repetition",
    )
    user_focus_areas: list[str] = Field(
        default_factory=list,
        description="Configured domain focus areas",
    )


# Compact action code constants for Telegram callback_data (<= 64 bytes limit)
ACTION_CODE_APPROVE_COMMENT = "ac"
ACTION_CODE_REJECT_COMMENT = "rc"
ACTION_CODE_APPROVE_POST = "ap"
ACTION_CODE_REJECT_POST = "rp"
ACTION_CODE_EDIT = "ed"
ACTION_CODE_REGENERATE = "reg"

CALLBACK_ACTION_MAP: dict[str, str] = {
    ACTION_CODE_APPROVE_COMMENT: "approve_comment",
    ACTION_CODE_REJECT_COMMENT: "reject_comment",
    ACTION_CODE_APPROVE_POST: "approve_post",
    ACTION_CODE_REJECT_POST: "reject_post",
    ACTION_CODE_EDIT: "edit",
    ACTION_CODE_REGENERATE: "regenerate",
    "edit": "edit",
    "ed": "edit",
    "reg": "regenerate",
    "regenerate": "regenerate",
    "apv": "approve_comment",
    "rej": "reject_comment",
}

REVERSE_ACTION_MAP: dict[str, str] = {
    "approve_comment": ACTION_CODE_APPROVE_COMMENT,
    "reject_comment": ACTION_CODE_REJECT_COMMENT,
    "approve_post": ACTION_CODE_APPROVE_POST,
    "reject_post": ACTION_CODE_REJECT_POST,
    "edit": ACTION_CODE_EDIT,
    "ed": ACTION_CODE_EDIT,
    "regenerate": ACTION_CODE_REGENERATE,
    "reg": ACTION_CODE_REGENERATE,
}


class CallbackDataPayload(BaseModel):
    """Telegram inline keyboard callback data parser and serializer.

    Encodes compact `<action_code>:<item_id>` payloads respecting Telegram's 64-byte limit.
    """

    model_config = ConfigDict(extra="forbid")

    action_code: str = Field(description="Compact action code (e.g. ac, rc, ap, rp, ed)")
    item_id: str = Field(description="Unique item identifier")

    @field_validator("action_code")
    @classmethod
    def validate_action_code(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("action_code must not be empty")
        return v.strip()

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("item_id must not be empty")
        return v.strip()

    def to_callback_data(self) -> str:
        """Serialize into compact '<action_code>:<item_id>' string."""
        raw = f"{self.action_code}:{self.item_id}"
        encoded_len = len(raw.encode("utf-8"))
        if encoded_len > 64:
            raise ValueError(
                f"Callback data exceeds Telegram 64-byte limit ({encoded_len} bytes): '{raw}'"
            )
        return raw

    @classmethod
    def from_callback_data(cls, data: str) -> CallbackDataPayload:
        """Parse raw Telegram callback_data string."""
        if not data or ":" not in data:
            raise ValueError(f"Invalid callback data format (expected 'action:item_id'): '{data}'")
        parts = data.split(":", 1)
        return cls(action_code=parts[0], item_id=parts[1])

    @property
    def is_approval(self) -> bool:
        """Check if action represents an approval."""
        return self.action_code in (
            ACTION_CODE_APPROVE_COMMENT,
            ACTION_CODE_APPROVE_POST,
            "approve_comment",
            "approve_post",
            "apv",
        )

    @property
    def is_rejection(self) -> bool:
        """Check if action represents a rejection."""
        return self.action_code in (
            ACTION_CODE_REJECT_COMMENT,
            ACTION_CODE_REJECT_POST,
            "reject_comment",
            "reject_post",
            "rej",
        )

    @property
    def is_edit(self) -> bool:
        """Check if action represents an edit request."""
        return self.action_code in (
            ACTION_CODE_EDIT,
            "edit",
            "ed",
        )

    @property
    def is_regenerate(self) -> bool:
        """Check if action represents a regenerate request."""
        return self.action_code in (
            ACTION_CODE_REGENERATE,
            "reg",
            "regenerate",
        )

    @property
    def canonical_action_type(self) -> str:
        """Return canonical action type string."""
        return CALLBACK_ACTION_MAP.get(self.action_code, self.action_code)


class RepositoryDispatchPayload(BaseModel):
    """GitHub repository_dispatch event trigger payload."""

    model_config = ConfigDict(extra="ignore")

    event_type: str = Field(description="GitHub repository_dispatch event type")
    client_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary client payload dictionary",
    )


class MediaAttachment(BaseModel):
    """Media attachment for scheduled original posts (e.g. image, carousel PDF)."""

    model_config = ConfigDict(extra="ignore")

    media_type: Literal["image", "carousel_pdf"] = Field(
        description="Type of media attachment"
    )
    file_name: str = Field(description="Original file name of attachment")
    file_url: str = Field(default="", description="URL or local path to attachment file")
    slide_count: int = Field(default=1, ge=1, description="Number of slides or pages")


class ScheduledPost(BaseModel):
    """Scheduled LinkedIn original post created via Post Composer Studio."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique deterministic or generated identifier for scheduled post")
    headline: str = Field(default="", description="Hook or working headline for post")
    post_text: str = Field(description="Full drafted post text")
    scheduled_time: datetime | str | None = Field(
        default=None, description="Scheduled publication timestamp in ISO format"
    )
    status: Literal["draft", "scheduled", "published", "failed"] = Field(
        default="draft", description="Status of the post lifecycle"
    )
    media: list[MediaAttachment] = Field(
        default_factory=list, description="Attached media items (images, carousel PDFs)"
    )
    topic_pillar: str = Field(
        default="", description="Topic pillar or category for content alignment"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of post creation",
    )
    approved_at: datetime | None = Field(
        default=None, description="UTC timestamp of human operator approval"
    )

