"""Unit tests for stealth context primitives and challenge detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from agent.browser.stealth import CHALLENGE_PATTERNS, detect_challenge_page


def test_detect_challenge_page_on_checkpoint_urls() -> None:
    for pattern in CHALLENGE_PATTERNS:
        mock_page = MagicMock()
        mock_page.url = f"https://www.linkedin.com{pattern}xyz"
        assert detect_challenge_page(mock_page) is True


def test_detect_challenge_page_on_normal_url() -> None:
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/feed/"
    assert detect_challenge_page(mock_page) is False
