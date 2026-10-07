"""LLM domain models for triage, comment drafting, and original post ideation.

Architecture Invariants:
- All domain payloads and structured outputs are typed Pydantic models.
- LLMs produce structured outputs matching these schemas.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class ReactionType(StrEnum):
    """Supported LinkedIn reaction types."""

    LIKE = "like"
    INSIGHTFUL = "insightful"
    CELEBRATE = "celebrate"
    SUPPORT = "support"
    FUNNY = "funny"
    LOVE = "love"


class TriageRecommendation(StrEnum):
    """Recommendation decision produced by LLM triage."""

    COMMENT = "comment"
    REACT = "react"
    IGNORE = "ignore"


class TriageResult(BaseModel):
    """Structured triage output for a scraped feed post."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["comment", "react", "ignore"] = Field(
        description="Whether to generate a comment, leave an endorsement/reaction, or ignore the post"
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
    reaction_type: ReactionType | str | None = Field(
        default=None,
        description="Recommended reaction type if reacting (like, insightful, celebrate, support, funny, love)",
    )


class ReplyTriageResult(BaseModel):
    """Structured triage output for evaluating a comment reply in a thread."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["reply", "ignore"] = Field(
        description="Whether to draft a follow-up reply or ignore this response"
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
    engagement_style: EngagementStyle | None = Field(
        default=None,
        description="Recommended engagement style if replying",
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
