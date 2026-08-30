"""Unit tests for the custom exception hierarchy in agent.errors."""

import pytest

from agent.errors import (
    AgentError,
    BotDetectionError,
    ConfigError,
    DuplicateActionError,
    ExecutionError,
    NIMError,
    NIMRateLimitError,
    NIMSchemaValidationError,
    NIMTimeoutError,
    PostNoLongerAvailableError,
    ScrapeError,
    SelectorDriftError,
    SessionError,
    SessionExpiredError,
    StaleApprovalError,
    StateStoreError,
    TelegramAPIError,
)


class TestErrorHierarchy:
    """Test suite ensuring all domain exceptions follow required inheritance."""

    def test_base_agent_error(self) -> None:
        err = AgentError("Something went wrong", details={"code": 500})
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.details == {"code": 500}
        assert isinstance(err, Exception)

    def test_config_error(self) -> None:
        err = ConfigError("Invalid configuration", details={"missing": ["API_KEY"]})
        assert isinstance(err, AgentError)
        assert err.details == {"missing": ["API_KEY"]}

    @pytest.mark.parametrize(
        "cls",
        [
            NIMError,
            NIMSchemaValidationError,
            NIMRateLimitError,
            NIMTimeoutError,
        ],
    )
    def test_nim_error_hierarchy(self, cls: type[AgentError]) -> None:
        err = cls("NIM failure")
        assert isinstance(err, AgentError)
        assert isinstance(err, NIMError)

    @pytest.mark.parametrize(
        "cls",
        [
            SessionError,
            SessionExpiredError,
            BotDetectionError,
        ],
    )
    def test_session_error_hierarchy(self, cls: type[AgentError]) -> None:
        err = cls("Session issue")
        assert isinstance(err, AgentError)
        assert isinstance(err, SessionError)

    @pytest.mark.parametrize(
        "cls",
        [
            ScrapeError,
            SelectorDriftError,
        ],
    )
    def test_scrape_error_hierarchy(self, cls: type[AgentError]) -> None:
        err = cls("Scrape issue")
        assert isinstance(err, AgentError)
        assert isinstance(err, ScrapeError)

    @pytest.mark.parametrize(
        "cls",
        [
            ExecutionError,
            PostNoLongerAvailableError,
            StaleApprovalError,
            DuplicateActionError,
        ],
    )
    def test_execution_error_hierarchy(self, cls: type[AgentError]) -> None:
        err = cls("Execution issue")
        assert isinstance(err, AgentError)
        assert isinstance(err, ExecutionError)

    def test_standalone_agent_errors(self) -> None:
        err_state = StateStoreError("State write failed")
        err_telegram = TelegramAPIError("Telegram request timed out")

        assert isinstance(err_state, AgentError)
        assert isinstance(err_telegram, AgentError)
