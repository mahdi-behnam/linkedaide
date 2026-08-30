"""Custom exception hierarchy for the LinkedIn HITL AI Agent.

Architecture Invariants:
- All agent exceptions inherit from AgentError.
- Subsystems raise specific domain exceptions rather than generic exceptions.
- BotDetectionError trips the circuit breaker and must never be swallowed.
"""

from typing import Any


class AgentError(Exception):
    """Base exception for all agent domain errors."""

    def __init__(self, message: str, *args: Any, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, *args)
        self.message = message
        self.details = details or {}


class ConfigError(AgentError):
    """Raised when configuration validation, loading, or decryption fails."""


class NIMError(AgentError):
    """Base exception for NVIDIA NIM / LLM integration failures."""


class NIMSchemaValidationError(NIMError):
    """Raised when LLM output fails schema validation or repair attempts."""


class NIMRateLimitError(NIMError):
    """Raised when NVIDIA NIM API rate limit (HTTP 429) is encountered."""


class NIMTimeoutError(NIMError):
    """Raised when NVIDIA NIM request times out."""


class SessionError(AgentError):
    """Base exception for browser authentication and session errors."""


class SessionExpiredError(SessionError):
    """Raised when the LinkedIn session is invalid or expired and requires re-auth."""


class BotDetectionError(SessionError):
    """Raised when LinkedIn presents a CAPTCHA, checkpoint, or security challenge.

    This exception is safety-critical and triggers the circuit breaker.
    """


class ScrapeError(AgentError):
    """Base exception for feed and post scraping errors."""


class SelectorDriftError(ScrapeError):
    """Raised when DOM selectors fail to find expected elements due to UI changes."""


class ExecutionError(AgentError):
    """Base exception for action execution errors."""


class PostNoLongerAvailableError(ExecutionError):
    """Raised when target post was deleted or is no longer accessible on LinkedIn."""


class StaleApprovalError(ExecutionError):
    """Raised when an approval is executed beyond its configured TTL."""


class DuplicateActionError(ExecutionError):
    """Raised when an action has already been executed or is duplicate."""


class StateStoreError(AgentError):
    """Raised when state persistence, file I/O, or Git operations fail."""


class TelegramAPIError(AgentError):
    """Raised when Telegram Bot API requests fail."""
