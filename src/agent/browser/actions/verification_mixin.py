"""Verification and diagnostic screenshot mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from agent.browser import stealth, telemetry
from agent.errors import BotDetectionError, SessionExpiredError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from agent.config import Settings

logger = logging.getLogger(__name__)


class VerificationMixin:
    """Mixin providing screenshot capture, telemetry capture, and DOM verification."""

    page: Page
    settings: Settings
    debug_dir: Path

    async def _capture_screenshot(self, name: str) -> str:
        """Capture audit screenshot and return relative path."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        path = self.debug_dir / filename
        try:
            await self.page.screenshot(path=str(path), full_page=False)
            return str(path)
        except Exception:
            return ""

    async def _upload_screenshot_to_r2(self, local_path: str, key_suffix: str) -> str:
        """Upload local audit screenshot to Cloudflare R2 media vault via Worker API."""
        if not local_path:
            return local_path

        worker_url = getattr(self.settings, "worker_url", None)
        api_secret = getattr(self.settings, "desktop_api_secret", None)
        if not worker_url or not api_secret:
            return local_path

        file_path = Path(local_path)
        if not file_path.exists() or not file_path.is_file():
            return local_path

        secret_val = (
            api_secret.get_secret_value()
            if hasattr(api_secret, "get_secret_value")
            else str(api_secret)
        )
        if not secret_val:
            return local_path

        r2_key = f"screenshots/{key_suffix}.png"
        endpoint = f"{worker_url.rstrip('/')}/api/media/{r2_key}"
        headers = {
            "Authorization": f"Bearer {secret_val}",
            "Content-Type": "image/png",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                data = file_path.read_bytes()
                resp = await client.put(endpoint, content=data, headers=headers)
                if resp.status_code == 200:
                    logger.info("Uploaded audit screenshot to R2 vault: %s", r2_key)
                    return r2_key
                else:
                    logger.warning(
                        "R2 screenshot upload failed (HTTP %s): %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return local_path
        except Exception as err:
            logger.warning("R2 screenshot upload encountered non-fatal error: %s", err)
            return local_path

    async def _capture_telemetry(
        self,
        trigger: str,
        target_selector: str | None = None,
        item_id: str | None = None,
    ) -> str | None:
        """Capture DOM telemetry defensively without disrupting error handling."""
        try:
            call_kwargs: dict[str, Any] = {"trigger": trigger}
            if target_selector is not None:
                call_kwargs["target_selector"] = target_selector
            if item_id is not None:
                call_kwargs["item_id"] = item_id
            res = await telemetry.capture_dom_telemetry(self.page, **call_kwargs)
            return str(res) if res is not None else None
        except Exception as err:
            logger.debug("Failed capturing DOM telemetry for %s: %s", trigger, err)
            return None

    async def _check_error_toasts(self) -> str | None:
        """Check for LinkedIn error toast notifications or inline error alerts."""
        error_loc = self.page.locator(
            "div.artdeco-toast-item--error, div.artdeco-toast--error, "
            "div.artdeco-inline-feedback--error, div[role='alert'].artdeco-toast-item, "
            ".artdeco-inline-feedback--error"
        )
        try:
            if await error_loc.count() > 0:
                first = error_loc.first
                try:
                    if not hasattr(first, "is_visible") or await first.is_visible():
                        text = (await first.inner_text()).strip()
                        return text if text else "LinkedIn error banner detected"
                except Exception:
                    try:
                        text = (await first.inner_text()).strip()
                        if text:
                            return text
                    except Exception:
                        return "LinkedIn error banner detected"
        except Exception:
            pass
        return None

    async def verify_login(self, target_url: str | None = None) -> bool:
        """Verify the current browser session is authenticated."""
        nav_target = target_url or "https://www.linkedin.com/feed/"
        current_url = self.page.url if isinstance(self.page.url, str) else ""
        if not current_url.startswith("https://www.linkedin.com"):
            try:
                res = self.page.goto(nav_target, wait_until="domcontentloaded", timeout=30000)
                if hasattr(res, "__await__"):
                    await res
            except Exception as err:
                logger.warning("Navigation during verify_login to %s failed: %s", nav_target, err)

        if stealth.detect_challenge_page(self.page):
            raise BotDetectionError(f"Challenge page detected during login check: {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            is_authenticated = await stealth.wait_for_login_redirect(self.page, timeout=15.0)
            if not is_authenticated:
                raise SessionExpiredError(
                    f"LinkedIn session expired; redirected to {self.page.url}"
                )

        nav_or_feed = self.page.locator("nav.global-nav, main, div.scaffold-layout")
        return await nav_or_feed.count() > 0

    async def verify_post_exists(self, post_url: str) -> bool:
        """Check whether the target post still exists and is accessible."""
        if not post_url:
            return False

        current_url = self.page.url if isinstance(self.page.url, str) else ""
        if not current_url or post_url not in current_url:
            try:
                res = self.page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                if hasattr(res, "__await__"):
                    await res
                await asyncio.sleep(1.0)
            except Exception as err:
                logger.warning("Navigation to post %s failed: %s", post_url, err)
                return False

        if stealth.detect_challenge_page(self.page):
            raise BotDetectionError(f"Challenge page on post navigation: {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            raise SessionExpiredError(
                f"LinkedIn session expired navigating to post: {self.page.url}"
            )

        # Check for deleted / unavailable markers
        error_container = self.page.locator(
            "div.artdeco-empty-state, "
            "h1:has-text('This post is no longer available'), "
            ":has-text('Post not found'), "
            ":has-text('This post was deleted or removed'), "
            ":has-text('This post is no longer available')"
        )
        if await error_container.count() > 0:
            return False

        post_article = self.page.locator(
            "button[aria-label*='Reaction button state' i], "
            "button[aria-label*='Like' i], "
            "button.react-button__trigger, "
            "article, div.feed-shared-update-v2, "
            "div[id^='expanded'][id*='FEED'], "
            "div[data-testid='mainFeed'] > div"
        )
        return await post_article.count() > 0
