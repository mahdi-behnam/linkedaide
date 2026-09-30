"""Rate limiting and daily caps enforcement."""

from __future__ import annotations

from datetime import UTC, datetime

from agent.config import Settings
from agent.models import DailyCounters, PendingAction


class DailyCapEnforcer:
    """Enforces deterministic daily action limits and approval TTLs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def can_execute_comment(self, counters: DailyCounters) -> tuple[bool, str | None]:
        """Check if daily comment limit allows another comment.

        Args:
            counters: Current daily counters.

        Returns:
            tuple[bool, str | None]: (True, None) if allowed, (False, reason) if capped.
        """
        if counters.comments_executed >= self.settings.max_comments_per_day:
            return (
                False,
                f"Daily comment cap reached ({counters.comments_executed}/{self.settings.max_comments_per_day})",
            )
        return True, None

    def can_execute_post(self, counters: DailyCounters) -> tuple[bool, str | None]:
        """Check if daily original post limit allows another post.

        Args:
            counters: Current daily counters.

        Returns:
            tuple[bool, str | None]: (True, None) if allowed, (False, reason) if capped.
        """
        if counters.posts_executed >= self.settings.max_posts_per_day:
            return (
                False,
                f"Daily post cap reached ({counters.posts_executed}/{self.settings.max_posts_per_day})",
            )
        return True, None

    def can_execute_connection(self, counters: DailyCounters) -> tuple[bool, str | None]:
        """Check if daily connection request limit allows another connection invitation.

        Args:
            counters: Current daily counters.

        Returns:
            tuple[bool, str | None]: (True, None) if allowed, (False, reason) if capped.
        """
        if not can_send_connection(counters, self.settings.max_connections_per_day):
            return (
                False,
                f"Daily connection cap reached ({counters.connections_sent}/{self.settings.max_connections_per_day})",
            )
        return True, None

    def can_send_suggestion(self, run_suggestions_count: int) -> bool:
        """Check if the maximum suggestions per scout run has been reached.

        Args:
            run_suggestions_count: Number of suggestions created in current run.

        Returns:
            bool: True if more suggestions can be surfaced.
        """
        return run_suggestions_count < self.settings.max_suggestions_per_run

    def is_within_ttl(
        self, pending: PendingAction, max_ttl_hours: int | None = None, now: datetime | None = None
    ) -> bool:
        """Check if a pending action is still within its valid TTL window.

        Args:
            pending: The pending action record.
            max_ttl_hours: Optional override for TTL hours (default: settings.pending_action_ttl_hours).
            now: Optional current timestamp (default: UTC now).

        Returns:
            bool: True if still within TTL, False if expired.
        """
        ttl = max_ttl_hours if max_ttl_hours is not None else self.settings.pending_action_ttl_hours
        current_time = now or datetime.now(UTC)

        created_at = pending.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        elapsed_seconds = (current_time - created_at).total_seconds()
        return elapsed_seconds <= (ttl * 3600)


def can_send_connection(counters: DailyCounters, max_daily: int = 10) -> bool:
    """Check if daily connection counter allows sending another connection request.

    Args:
        counters: Current daily counters.
        max_daily: Maximum connection requests allowed per day.

    Returns:
        bool: True if another connection request can be sent today.
    """
    return counters.connections_sent < max_daily
