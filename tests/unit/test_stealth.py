"""Unit tests for stealth context primitives and challenge detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.browser.stealth import (
    CHALLENGE_PATTERNS,
    detect_challenge_page,
    humanized_dwell,
    is_authwall_or_login,
    is_real_login_page,
    wait_for_login_redirect,
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


@pytest.mark.asyncio
async def test_humanized_dwell_pauses_within_range() -> None:
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await humanized_dwell(min_seconds=1.5, max_seconds=3.5)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 1.5 <= delay <= 3.5


@pytest.mark.asyncio
async def test_humanized_dwell_custom_bounds() -> None:
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await humanized_dwell(min_seconds=0.1, max_seconds=0.2)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0.1 <= delay <= 0.2


@pytest.mark.asyncio
async def test_is_real_login_page_with_session_ids() -> None:
    page = MagicMock()

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if selector in ("#session_key", "#session_password"):
            loc.count = AsyncMock(return_value=1)
        else:
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)
    assert await is_real_login_page(page) is True


@pytest.mark.asyncio
async def test_is_real_login_page_with_email_password_types() -> None:
    page = MagicMock()

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if selector in ("input[type='email']", "input[type='password']"):
            loc.count = AsyncMock(return_value=1)
        else:
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)
    assert await is_real_login_page(page) is True


@pytest.mark.asyncio
async def test_is_real_login_page_handshake_returns_false() -> None:
    # On handshake page ("Signing you in..."), no password/credential inputs exist
    page = MagicMock()
    empty_loc = MagicMock()
    empty_loc.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=empty_loc)

    assert await is_real_login_page(page) is False


@pytest.mark.asyncio
async def test_is_real_login_page_handles_exception_gracefully() -> None:
    page = MagicMock()
    page.locator = MagicMock(side_effect=RuntimeError("Playwright locator crashed"))

    assert await is_real_login_page(page) is False


@pytest.mark.asyncio
async def test_wait_for_login_redirect_immediate_when_already_authenticated() -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    result = await wait_for_login_redirect(page, timeout=15.0)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_login_redirect_returns_false_on_real_login_page() -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if selector in ("#session_key", "#session_password"):
            loc.count = AsyncMock(return_value=1)
        else:
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    result = await wait_for_login_redirect(page, timeout=15.0)
    assert result is False


@pytest.mark.asyncio
async def test_wait_for_login_redirect_returns_false_on_challenge_page() -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"

    result = await wait_for_login_redirect(page, timeout=15.0)
    assert result is False


@pytest.mark.asyncio
async def test_wait_for_login_redirect_succeeds_when_handshake_redirects_to_feed() -> None:
    page = MagicMock()
    # Initially on login handshake page
    page.url = (
        "https://www.linkedin.com/login/?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Ffeed%2F"
    )

    # No real login inputs on handshake page
    empty_loc = MagicMock()
    empty_loc.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=empty_loc)

    call_count = 0

    async def fake_sleep(duration: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            # Simulate LinkedIn redirecting to /feed/ after 2 polling iterations
            page.url = "https://www.linkedin.com/feed/"

    with patch("asyncio.sleep", side_effect=fake_sleep):
        result = await wait_for_login_redirect(page, timeout=15.0)
        assert result is True
        assert call_count == 2


@pytest.mark.asyncio
async def test_wait_for_login_redirect_times_out_when_stuck_on_authwall() -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/authwall"

    empty_loc = MagicMock()
    empty_loc.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=empty_loc)

    # Fast forward time to simulate 15s timeout
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("time.monotonic", side_effect=[0.0, 1.0, 16.0, 17.0]),
    ):
        result = await wait_for_login_redirect(page, timeout=15.0)
        assert result is False
