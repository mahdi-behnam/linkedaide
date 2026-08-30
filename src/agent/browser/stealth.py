"""Stealth primitives, human-paced interaction, and bot-challenge detection."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Locator, Page

CHALLENGE_PATTERNS: tuple[str, ...] = (
    "/checkpoint/",
    "/challenge/",
    "/uas/login",
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
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {},
        };
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
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


def detect_challenge_page(page: Page) -> bool:
    """Check if the current page contains a LinkedIn security checkpoint or bot challenge.

    Args:
        page: Playwright Page instance.

    Returns:
        bool: True if a challenge page is detected.
    """
    url_lower = page.url.lower()

    for pattern in CHALLENGE_PATTERNS:
        if pattern.lower() in url_lower:
            return True

    return False
