"""Post creation action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from agent.browser import stealth
from agent.browser.actions.base import _safe_scroll
from agent.browser.selectors import LINKEDIN_SELECTORS
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    SelectorDriftError,
    SessionExpiredError,
    SubmissionVerificationError,
)
from agent.models import ExecutionResult, MediaAttachment

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from agent.browser.biometrics import BiometricController
    from agent.browser.selectors import SelfHealingSelectorEngine
    from agent.config import Settings

logger = logging.getLogger(__name__)


class PostMixin:
    """Mixin providing original post creation and submission verification."""

    page: Page
    settings: Settings
    biometrics: BiometricController
    selector_engine: SelfHealingSelectorEngine

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

    async def _resolve_media_file_paths(
        self, media: list[MediaAttachment]
    ) -> tuple[list[str], list[Path]]:
        """Resolve media attachments to local paths, downloading remote URLs if needed.

        Args:
            media: List of media attachment descriptors.

        Returns:
            tuple[list[str], list[Path]]: File paths for input upload and temp files to clean up.
        """
        file_paths: list[str] = []
        temp_files: list[Path] = []

        for m in media:
            if not m.file_url:
                continue
            raw_url = m.file_url.strip()
            if raw_url.startswith(("http://", "https://")):
                suffix = Path(m.file_name).suffix or Path(raw_url.split("?")[0]).suffix or ".tmp"
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        temp_path = Path(tmp.name)
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        resp = await client.get(raw_url)
                        resp.raise_for_status()
                        temp_path.write_bytes(resp.content)
                    temp_files.append(temp_path)
                    file_paths.append(str(temp_path))
                    logger.info("Downloaded remote media attachment %s to %s", raw_url, temp_path)
                except Exception as err:
                    logger.warning(
                        "Failed to download remote media attachment %s: %s", raw_url, err
                    )
            elif Path(raw_url).exists():
                file_paths.append(raw_url)
            else:
                logger.warning("Media attachment path not found: %s", raw_url)

        return file_paths, temp_files

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

        temp_media_files: list[Path] = []
        try:
            feed_url = "https://www.linkedin.com/feed/"
            current_url = self.page.url if isinstance(self.page.url, str) else ""
            if not current_url or "linkedin.com/feed" not in current_url:
                try:
                    res = self.page.goto(feed_url, wait_until="domcontentloaded", timeout=30000)
                    if hasattr(res, "__await__"):
                        await res
                    await stealth.humanized_dwell(1.0, 2.0)
                except Exception as err:
                    logger.warning("Navigation to feed during create_post failed: %s", err)

            start_post_selector = (
                "div[role='button']:has-text('Start a post'), "
                "div[role='button'][aria-label*='Start a post'], "
                "button:has-text('Start a post'), "
                "button.share-box-feed-entry__trigger, "
                "[data-view-name*='share-box'] [role='button']"
            )
            try:
                start_post_btn, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "post_input",
                    candidates=[start_post_selector, *LINKEDIN_SELECTORS.get("post_input", [])],
                )
                await _safe_scroll(start_post_btn)
            except SelectorDriftError as err:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=start_post_selector,
                )
                raise ExecutionError("Start a post button not found in DOM") from err

            await self.biometrics.click_element(start_post_btn)
            await asyncio.sleep(1.2)

            try:
                modal_loc, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "post_modal",
                )
            except SelectorDriftError:
                modal_loc = self.page.locator(
                    "div[role='dialog'], div.share-box-modal, div.artdeco-modal[role='dialog'], div.share-creation-state"
                ).first

            editor_selector = (
                "div.tiptap.ProseMirror[contenteditable='true'], "
                "div[data-testid='ui-core-tiptap-text-editor-wrapper'] div.tiptap.ProseMirror, "
                "div[componentkey='ShareBox_textEditor'], "
                "div.tiptap.ProseMirror, "
                "div[role='textbox'], "
                "div.ql-editor"
            )
            try:
                editor, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "post_editor",
                    candidates=[editor_selector, *LINKEDIN_SELECTORS.get("post_editor", [])],
                )
                await _safe_scroll(editor)
            except SelectorDriftError as err:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=editor_selector,
                )
                raise ExecutionError("Post editor textbox not found in DOM") from err

            await self.biometrics.type_text(editor, post_text)

            if media:
                file_paths, temp_media_files = await self._resolve_media_file_paths(media)
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

            post_btn_selector = (
                "button:has-text('Post'), "
                "button.share-actions__primary-action, "
                "button[aria-label='Post']"
            )
            try:
                post_btn, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "post_submit",
                    candidates=[post_btn_selector, *LINKEDIN_SELECTORS.get("post_submit", [])],
                )
                await _safe_scroll(post_btn)
            except SelectorDriftError as err:
                await self._capture_telemetry(
                    trigger="create_post_ui_drift",
                    item_id=item_id,
                    target_selector=post_btn_selector,
                )
                raise ExecutionError("Publish post button not found in DOM") from err

            await self.biometrics.click_element(post_btn)

            # Active DOM post-submission verification
            await self._verify_post_submission(
                modal_loc=modal_loc,
                post_text=post_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

            # Resolve published post verification URL
            published_url = None
            try:
                view_link = self.page.locator(
                    "div.artdeco-toast a[href*='/feed/update/'], a:has-text('View post'), a:has-text('View update')"
                )
                if await view_link.count() > 0:
                    href = await view_link.first.get_attribute("href")
                    if href:
                        published_url = (
                            href if href.startswith("http") else f"https://www.linkedin.com{href}"
                        )
                elif "/feed/update/" in (self.page.url or ""):
                    published_url = self.page.url
            except Exception as e:
                logger.debug("Could not resolve published post URL: %s", e)

            await self._refresh_and_persist_session()
            screenshot = await self._capture_screenshot(f"success_post_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(screenshot, f"success_post_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_post",
                item_id=item_id,
                post_url=published_url,
                published_post_url=published_url,
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
        finally:
            for tf in temp_media_files:
                try:
                    tf.unlink(missing_ok=True)
                except Exception as cleanup_err:
                    logger.debug("Failed to remove temp media file %s: %s", tf, cleanup_err)
