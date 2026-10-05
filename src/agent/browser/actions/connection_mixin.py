"""Connection outreach action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agent.browser import stealth
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
                "button:has-text('Pending'), button[aria-label*='Pending'], button[aria-label*='Invitation sent']"
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
    ) -> ExecutionResult:
        """Send a personalized LinkedIn connection invitation request."""
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
            if self.page.url != profile_url:
                await self.page.goto(profile_url, wait_until="domcontentloaded")
                await stealth.humanized_dwell(1.0, 2.0)

            if stealth.detect_challenge_page(self.page):
                screenshot = await self._capture_screenshot(f"challenge_connect_{item_id}")
                raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

            if stealth.is_authwall_or_login(self.page):
                raise SessionExpiredError(f"LinkedIn session expired navigating to {profile_url}")

            # 5. Detect "Connect" button directly or via "More actions"
            connect_selector = (
                "button:has-text('Connect'), "
                "button[aria-label*='Invite'][aria-label*='to connect'], "
                "button.pvs-profile-actions__action:has-text('Connect'), "
                "div.ph5 button:has-text('Connect')"
            )
            found_connect = False
            try:
                connect_btn, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "connect_btn",
                    candidates=[connect_selector, *LINKEDIN_SELECTORS.get("connect_btn", [])],
                )
                found_connect = True
                await self.biometrics.click_element(connect_btn)
            except SelectorDriftError:
                found_connect = False

            if not found_connect:
                # Try "More actions" dropdown
                more_selector = (
                    "button[aria-label='More actions'], "
                    "button:has-text('More'), "
                    "div.pvs-profile-actions button:has-text('More')"
                )
                try:
                    more_btn, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        "more_actions_btn",
                        candidates=[more_selector, *LINKEDIN_SELECTORS.get("more_actions_btn", [])],
                    )
                    await self.biometrics.click_element(more_btn)
                    await asyncio.sleep(0.5)

                    dropdown_connect_selector = (
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

            # 6. Handle Invitation modal
            await asyncio.sleep(0.5)
            if note_text:
                add_note_selector = "button:has-text('Add a note'), button[aria-label='Add a note']"
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
                    "textarea[name='message'], "
                    "textarea#custom-message, "
                    "textarea[id*='custom-message'], "
                    "textarea"
                )
                textarea = self.page.locator(textarea_selector).first
                if await textarea.count() > 0:
                    await self.biometrics.type_text(textarea, note_text)
                else:
                    logger.warning("Add note textarea not found; proceeding to send invitation")

                send_selector = (
                    "button:has-text('Send'), "
                    "button[aria-label='Send invitation'], "
                    "button[aria-label='Send now']"
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
                    "button:has-text('Send without a note'), "
                    "button[aria-label='Send without a note'], "
                    "button:has-text('Send'), "
                    "button[aria-label='Send invitation'], "
                    "button[aria-label='Send now']"
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

            # 7. DOM verification of sent invitation
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
                BotDetectionError | SessionExpiredError | SubmissionVerificationError,
            ):
                raise
            screenshot = await self._capture_screenshot(f"failed_connect_{item_id}")
            raise ExecutionError(
                f"Failed to send connection request: {err}",
                details={"screenshot_path": screenshot, "item_id": item_id},
            ) from err
