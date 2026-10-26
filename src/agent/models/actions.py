"""Action schemas for pending approvals, scheduled posts, and connection outreach.

Architecture Invariants:
- All write actions pending human approval are represented as PendingAction.
- Scheduled posts and connection requests are typed Pydantic models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.models.llm import EngagementStyle


class PendingAction(BaseModel):
    """Durable pending action waiting for Telegram human approval."""

    model_config = ConfigDict(extra="ignore")

    item_id: str = Field(description="Unique deterministic identifier for the pending item")
    action_type: Literal[
        "approve_comment", "approve_post", "approve_reply", "approve_connection", "approve_reaction"
    ] = Field(description="Type of action requiring approval")
    reaction_type: str = Field(
        default="like",
        description="Reaction type for approve_reaction (like, insightful, celebrate, support, funny, love)",
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
    media_attachments: list[MediaAttachment] = Field(
        default_factory=list,
        description="Optional media attachments for original posts",
    )
    post_image_url: str | None = Field(
        default=None,
        description="Direct URL of image attached to target post",
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback model was used to draft this action",
    )
    model_used: str | None = Field(
        default=None,
        description="Identifier of model used to draft this action",
    )


class MediaAttachment(BaseModel):
    """Media attachment for scheduled original posts (e.g. image, carousel PDF)."""

    model_config = ConfigDict(extra="ignore")

    media_type: Literal["image", "carousel_pdf"] = Field(description="Type of media attachment")
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
    status: Literal["draft", "scheduled", "published", "failed", "rejected"] = Field(
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


class ConnectionRequestAction(BaseModel):
    """Pending or executed LinkedIn connection request candidate."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        description="Unique deterministic or generated identifier for the connection action"
    )
    profile_url: str = Field(description="Target LinkedIn profile URL")
    target_name: str = Field(description="Target contact full name")
    target_headline: str = Field(default="", description="Target contact professional headline")
    mutual_context: str = Field(
        default="",
        description="Contextual interaction or mutual topic grounding outreach reason",
    )
    note_text: str = Field(
        default="",
        max_length=300,
        description="Personalized connection invitation note text (max 300 chars)",
    )
    status: Literal["pending", "approved", "rejected", "sent", "failed"] = Field(
        default="pending",
        description="Current lifecycle status of the outreach action",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the connection action candidate was created",
    )
    approved_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the connection request was approved",
    )


# Type alias for backward compatibility and outreach queue terminology
ConnectionCandidate = ConnectionRequestAction
