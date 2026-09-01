"""Unit tests for stealth context primitives and challenge detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from agent.browser.stealth import (
    CHALLENGE_PATTERNS,
    detect_challenge_page,
    is_authwall_or_login,
)


def test_detect_challenge_page_on_checkpoint_urls() -> None:
    for pattern in CHALLENGE_PATTERNS:
        mock_page = MagicMock()
        mock_page.url = f"https://www.linkedin.com{pattern}xyz"
        assert detect_challenge_page(mock_page) is True


def test_detect_challenge_page_on_normal_url() -> None:
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    assert detect_challenge_page(mock_page) is False


def test_is_authwall_or_login() -> None:
    for url in [
        "https://www.linkedin.com/uas/login?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Ffeed%2F",
        "https://www.linkedin.com/login",
        "https://www.linkedin.com/authwall?trk=rip",
    ]:
        mock_page = MagicMock()
        mock_page.url = url
        assert is_authwall_or_login(mock_page) is True
        assert detect_challenge_page(mock_page) is False

    mock_normal = MagicMock()
    mock_normal.url = "https://www.linkedin.com/feed/"
    assert is_authwall_or_login(mock_normal) is False
