"""Persistence and state tracking schemas for LinkedAide.

Architecture Invariants:
- All audit history entries and daily counters are typed Pydantic models.
- History is append-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActiveThreadRecord(BaseModel):
    """Tracking record for active multi-turn comment threads on LinkedIn."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique thread tracking ID")
    post_url: str = Field(description="Direct URL to the target post")
    post_urn: str = Field(description="LinkedIn post URN")
    our_comment_urn: str = Field(description="URN of our comment being replied to")
    our_comment_text: str = Field(description="Text content of our original comment")
    post_author: str = Field(description="Author of the original post")
    last_checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this thread was last inspected for replies",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when thread tracking started",
    )
    status: Literal["active", "resolved", "expired"] = Field(
        default="active",
        description="Lifecycle status of the thread",
    )


class ThreadReplyItem(BaseModel):
    """Individual reply item discovered within a comment thread."""

    model_config = ConfigDict(extra="ignore")

    reply_urn: str = Field(description="LinkedIn URN or ID of the reply")
    parent_comment_urn: str = Field(description="URN of the parent comment being replied to")
    author_name: str = Field(description="Name of the person who replied")
    author_headline: str = Field(default="", description="Headline or title of the replier")
    reply_text: str = Field(description="Text content of the reply")
    is_post_author: bool = Field(
        default=False, description="Whether the replier is the original post author"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when reply was discovered",
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
    connections_sent: int = Field(
        default=0, ge=0, description="Number of connection requests sent today"
    )
