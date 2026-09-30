"""Stealth primitives, human-paced interaction, and bot-challenge detection."""

from __future__ import annotations

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Locator, Page

CHALLENGE_PATTERNS: tuple[str, ...] = (
    "/checkpoint/",
    "/challenge/",
    "checkpoint/challenge",
    "security-verification",
    "captcha",
    "recaptcha",
    "arkoselabs",
    "unusual activity",
    "verify your identity",
    "quick verification",
    "checkpoint/lg/login-challenge",
)


async def new_stealth_context(
    browser: Browser,
    storage_state_path: Path | None = None,
    **kwargs: Any,
) -> BrowserContext:
    """Create a Playwright browser context configured with stealth defaults.

    Args:
        browser: Playwright Browser instance.
        storage_state_path: Optional path to storage_state.json.
        kwargs: Additional context options.

    Returns:
        BrowserContext: Configured stealth context.
    """
    options: dict[str, Any] = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "permissions": ["geolocation", "notifications"],
        "bypass_csp": True,
        "ignore_https_errors": True,
    }

    if storage_state_path and Path(storage_state_path).exists():
        options["storage_state"] = str(storage_state_path)

    options.update(kwargs)
    context = await browser.new_context(**options)

    # Apply anti-detection script before any page navigation
    locale = options.get("locale", "en-US")
    base_lang = locale.split("-")[0] if "-" in locale else locale
    languages_json = json.dumps([locale, base_lang] if locale != base_lang else [locale])

    await context.add_init_script(f"""
        Object.defineProperty(navigator, 'webdriver', {{
            get: () => undefined,
        }});
        window.chrome = {{
            runtime: {{}},
            loadTimes: function() {{}},
            csi: function() {{}},
            app: {{}},
        }};
        Object.defineProperty(navigator, 'plugins', {{
            get: () => [1, 2, 3, 4, 5],
        }});
        Object.defineProperty(navigator, 'languages', {{
            get: () => {languages_json},
        }});
    """)

    return context


async def humanized_type(
    locator: Locator,
    text: str,
    min_delay_ms: float = 30.0,
    max_delay_ms: float = 90.0,
) -> None:
    """Type text into an input element with realistic human rhythm.

    Args:
        locator: Target Playwright Locator.
        text: Text string to type.
        min_delay_ms: Minimum per-key delay in milliseconds.
        max_delay_ms: Maximum per-key delay in milliseconds.
    """
    await locator.focus()
    for char in text:
        delay = random.uniform(min_delay_ms, max_delay_ms) / 1000.0
        await asyncio.sleep(delay)
        await locator.press_sequentially(char, delay=int(delay * 1000))


async def humanized_scroll(page: Page, screens: int = 2) -> None:
    """Perform smooth variable-speed scrolling with organic pauses.

    Args:
        page: Playwright Page instance.
        screens: Number of screen-lengths to scroll.
    """
    for _ in range(screens):
        scroll_distance = random.randint(500, 900)
        steps = random.randint(4, 8)
        step_dist = scroll_distance // steps

        for _ in range(steps):
            await page.evaluate(f"window.scrollBy(0, {step_dist});")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # Pause to simulate reading visible post cards
        await asyncio.sleep(random.uniform(1.0, 2.5))


async def humanized_dwell(
    min_seconds: float = 1.5,
    max_seconds: float = 3.5,
) -> None:
    """Pause asynchronously for a randomized human reading/dwell duration.

    Args:
        min_seconds: Minimum dwell duration in seconds.
        max_seconds: Maximum dwell duration in seconds.
    """
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


def detect_challenge_page(page: Page) -> bool:
    """Check if the current page contains a LinkedIn security checkpoint or bot challenge.

    Args:
        page: Playwright Page instance.

    Returns:
        bool: True if a challenge page is detected.
    """
    raw_url = getattr(page, "url", "")
    if not isinstance(raw_url, str):
        return False
    url_lower = raw_url.lower()

    for pattern in CHALLENGE_PATTERNS:
        if pattern.lower() in url_lower:
            return True

    return False


def is_authwall_or_login(page: Page) -> bool:
    """Check if the current page is a standard unauthenticated login or authwall page.

    Args:
        page: Playwright Page instance.

    Returns:
        bool: True if redirected to login or authwall.
    """
    raw_url = getattr(page, "url", "")
    if not isinstance(raw_url, str):
        return False
    url_lower = raw_url.lower()
    return (
        "/uas/login" in url_lower
        or "/login" in url_lower
        or "authwall" in url_lower
        or "/checkpoint/lg/login-submit" in url_lower
    )


async def is_real_login_page(page: Page) -> bool:
    """Check if the current page is a real login form requiring user credentials.

    A real login page either contains:
    1. Input elements with the id of '#session_key' and '#session_password', OR
    2. Input elements with type of 'email' and 'password'.
    """
    try:
        # Condition 1: input elements with id of '#session_key' and '#session_password'
        key_loc = page.locator("#session_key")
        pwd_loc = page.locator("#session_password")
        key_cnt = await key_loc.count() if hasattr(key_loc, "count") else 0
        pwd_cnt = await pwd_loc.count() if hasattr(pwd_loc, "count") else 0
        if isinstance(key_cnt, int | float) and isinstance(pwd_cnt, int | float):
            if key_cnt > 0 and pwd_cnt > 0:
                return True

        # Condition 2: input elements with type of 'email' and 'password'
        email_loc = page.locator("input[type='email']")
        type_pwd_loc = page.locator("input[type='password']")
        email_cnt = await email_loc.count() if hasattr(email_loc, "count") else 0
        type_pwd_cnt = await type_pwd_loc.count() if hasattr(type_pwd_loc, "count") else 0
        if isinstance(email_cnt, int | float) and isinstance(type_pwd_cnt, int | float):
            if email_cnt > 0 and type_pwd_cnt > 0:
                return True
    except Exception:
        pass

    return False


async def wait_for_login_redirect(page: Page, timeout: float = 15.0) -> bool:
    """Wait for LinkedIn login handshake or redirect to complete.

    Args:
        page: Playwright Page instance.
        timeout: Maximum wait time in seconds (default: 15.0).

    Returns:
        bool: True if authenticated / redirected away from login or authwall.
              False if confirmed on a real login page, challenge encountered, or timeout reached.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    poll_interval = 0.5

    while True:
        if detect_challenge_page(page):
            return False

        # If redirected away from login/authwall URLs
        if not is_authwall_or_login(page):
            return True

        # If confirmed on a real login page requiring credentials
        if await is_real_login_page(page):
            return False

        if time.monotonic() >= deadline:
            break

        remaining = deadline - time.monotonic()
        await asyncio.sleep(min(poll_interval, max(0.01, remaining)))

    return not is_authwall_or_login(page)
