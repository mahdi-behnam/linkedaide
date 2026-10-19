"""Connection outreach action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
from agent.models import ExecutionResult

if TYPE_CHECKING:
    from playwright.async_api import Page

    from agent.browser.biometrics import BiometricController
    from agent.browser.selectors import SelfHealingSelectorEngine
    from agent.config import Settings

logger = logging.getLogger(__name__)


class ConnectionMixin:
    """Mixin providing personalized connection requests and verification."""

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

    async def _verify_connection_sent(
        self,
        item_id: str,
        timeout: float = 6.0,
        poll_interval: float = 0.25,
    ) -> bool:
        """Actively verify connection request invitation submission in the DOM."""
        deadline = time.monotonic() + max(0.0, timeout)

        while True:
            if stealth.detect_challenge_page(self.page):
                screenshot = await self._capture_screenshot(f"challenge_verify_conn_{item_id}")
                raise BotDetectionError(
                    f"Bot challenge during connection verification on {self.page.url}"
                )

            error_msg = await self._check_error_toasts()
            if error_msg:
                screenshot = await self._capture_screenshot(f"failed_verify_conn_{item_id}")
                raise SubmissionVerificationError(
                    f"LinkedIn connection request rejected: {error_msg}",
                    details={
                        "screenshot_path": screenshot,
                        "item_id": item_id,
                        "error": error_msg,
                    },
                )

            # Signal 1: "Pending" button appears on profile
            pending_loc = self.page.locator(
                "button:has-text('Pending'), button[aria-label*='Pending'], button[aria-label*='Invitation sent'], a:has-text('Pending'), a[aria-label*='Pending']"
            )
            try:
                if await pending_loc.count() > 0:
                    return True
            except Exception:
                pass

            # Signal 2: Success toast appears
            toast_loc = self.page.locator(
                "div.artdeco-toast-item--success, div.artdeco-toast:has-text('Invitation sent'), div.artdeco-toast:has-text('Your invitation')"
            )
            try:
                if await toast_loc.count() > 0:
                    return True
            except Exception:
                pass

            if time.monotonic() >= deadline:
                break

            remaining = deadline - time.monotonic()
            await asyncio.sleep(min(poll_interval, max(0.01, remaining)))

        screenshot = await self._capture_screenshot(f"failed_verify_conn_{item_id}")
        await self._capture_telemetry(
            trigger="connection_request_verification_timeout",
            item_id=item_id,
        )
        raise SubmissionVerificationError(
            f"Connection request could not be verified in DOM within {timeout:.1f}s",
            details={"screenshot_path": screenshot, "item_id": item_id},
        )

    async def send_connection_request(
        self,
        profile_url: str,
        note_text: str | None = None,
        item_id: str = "conn_action",
        dry_run: bool | None = None,
        verification_timeout: float = 6.0,
        note: str | None = None,
    ) -> ExecutionResult:
        """Send a personalized LinkedIn connection invitation request."""
        note_text = note_text if note_text is not None else note
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        # 1. Validate note length limit (strict 300 char safety constraint)
        if note_text is not None and len(note_text) > 300:
            raise ExecutionError(
                f"Connection note exceeds 300 characters limit ({len(note_text)} chars)"
            )

        # 2. Challenge page detection
        if stealth.detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_connect_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        # 3. Dry-run safety bypass
        if is_dry_run:
            logger.info(
                "DRY_RUN: Simulated connection request to %s (note_length=%s)",
                profile_url,
                len(note_text) if note_text else 0,
            )
            screenshot = await self._capture_screenshot(f"dryrun_connect_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(
                screenshot, f"dryrun_connect_{item_id}"
            )
            return ExecutionResult(
                success=True,
                action_type="send_connection",
                item_id=item_id,
                post_url=profile_url,
                comment_text=note_text,
                post_text=None,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )

        try:
            # 4. Navigate to profile URL if not already there
            clean_profile = profile_url.split("?")[0].rstrip("/")
            clean_page_url = self.page.url.split("?")[0].rstrip("/")
            if clean_page_url != clean_profile:
                await self.page.goto(
                    profile_url,
                    referer="https://www.linkedin.com/feed/",
                    wait_until="domcontentloaded",
                )
                await stealth.humanized_dwell(1.0, 2.0)

            if stealth.detect_challenge_page(self.page):
                screenshot = await self._capture_screenshot(f"challenge_connect_{item_id}")
                raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

            if stealth.is_authwall_or_login(self.page):
                if not await stealth.wait_for_login_redirect(self.page, timeout=5.0):
                    raise SessionExpiredError(
                        f"LinkedIn session expired navigating to {profile_url}"
                    )

            # 5. Detect "Connect" button directly or via "More actions"
            connect_selector = (
                "main section[aria-label='Primary content'] a[aria-label*='to connect' i], "
                "main section[aria-label='Primary content'] button[aria-label*='to connect' i], "
                "main section[aria-label='Primary content'] button:has-text('Connect'), "
                "main div[id*='Topcard'] a[aria-label*='to connect' i], "
                "main div[id*='Topcard'] button:has-text('Connect'), "
                "button[data-control-name='connect'], "
                "button.pvs-profile-actions__action[data-test-connect-button], "
                "button[aria-label*='Invite'][aria-label*='to connect'], "
                "a[aria-label*='Invite'][aria-label*='to connect'], "
                "button.pvs-profile-actions__action:has-text('Connect'), "
                "div.ph5 button:has-text('Connect'), "
                "button:has-text('Connect'), "
                "a:has-text('Connect')"
            )
            found_connect = False
            try:
                connect_btn, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "connect_btn",
                    candidates=[connect_selector, *LINKEDIN_SELECTORS.get("connect_btn", [])],
                )
                await _safe_scroll(connect_btn)
                found_connect = True
                await self.biometrics.click_element(connect_btn)
            except SelectorDriftError:
                found_connect = False

            if not found_connect:
                # Try "More actions" dropdown
                more_selector = (
                    "main section[aria-label='Primary content'] button:has-text('More'), "
                    "main div[id*='Topcard'] button:has-text('More'), "
                    "main section[aria-label='Primary content'] button[aria-label='More actions'], "
                    "main div[id*='Topcard'] button[aria-label='More actions'], "
                    "div.pvs-profile-actions button:has-text('More'), "
                    "main button[aria-label='More actions'], "
                    "main button[aria-label='More'], "
                    "main button:has-text('More'), "
                    "button[aria-label='More actions'], "
                    "button[aria-label='More'], "
                    "button:has-text('More')"
                )
                try:
                    more_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "more_actions_btn",
                        candidates=[more_selector, *LINKEDIN_SELECTORS.get("more_actions_btn", [])],
                    )
                    await _safe_scroll(more_btn)
                    await self.biometrics.click_element(more_btn)
                    await asyncio.sleep(0.5)

                    dropdown_connect_selector = (
                        "div[role='menu'] [aria-label*='to connect'], "
                        "div[role='menu'] :has-text('Connect'), "
                        "[role='menuitem']:has-text('Connect'), "
                        "div[role='button']:has-text('Connect'), "
                        "li:has-text('Connect'), "
                        "div.artdeco-dropdown__item:has-text('Connect'), "
                        "span:has-text('Connect')"
                    )
                    dropdown_connect, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "dropdown_connect_button",
                        candidates=[
                            dropdown_connect_selector,
                            *LINKEDIN_SELECTORS.get("dropdown_connect_button", []),
                        ],
                    )
                    found_connect = True
                    await self.biometrics.click_element(dropdown_connect)
                except SelectorDriftError:
                    pass

            if not found_connect:
                # Check if connection already pending
                pending_selector = (
                    "button:has-text('Pending'), "
                    "button[aria-label*='Pending'], "
                    "button[aria-label*='Invitation sent']"
                )
                try:
                    pending_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "pending_button",
                        candidates=[
                            pending_selector,
                            *LINKEDIN_SELECTORS.get("pending_button", []),
                        ],
                    )
                    logger.info("Connection invitation already pending for %s", profile_url)
                    screenshot = await self._capture_screenshot(f"already_pending_{item_id}")
                    screenshot = await self._upload_screenshot_to_r2(
                        screenshot, f"already_pending_{item_id}"
                    )
                    return ExecutionResult(
                        success=True,
                        action_type="send_connection",
                        item_id=item_id,
                        post_url=profile_url,
                        comment_text=note_text,
                        post_text=None,
                        screenshot_path=screenshot,
                        error=None,
                        executed_at=now,
                    )
                except SelectorDriftError:
                    pass

                await self._capture_telemetry(
                    trigger="connect_button_not_found",
                    item_id=item_id,
                    target_selector=connect_selector,
                )
                raise ExecutionError(f"Connect button not found on profile {profile_url}")

            # 6. Check for Premium paywall modal
            await asyncio.sleep(0.8)
            paywall_selector = (
                "dialog[open]:has-text('Grow your career'), "
                "dialog[open]:has-text('Try 1 month of Premium'), "
                "dialog[open]:has-text('Try Premium'), "
                "[data-testid='dialog']:has-text('Grow your career'), "
                "[data-testid='dialog']:has-text('Try 1 month of Premium')"
            )
            paywall = self.page.locator(paywall_selector).first
            try:
                if await paywall.count() > 0:
                    logger.warning("LinkedIn Premium paywall encountered for %s", profile_url)
                    dismiss_btn = paywall.locator("button[aria-label='Dismiss']").first
                    if await dismiss_btn.count() > 0:
                        await dismiss_btn.click()
                    else:
                        await self.page.keyboard.press("Escape")
                    screenshot = await self._capture_screenshot(f"premium_required_{item_id}")
                    raise ExecutionError(
                        f"LinkedIn requires Premium subscription to connect with this profile: {profile_url}"
                    )
            except ExecutionError:
                raise
            except Exception:
                pass

            # 7. Handle Invitation modal
            await asyncio.sleep(0.5)
            if note_text:
                add_note_selector = "button[aria-label='Add a note'], button:has-text('Add a note')"
                try:
                    add_note_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "add_note_button",
                        candidates=[
                            add_note_selector,
                            *LINKEDIN_SELECTORS.get("add_note_button", []),
                        ],
                    )
                    await self.biometrics.click_element(add_note_btn)
                    await asyncio.sleep(0.3)
                except SelectorDriftError:
                    pass

                textarea_selector = (
                    "textarea#custom-message, "
                    "textarea[name='message'], "
                    "textarea[id*='custom-message'], "
                    "textarea"
                )
                textarea = self.page.locator(textarea_selector).first
                if await textarea.count() > 0:
                    await self.biometrics.type_text(textarea, note_text)
                else:
                    logger.warning("Add note textarea not found; proceeding to send invitation")

                send_selector = (
                    "button[aria-label='Send invitation'], "
                    "button[aria-label='Send now'], "
                    "button:has-text('Send invitation'), "
                    "button:has-text('Send')"
                )
                try:
                    send_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "send_invitation_button",
                        candidates=[
                            send_selector,
                            *LINKEDIN_SELECTORS.get("send_invitation_button", []),
                        ],
                    )
                    await self.biometrics.click_element(send_btn)
                except SelectorDriftError as err:
                    raise ExecutionError("Send invitation button not found in modal") from err
            else:
                send_selector = (
                    "button[aria-label='Send without a note'], "
                    "button:has-text('Send without a note'), "
                    "button[aria-label='Send invitation'], "
                    "button[aria-label='Send now'], "
                    "button:has-text('Send')"
                )
                try:
                    send_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "send_invitation_button",
                        candidates=[
                            send_selector,
                            *LINKEDIN_SELECTORS.get("send_invitation_button", []),
                        ],
                    )
                    await self.biometrics.click_element(send_btn)
                except SelectorDriftError as err:
                    raise ExecutionError("Send invitation button not found in modal") from err

            # 8. DOM verification of sent invitation
            await self._verify_connection_sent(
                item_id=item_id,
                timeout=verification_timeout,
            )

            await self._refresh_and_persist_session()
            screenshot = await self._capture_screenshot(f"success_connect_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(
                screenshot, f"success_connect_{item_id}"
            )
            return ExecutionResult(
                success=True,
                action_type="send_connection",
                item_id=item_id,
                post_url=profile_url,
                comment_text=note_text,
                post_text=None,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )
        except Exception as err:
            if isinstance(
                err,
                BotDetectionError
                | SessionExpiredError
                | SubmissionVerificationError
                | ExecutionError,
            ):
                raise
            screenshot = await self._capture_screenshot(f"failed_connect_{item_id}")
            raise ExecutionError(
                f"Failed to send connection request: {err}",
                details={"screenshot_path": screenshot, "item_id": item_id},
            ) from err
