"""Comment action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agent.browser import stealth
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    PostNoLongerAvailableError,
    SessionExpiredError,
    SubmissionVerificationError,
)
from agent.models import ExecutionResult

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from agent.browser.biometrics import BiometricController
    from agent.config import Settings

logger = logging.getLogger(__name__)


class CommentMixin:
    """Mixin providing comment creation and submission verification."""

    page: Page
    settings: Settings
    biometrics: BiometricController

    # Methods provided by VerificationMixin & ReactionMixin
    _capture_screenshot: Any
    _upload_screenshot_to_r2: Any
    _capture_telemetry: Any
    _check_error_toasts: Any
    _refresh_and_persist_session: Any
    verify_post_exists: Any
    react_to_post: Any

    async def _verify_comment_submission(
        self,
        comment_box: Locator,
        submit_btn: Locator,
        comment_text: str,
        item_id: str,
        timeout: float = 6.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Actively verify comment submission in the DOM."""
        deadline = time.monotonic() + max(0.0, timeout)
        snippet = comment_text[:80].strip()

        while True:
            if stealth.detect_challenge_page(self.page):
                await self._capture_screenshot(f"challenge_{item_id}")
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
        await self._capture_telemetry(
            trigger="comment_verification_timeout",
            item_id=item_id,
        )
        raise SubmissionVerificationError(
            f"Comment submission could not be verified in DOM within {timeout:.1f}s",
            details={"screenshot_path": screenshot, "item_id": item_id},
        )

    async def post_comment(
        self,
        post_url: str,
        comment_text: str,
        item_id: str = "item_action",
        dry_run: bool | None = None,
        verification_timeout: float = 6.0,
        reaction_type: str | None = None,
        simulate_dwell: bool = True,
    ) -> ExecutionResult:
        """Post an approved comment on a LinkedIn post."""
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        if stealth.detect_challenge_page(self.page):
            await self._capture_screenshot(f"challenge_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        # Verify target post exists
        post_exists = await self.verify_post_exists(post_url)
        if not post_exists:
            screenshot = await self._capture_screenshot(f"missing_post_{item_id}")
            raise PostNoLongerAvailableError(f"Post at {post_url} is no longer available")

        # Determine effective reaction
        effective_reaction = reaction_type or (
            self.settings.default_reaction_type
            if self.settings.enable_pre_comment_reaction
            else None
        )

        # Dry run safety guarantee: zero write submission
        if is_dry_run:
            if effective_reaction:
                logger.info("DRY_RUN: Simulated reaction '%s' on %s", effective_reaction, post_url)
            logger.info("DRY_RUN: Simulated comment on %s: %s", post_url, comment_text)
            screenshot = await self._capture_screenshot(f"dryrun_comment_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(
                screenshot, f"dryrun_comment_{item_id}"
            )
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
            # Pre-comment reaction simulation if enabled
            if effective_reaction:
                if simulate_dwell:
                    await stealth.humanized_dwell(1.5, 3.5)
                await self.react_to_post(
                    reaction_type=effective_reaction,
                    item_id=item_id,
                    dry_run=False,
                )
                if simulate_dwell:
                    await stealth.humanized_dwell(1.0, 2.5)

            # Locate comment button
            comment_btn = self.page.locator(
                "button[aria-label*='Comment'], button[aria-label*='comment' i], "
                "button.comment-button, "
                "button.feed-shared-social-action-bar__action-button:has-text('Comment'), "
                "button:has-text('Comment')"
            ).first
            if await comment_btn.count() > 0:
                await self.biometrics.click_element(comment_btn)

            comment_box_selector = (
                "div[data-testid='ui-core-tiptap-text-editor-wrapper'] div.tiptap.ProseMirror, "
                "div.tiptap.ProseMirror, "
                "div[role='textbox'][aria-label*='comment' i], "
                "div[role='textbox'][contenteditable='true'], "
                "div.ql-editor, textarea[name='comment']"
            )
            comment_box = self.page.locator(comment_box_selector).first
            if await comment_box.count() == 0:
                await self._capture_telemetry(
                    trigger="comment_box_drift",
                    item_id=item_id,
                    target_selector=comment_box_selector,
                )
                raise ExecutionError("Comment input box not found in DOM")

            await self.biometrics.type_text(comment_box, comment_text)

            submit_btn_selector = (
                "button[componentkey*='commentButtonSection'], "
                "div[id*='commentButtonSection'] button, "
                "button.comments-comment-box__submit-button, "
                "div.comments-comment-box button[type='submit'], "
                "button[type='submit']:has-text('Comment'), "
                "button[type='submit']:has-text('Post'), "
                "button:has-text('Comment')"
            )
            submit_btn = self.page.locator(submit_btn_selector).first
            if await submit_btn.count() == 0:
                await self._capture_telemetry(
                    trigger="comment_submit_btn_drift",
                    item_id=item_id,
                    target_selector=submit_btn_selector,
                )
                raise ExecutionError("Comment submit button not found in DOM")

            await self.biometrics.click_element(submit_btn)

            # Confirm submission in DOM (wait for box to clear or comment to appear)
            await self._verify_comment_submission(
                comment_box=comment_box,
                submit_btn=submit_btn,
                comment_text=comment_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

            await self._refresh_and_persist_session()
            screenshot = await self._capture_screenshot(f"success_comment_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(
                screenshot, f"success_comment_{item_id}"
            )
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
