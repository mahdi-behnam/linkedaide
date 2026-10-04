"""Dispatch, event triggers, and Telegram callback schemas.

Architecture Invariants:
- Telegram callback payloads are compact and opaque (<= 64 bytes limit).
- GitHub repository_dispatch event triggers are strongly validated.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Compact action code constants for Telegram callback_data (<= 64 bytes limit)
ACTION_CODE_APPROVE_COMMENT = "ac"
ACTION_CODE_REJECT_COMMENT = "rc"
ACTION_CODE_APPROVE_POST = "ap"
ACTION_CODE_REJECT_POST = "rp"
ACTION_CODE_APPROVE_REPLY = "ar"
ACTION_CODE_REJECT_REPLY = "rr"
ACTION_CODE_APPROVE_CONNECTION = "acon"
ACTION_CODE_REJECT_CONNECTION = "rcon"
ACTION_CODE_EDIT = "ed"
ACTION_CODE_REGENERATE = "reg"

CALLBACK_ACTION_MAP: dict[str, str] = {
    ACTION_CODE_APPROVE_COMMENT: "approve_comment",
    ACTION_CODE_REJECT_COMMENT: "reject_comment",
    ACTION_CODE_APPROVE_POST: "approve_post",
    ACTION_CODE_REJECT_POST: "reject_post",
    ACTION_CODE_APPROVE_REPLY: "approve_reply",
    ACTION_CODE_REJECT_REPLY: "reject_reply",
    ACTION_CODE_APPROVE_CONNECTION: "approve_connection",
    ACTION_CODE_REJECT_CONNECTION: "reject_connection",
    ACTION_CODE_EDIT: "edit",
    ACTION_CODE_REGENERATE: "regenerate",
    "edit": "edit",
    "ed": "edit",
    "reg": "regenerate",
    "regenerate": "regenerate",
    "apv": "approve_comment",
    "rej": "reject_comment",
    "approve_reply": "approve_reply",
    "reject_reply": "reject_reply",
    "approve_connection": "approve_connection",
    "reject_connection": "reject_connection",
    "ar": "approve_reply",
    "rr": "reject_reply",
    "acon": "approve_connection",
    "rcon": "reject_connection",
}

REVERSE_ACTION_MAP: dict[str, str] = {
    "approve_comment": ACTION_CODE_APPROVE_COMMENT,
    "reject_comment": ACTION_CODE_REJECT_COMMENT,
    "approve_post": ACTION_CODE_APPROVE_POST,
    "reject_post": ACTION_CODE_REJECT_POST,
    "approve_reply": ACTION_CODE_APPROVE_REPLY,
    "reject_reply": ACTION_CODE_REJECT_REPLY,
    "approve_connection": ACTION_CODE_APPROVE_CONNECTION,
    "reject_connection": ACTION_CODE_REJECT_CONNECTION,
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
            ACTION_CODE_APPROVE_REPLY,
            ACTION_CODE_APPROVE_CONNECTION,
            "approve_comment",
            "approve_post",
            "approve_reply",
            "approve_connection",
            "apv",
            "ar",
            "acon",
        )

    @property
    def is_rejection(self) -> bool:
        """Check if action represents a rejection."""
        return self.action_code in (
            ACTION_CODE_REJECT_COMMENT,
            ACTION_CODE_REJECT_POST,
            ACTION_CODE_REJECT_REPLY,
            ACTION_CODE_REJECT_CONNECTION,
            "reject_comment",
            "reject_post",
            "reject_reply",
            "reject_connection",
            "rej",
            "rr",
            "rcon",
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
