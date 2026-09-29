"""Playwright browser action executor for comments and posts."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.browser.biometrics import BiometricController
from agent.browser.session_keeper import refresh_and_persist_session
from agent.browser.stealth import (
    detect_challenge_page,
    humanized_dwell,
    humanized_type,  # noqa: F401
    is_authwall_or_login,
    wait_for_login_redirect,
)
from agent.browser.telemetry import capture_dom_telemetry
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

    from agent.state.base import BaseStateStore

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes validated LinkedIn write and read actions via Playwright."""

    def __init__(
        self,
        page: Page,
        settings: Settings,
        debug_dir: Path | None = None,
        state_store: BaseStateStore | None = None,
        biometrics: BiometricController | None = None,
    ) -> None:
        self.page = page
        self.settings = settings
        self.debug_dir = debug_dir or (Path("debug") / "screenshots")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = state_store
        self.biometrics = biometrics or BiometricController(page)

    async def refresh_session(self) -> dict[str, Any] | None:
        """Refresh and persist authenticated session state."""
        return await self._refresh_and_persist_session()

    async def _refresh_and_persist_session(self) -> dict[str, Any] | None:
        """Refresh and persist authenticated session state after successful action execution."""
        enc_key = getattr(self.settings, "session_encryption_key", None)
        if not enc_key:
            return None

        ctx = getattr(self.page, "context", None)
        if not ctx:
            return None

        store = self.state_store
        if store is None:
            try:
                from agent.state import get_state_store

                store = get_state_store(self.settings, Path.cwd())
            except Exception:
                store = None

        if store is None:
            return None

        try:
            return await refresh_and_persist_session(
                context=ctx,
                session_encryption_key=enc_key,
                state_store=store,
            )
        except Exception as err:
            logger.warning("Rolling cookie keepalive refresh failed non-fatally: %s", err)
            return None


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
            return await capture_dom_telemetry(self.page, **call_kwargs)
        except Exception as err:
            logger.debug("Failed capturing DOM telemetry for %s: %s", trigger, err)
            return None

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
        await self._capture_telemetry(
            trigger="comment_verification_timeout",
            item_id=item_id,
        )
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
        await self._capture_telemetry(
            trigger="create_post_verification_timeout",
            item_id=item_id,
        )
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
            is_authenticated = await wait_for_login_redirect(self.page, timeout=15.0)
            if not is_authenticated:
                raise SessionExpiredError(
                    f"LinkedIn session expired; redirected to {self.page.url}"
                )

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
            "article, div[id^='expanded'][id*='FEED'], div.feed-shared-update-v2, "
            "div.feed-shared-update-v2__content, div[componentkey], a[href*='/in/']"
        )
        return await post_article.count() > 0

    async def react_to_post(
        self,
        reaction_type: str = "like",
        item_id: str = "item_action",
        dry_run: bool | None = None,
    ) -> bool:
        """React to a LinkedIn post with humanized dwell and graceful degradation.

        Args:
            reaction_type: Reaction name ('like', 'insightful', 'celebrate', 'support', 'love', 'funny').
            item_id: Action item ID for audit logging.
            dry_run: Override dry-run setting.

        Returns:
            bool: True if reaction succeeded, was skipped because already reacted, or dry-run simulated.
        """
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run

        if detect_challenge_page(self.page):
            await self._capture_screenshot(f"challenge_react_{item_id}")
            raise BotDetectionError(f"Bot challenge during reaction check: {self.page.url}")

        if is_authwall_or_login(self.page):
            raise SessionExpiredError(
                f"LinkedIn session expired during reaction check; redirected to {self.page.url}"
            )

        if is_dry_run:
            logger.info("DRY_RUN: Simulated reaction '%s' on %s", reaction_type, self.page.url)
            return True

        try:
            react_btn = self.page.locator(
                "button[aria-label*='Reaction button state' i], button[aria-label*='React Like'], "
                "button[aria-label*='Like' i], button.react-button__trigger, button.reactions-react-button, "
                "button.feed-shared-social-action-bar__action-button:has-text('Like'), button:has-text('Like')"
            ).first

            if await react_btn.count() == 0:
                logger.warning("Reaction button not found on %s", self.page.url)
                return False

            # Check if already reacted
            aria_pressed = (await react_btn.get_attribute("aria-pressed") or "").strip().lower()
            aria_label = (await react_btn.get_attribute("aria-label") or "").lower()
            is_already_reacted = (
                aria_pressed in ("true", "1")
                or "unreact" in aria_label
                or "unlike" in aria_label
                or ("reaction button state" in aria_label and "no reaction" not in aria_label)
            )
            if is_already_reacted:
                logger.info(
                    "Post %s already reacted (%s); skipping click", self.page.url, aria_label
                )
                return True

            norm_type = reaction_type.strip().lower()
            if norm_type in ("", "like"):
                await self.biometrics.click_element(react_btn)
                return True

            # Non-default reaction (e.g. insightful, celebrate, etc.)
            try:
                await react_btn.hover()
                await asyncio.sleep(0.4)
                reaction_menu_item = self.page.locator(
                    f"button[aria-label*='{norm_type.capitalize()}' i], "
                    f"button[data-test-reaction-type='{norm_type}'], "
                    f"div.reactions-menu button:has-text('{norm_type.capitalize()}')"
                ).first

                if await reaction_menu_item.count() > 0:
                    await self.biometrics.click_element(reaction_menu_item)
                    return True
                else:
                    logger.warning(
                        "Specific reaction button '%s' not found, falling back to Like", norm_type
                    )
                    await self.biometrics.click_element(react_btn)
                    return True
            except Exception as e:
                logger.warning(
                    "Failed to trigger specific reaction '%s' (%s), falling back to Like",
                    norm_type,
                    e,
                )
                await self.biometrics.click_element(react_btn)
                return True

        except (BotDetectionError, SessionExpiredError):
            raise
        except Exception as err:
            logger.warning("Non-fatal error during reaction attempt on %s: %s", self.page.url, err)
            return False

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
        """Post an approved comment on a LinkedIn post.

        Args:
            post_url: Target post URL.
            comment_text: Approved comment text.
            item_id: Action item ID for audit logging.
            dry_run: Override dry-run setting.
            verification_timeout: Maximum timeout in seconds to verify DOM outcome.
            reaction_type: Optional reaction type ('like', 'insightful', etc.) to perform before commenting.
            simulate_dwell: Whether to simulate humanized reading/dwelling pauses.

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
                    await humanized_dwell(1.5, 3.5)
                await self.react_to_post(
                    reaction_type=effective_reaction,
                    item_id=item_id,
                    dry_run=False,
                )
                if simulate_dwell:
                    await humanized_dwell(1.0, 2.5)

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
