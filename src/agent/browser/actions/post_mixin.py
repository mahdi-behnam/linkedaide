"""Post creation action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.browser import stealth
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    SessionExpiredError,
    SubmissionVerificationError,
)
from agent.models import ExecutionResult, MediaAttachment

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from agent.browser.biometrics import BiometricController
    from agent.config import Settings

logger = logging.getLogger(__name__)


class PostMixin:
    """Mixin providing original post creation and submission verification."""

    page: Page
    settings: Settings
    biometrics: BiometricController

    # Methods provided by VerificationMixin
    _capture_screenshot: Any
    _upload_screenshot_to_r2: Any
    _capture_telemetry: Any
    _check_error_toasts: Any
    _refresh_and_persist_session: Any

    async def _verify_post_submission(
        self,
        modal_loc: Locator | None,
        post_text: str,
        item_id: str,
        timeout: float = 8.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Actively verify post creation in the DOM."""
        deadline = time.monotonic() + max(0.0, timeout)

        while True:
            if stealth.detect_challenge_page(self.page):
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
        await self._capture_telemetry(
            trigger="create_post_verification_timeout",
            item_id=item_id,
        )
        raise SubmissionVerificationError(
            f"Post creation could not be verified in DOM within {timeout:.1f}s (modal remained open)",
            details={"screenshot_path": screenshot, "item_id": item_id},
        )

    async def create_post(
        self,
        post_text: str,
        item_id: str = "post_action",
        dry_run: bool | None = None,
        verification_timeout: float = 8.0,
        media: list[MediaAttachment] | None = None,
    ) -> ExecutionResult:
        """Create an approved original LinkedIn post."""
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        if stealth.detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_post_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        if is_dry_run:
            media_info = f" with {len(media)} media attachment(s)" if media else ""
            logger.info("DRY_RUN: Simulated original post%s: %s", media_info, post_text)
            screenshot = await self._capture_screenshot(f"dryrun_post_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(screenshot, f"dryrun_post_{item_id}")
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
            start_post_selector = (
                "div[role='button']:has-text('Start a post'), "
                "button:has-text('Start a post'), "
                "button.share-box-feed-entry__trigger, "
                "[data-view-name*='share-box'] [role='button']"
            )
            start_post_btn = self.page.locator(start_post_selector).first
            if await start_post_btn.count() == 0:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=start_post_selector,
                )
                raise ExecutionError("Start a post button not found in DOM")

            await self.biometrics.click_element(start_post_btn)

            modal_loc = self.page.locator(
                "div.share-box-modal, div.artdeco-modal[role='dialog'], div.share-creation-state"
            ).first

            editor_selector = "div.tiptap.ProseMirror, div.ql-editor, div[role='textbox']"
            editor = self.page.locator(editor_selector).first
            if await editor.count() == 0:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=editor_selector,
                )
                raise ExecutionError("Post editor textbox not found in DOM")

            await self.biometrics.type_text(editor, post_text)

            if media:
                file_paths = [m.file_url for m in media if m.file_url and Path(m.file_url).exists()]
                if file_paths:
                    file_input = self.page.locator("input[type='file']").first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(file_paths)
                        await asyncio.sleep(1.0)
                        next_btn = self.page.locator(
                            "button:has-text('Next'), button[aria-label='Next'], button:has-text('Done')"
                        ).first
                        if await next_btn.count() > 0:
                            await self.biometrics.click_element(next_btn)
                            await asyncio.sleep(0.5)

            post_btn_selector = "button.share-actions__primary-action, button:has-text('Post')"
            post_btn = self.page.locator(post_btn_selector).first
            if await post_btn.count() == 0:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=post_btn_selector,
                )
                raise ExecutionError("Publish post button not found in DOM")

            await self.biometrics.click_element(post_btn)

            # Active DOM post-submission verification
            await self._verify_post_submission(
                modal_loc=modal_loc,
                post_text=post_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

            await self._refresh_and_persist_session()
            screenshot = await self._capture_screenshot(f"success_post_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(screenshot, f"success_post_{item_id}")
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
