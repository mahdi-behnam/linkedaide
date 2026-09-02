"""Playwright browser action executor for comments and posts."""

from __future__ import annotations

import asyncio
import logging
import time
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
    SubmissionVerificationError,
)
from agent.models.schemas import ExecutionResult

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

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

    async def _check_error_toasts(self) -> str | None:
        """Check for LinkedIn error toast notifications or inline error alerts.

        Returns:
            str | None: Error message text if an error banner/toast is visible, else None.
        """
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

    async def _verify_comment_submission(
        self,
        comment_box: Locator,
        submit_btn: Locator,
        comment_text: str,
        item_id: str,
        timeout: float = 6.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Actively verify comment submission in the DOM.

        Checks for:
        1. Bot challenge / security checkpoint -> BotDetectionError
        2. LinkedIn error toast/feedback -> SubmissionVerificationError
        3. Comment text appearing in the comment list/thread (Primary confirmation)
        4. Comment box cleared AND submit button disabled/hidden (Secondary confirmation)

        Args:
            comment_box: Playwright Locator for the comment input element.
            submit_btn: Playwright Locator for the comment submit button.
            comment_text: Submitted comment text.
            item_id: Action item ID for diagnostic artifacts.
            timeout: Maximum verification timeout in seconds.
            poll_interval: Polling interval in seconds.

        Returns:
            bool: True if submission is confirmed in the DOM.

        Raises:
            BotDetectionError: If a security checkpoint/challenge is encountered.
            SubmissionVerificationError: If submission was rejected or could not be verified.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        snippet = comment_text[:80].strip()

        while True:
            if detect_challenge_page(self.page):
                screenshot = await self._capture_screenshot(f"challenge_{item_id}")
                raise BotDetectionError(
                    f"Bot detection challenge during comment verification on {self.page.url}"
                )

            error_msg = await self._check_error_toasts()
            if error_msg:
                screenshot = await self._capture_screenshot(f"failed_verify_comment_{item_id}")
                raise SubmissionVerificationError(
                    f"LinkedIn comment submission rejected: {error_msg}",
                    details={
                        "screenshot_path": screenshot,
                        "item_id": item_id,
                        "error": error_msg,
                    },
                )

            # Signal 1: Comment text rendered in thread / comments list
            if snippet:
                comment_loc = self.page.locator(
                    "article.comments-comment-item, div.comments-comment-item, "
                    "div.comments-comment-item__main-content, div.feed-shared-update-v2__comments-container, "
                    ".comments-comments-list, div.comments-comments-list__comment-item"
                )
                try:
                    if hasattr(comment_loc, "filter"):
                        try:
                            if await comment_loc.filter(has_text=snippet).count() > 0:
                                return True
                        except Exception:
                            pass
                    if await comment_loc.count() > 0:
                        try:
                            text_content = await comment_loc.first.inner_text()
                            if snippet in text_content:
                                return True
                        except Exception:
                            pass
                except Exception:
                    pass

            # Signal 2: Comment box cleared and submit button disabled or hidden
            is_box_cleared = False
            try:
                box_text = await comment_box.inner_text()
                if not box_text.strip():
                    is_box_cleared = True
            except Exception:
                pass

            is_btn_inactive = False
            try:
                btn_count = await submit_btn.count()
                if btn_count == 0:
                    is_btn_inactive = True
                else:
                    if hasattr(submit_btn, "is_disabled") and await submit_btn.is_disabled():
                        is_btn_inactive = True
                    elif hasattr(submit_btn, "is_visible") and not await submit_btn.is_visible():
                        is_btn_inactive = True
                    elif (await submit_btn.get_attribute("disabled")) is not None:
                        is_btn_inactive = True
            except Exception:
                pass

            if is_box_cleared and is_btn_inactive:
                return True

            if time.monotonic() >= deadline:
                break

            remaining = deadline - time.monotonic()
            await asyncio.sleep(min(poll_interval, max(0.01, remaining)))

        screenshot = await self._capture_screenshot(f"failed_verify_comment_{item_id}")
        raise SubmissionVerificationError(
            f"Comment submission could not be verified in DOM within {timeout:.1f}s",
            details={"screenshot_path": screenshot, "item_id": item_id},
        )

    async def _verify_post_submission(
        self,
        modal_loc: Locator | None,
        post_text: str,
        item_id: str,
        timeout: float = 8.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Actively verify post creation in the DOM.

        Checks for:
        1. Bot challenge / security checkpoint -> BotDetectionError
        2. LinkedIn error toast or modal inline feedback -> SubmissionVerificationError
        3. Creation modal dismissed / closed (Primary confirmation)
        4. Success toast banner appeared (Supplementary confirmation)

        Args:
            modal_loc: Playwright Locator for the post creation dialog/modal.
            post_text: Submitted post text.
            item_id: Action item ID for diagnostic artifacts.
            timeout: Maximum verification timeout in seconds.
            poll_interval: Polling interval in seconds.

        Returns:
            bool: True if post creation is confirmed in the DOM.

        Raises:
            BotDetectionError: If a security checkpoint/challenge is encountered.
            SubmissionVerificationError: If creation was rejected or could not be verified.
        """
        deadline = time.monotonic() + max(0.0, timeout)

        while True:
            if detect_challenge_page(self.page):
                screenshot = await self._capture_screenshot(f"challenge_post_{item_id}")
                raise BotDetectionError(
                    f"Bot detection challenge during post verification on {self.page.url}"
                )

            error_msg = await self._check_error_toasts()
            if error_msg:
                screenshot = await self._capture_screenshot(f"failed_verify_post_{item_id}")
                raise SubmissionVerificationError(
                    f"LinkedIn post creation rejected: {error_msg}",
                    details={
                        "screenshot_path": screenshot,
                        "item_id": item_id,
                        "error": error_msg,
                    },
                )

            # Signal 1: Creation modal dismissed / closed
            modal_closed = False
            if modal_loc is not None:
                try:
                    count = await modal_loc.count()
                    if count == 0:
                        modal_closed = True
                    elif hasattr(modal_loc, "is_visible") and not await modal_loc.is_visible():
                        modal_closed = True
                except Exception:
                    pass
            else:
                dialog_loc = self.page.locator(
                    "div.share-box-modal, div.artdeco-modal[role='dialog'], div.share-creation-state"
                )
                try:
                    count = await dialog_loc.count()
                    if count == 0:
                        modal_closed = True
                    elif hasattr(dialog_loc, "is_visible") and not await dialog_loc.is_visible():
                        modal_closed = True
                except Exception:
                    pass

            if modal_closed:
                return True

            # Signal 2: Success toast / confirmation appeared
            success_toast = self.page.locator(
                "div.artdeco-toast-item--success, div.artdeco-toast:has-text('Post successful'), "
                "div.artdeco-toast:has-text('Your post was shared')"
            )
            try:
                if await success_toast.count() > 0:
                    first_success = success_toast.first
                    if not hasattr(first_success, "is_visible") or await first_success.is_visible():
                        return True
            except Exception:
                pass

            if time.monotonic() >= deadline:
                break

            remaining = deadline - time.monotonic()
            await asyncio.sleep(min(poll_interval, max(0.01, remaining)))

        screenshot = await self._capture_screenshot(f"failed_verify_post_{item_id}")
        raise SubmissionVerificationError(
            f"Post creation could not be verified in DOM within {timeout:.1f}s (modal remained open)",
            details={"screenshot_path": screenshot, "item_id": item_id},
        )

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
        verification_timeout: float = 6.0,
    ) -> ExecutionResult:
        """Post an approved comment on a LinkedIn post.

        Args:
            post_url: Target post URL.
            comment_text: Approved comment text.
            item_id: Action item ID for audit logging.
            dry_run: Override dry-run setting.
            verification_timeout: Maximum timeout in seconds to verify DOM outcome.

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
            await self._verify_comment_submission(
                comment_box=comment_box,
                submit_btn=submit_btn,
                comment_text=comment_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

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
            if isinstance(
                err,
                BotDetectionError
                | PostNoLongerAvailableError
                | SessionExpiredError
                | SubmissionVerificationError,
            ):
                raise
            screenshot = await self._capture_screenshot(f"failed_comment_{item_id}")
            raise ExecutionError(
                f"Failed to post comment: {err}",
                details={"screenshot_path": screenshot, "item_id": item_id},
            ) from err

    async def create_post(
        self,
        post_text: str,
        item_id: str = "post_action",
        dry_run: bool | None = None,
        verification_timeout: float = 8.0,
    ) -> ExecutionResult:
        """Create an approved original LinkedIn post.

        Args:
            post_text: Approved post text.
            item_id: Action item ID.
            dry_run: Override dry-run setting.
            verification_timeout: Maximum timeout in seconds to verify DOM outcome.

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

            modal_loc = self.page.locator(
                "div.share-box-modal, div.artdeco-modal[role='dialog'], div.share-creation-state"
            ).first

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

            # Active DOM post-submission verification
            await self._verify_post_submission(
                modal_loc=modal_loc,
                post_text=post_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

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
            if isinstance(
                err,
                BotDetectionError | SessionExpiredError | SubmissionVerificationError,
            ):
                raise
            screenshot = await self._capture_screenshot(f"failed_post_{item_id}")
            raise ExecutionError(
                f"Failed to publish post: {err}",
                details={"screenshot_path": screenshot, "item_id": item_id},
            ) from err
