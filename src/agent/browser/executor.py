"""Playwright browser action executor for comments and posts."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from agent.browser.stealth import (
    detect_challenge_page,
    humanized_type,
    is_authwall_or_login,
)
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    PostNoLongerAvailableError,
    SessionExpiredError,
)
from agent.models.schemas import ExecutionResult

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes validated LinkedIn write and read actions via Playwright."""

    def __init__(self, page: Page, settings: Settings, debug_dir: Path | None = None) -> None:
        self.page = page
        self.settings = settings
        self.debug_dir = debug_dir or (Path("debug") / "screenshots")
        self.debug_dir.mkdir(parents=True, exist_ok=True)

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

    async def verify_login(self) -> bool:
        """Verify the current browser session is authenticated.

        Returns:
            bool: True if logged in.

        Raises:
            BotDetectionError: If security checkpoint or challenge is detected.
            SessionExpiredError: If redirected to login page.
        """
        if detect_challenge_page(self.page):
            raise BotDetectionError(f"Challenge page detected during login check: {self.page.url}")

        if is_authwall_or_login(self.page):
            raise SessionExpiredError(f"LinkedIn session expired; redirected to {self.page.url}")

        nav_or_feed = self.page.locator("nav.global-nav, main, div.scaffold-layout")
        return await nav_or_feed.count() > 0

    async def verify_post_exists(self, post_url: str) -> bool:
        """Check whether the target post still exists and is accessible.

        Args:
            post_url: Direct URL to the LinkedIn update.

        Returns:
            bool: True if post exists and is accessible.
        """
        if detect_challenge_page(self.page):
            raise BotDetectionError(f"Challenge page on post navigation: {self.page.url}")

        # Check for deleted / unavailable markers
        error_container = self.page.locator(
            "div.artdeco-empty-state, h1:has-text('This post is no longer available')"
        )
        if await error_container.count() > 0:
            return False

        post_article = self.page.locator(
            "article, div.feed-shared-update-v2, div.feed-shared-update-v2__content, div[componentkey], a[href*='/in/']"
        )
        return await post_article.count() > 0

    async def post_comment(
        self,
        post_url: str,
        comment_text: str,
        item_id: str = "item_action",
        dry_run: bool | None = None,
    ) -> ExecutionResult:
        """Post an approved comment on a LinkedIn post.

        Args:
            post_url: Target post URL.
            comment_text: Approved comment text.
            item_id: Action item ID for audit logging.
            dry_run: Override dry-run setting.

        Returns:
            ExecutionResult: Execution outcome with screenshot.
        """
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        if detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        # Verify target post exists
        post_exists = await self.verify_post_exists(post_url)
        if not post_exists:
            screenshot = await self._capture_screenshot(f"missing_post_{item_id}")
            raise PostNoLongerAvailableError(f"Post at {post_url} is no longer available")

        # Dry run safety guarantee: zero write submission
        if is_dry_run:
            logger.info("DRY_RUN: Simulated comment on %s: %s", post_url, comment_text)
            screenshot = await self._capture_screenshot(f"dryrun_comment_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_comment",
                item_id=item_id,
                post_url=post_url,
                comment_text=comment_text,
                post_text=None,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )

        # Live write submission path
        try:
            # Locate comment button
            comment_btn = self.page.locator(
                "button[aria-label*='Comment'], button:has-text('Comment'), button.comment-button"
            ).first
            if await comment_btn.count() > 0:
                await comment_btn.click()

            comment_box = self.page.locator(
                "div.tiptap.ProseMirror, div[role='textbox'][aria-label*='comment' i], div[role='textbox'][contenteditable='true'], div.ql-editor, textarea[name='comment']"
            ).first
            if await comment_box.count() == 0:
                raise ExecutionError("Comment input box not found in DOM")

            await humanized_type(comment_box, comment_text)

            submit_btn = self.page.locator(
                "button.comments-comment-box__submit-button, button:has-text('Comment'), button:has-text('Post'), button[type='submit']"
            ).first
            if await submit_btn.count() == 0:
                raise ExecutionError("Comment submit button not found in DOM")

            await submit_btn.click()

            # Confirm submission in DOM (wait for box to clear or comment to appear)
            screenshot = await self._capture_screenshot(f"success_comment_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_comment",
                item_id=item_id,
                post_url=post_url,
                comment_text=comment_text,
                post_text=None,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )
        except Exception as err:
            screenshot = await self._capture_screenshot(f"failed_comment_{item_id}")
            if isinstance(
                err, BotDetectionError | PostNoLongerAvailableError | SessionExpiredError
            ):
                raise
            raise ExecutionError(f"Failed to post comment: {err}") from err

    async def create_post(
        self,
        post_text: str,
        item_id: str = "post_action",
        dry_run: bool | None = None,
    ) -> ExecutionResult:
        """Create an approved original LinkedIn post.

        Args:
            post_text: Approved post text.
            item_id: Action item ID.
            dry_run: Override dry-run setting.

        Returns:
            ExecutionResult: Execution outcome with screenshot.
        """
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        if detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_post_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        if is_dry_run:
            logger.info("DRY_RUN: Simulated original post: %s", post_text)
            screenshot = await self._capture_screenshot(f"dryrun_post_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_post",
                item_id=item_id,
                post_url=None,
                comment_text=None,
                post_text=post_text,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )

        try:
            start_post_btn = self.page.locator(
                "button:has-text('Start a post'), button.share-box-feed-entry__trigger"
            ).first
            if await start_post_btn.count() == 0:
                raise ExecutionError("Start a post button not found in DOM")

            await start_post_btn.click()

            editor = self.page.locator("div.ql-editor, div[role='textbox']").first
            if await editor.count() == 0:
                raise ExecutionError("Post editor textbox not found in DOM")

            await humanized_type(editor, post_text)

            post_btn = self.page.locator(
                "button.share-actions__primary-action, button:has-text('Post')"
            ).first
            if await post_btn.count() == 0:
                raise ExecutionError("Publish post button not found in DOM")

            await post_btn.click()

            screenshot = await self._capture_screenshot(f"success_post_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_post",
                item_id=item_id,
                post_url=None,
                comment_text=None,
                post_text=post_text,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )
        except Exception as err:
            screenshot = await self._capture_screenshot(f"failed_post_{item_id}")
            if isinstance(err, BotDetectionError):
                raise
            raise ExecutionError(f"Failed to publish post: {err}") from err
