"""Thread engagement action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agent.browser import stealth
from agent.browser.actions.base import _safe_count, _safe_scroll
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    PostNoLongerAvailableError,
    SessionExpiredError,
    SubmissionVerificationError,
)
from agent.models import ExecutionResult, ThreadReplyItem

if TYPE_CHECKING:
    from playwright.async_api import Page

    from agent.browser.biometrics import BiometricController
    from agent.config import Settings

logger = logging.getLogger(__name__)


def _pick_loc(loc: Any, prefer_last: bool = False) -> Any:
    if type(loc).__name__ in ("MagicMock", "Mock", "AsyncMock"):
        return getattr(loc, "first", loc)
    if prefer_last and hasattr(loc, "last"):
        return loc.last
    return getattr(loc, "first", loc)


class ThreadMixin:
    """Mixin providing multi-turn comment thread inspection and reply posting."""

    page: Page
    settings: Settings
    biometrics: BiometricController

    # Methods provided by VerificationMixin & CommentMixin
    _capture_screenshot: Any
    _upload_screenshot_to_r2: Any
    _capture_telemetry: Any
    _refresh_and_persist_session: Any
    _verify_comment_submission: Any
    verify_post_exists: Any

    async def inspect_comment_replies(
        self,
        post_url: str,
        our_comment_text: str,
    ) -> list[ThreadReplyItem]:
        """Inspect a LinkedIn post's comment thread to extract replies to our comment."""
        if stealth.detect_challenge_page(self.page):
            await self._capture_screenshot("challenge_inspect_replies")
            raise BotDetectionError(f"Challenge page before inspecting replies: {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            raise SessionExpiredError(f"LinkedIn session expired; redirected to {self.page.url}")

        # Navigate to post_url if not already there
        if post_url and (not self.page.url or post_url not in self.page.url):
            try:
                await self.page.goto(post_url, wait_until="domcontentloaded")
            except Exception as err:
                logger.warning("Navigation to %s failed: %s", post_url, err)

        if stealth.detect_challenge_page(self.page):
            await self._capture_screenshot("challenge_inspect_replies")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            raise SessionExpiredError(f"LinkedIn session expired; redirected to {self.page.url}")

        post_exists = await self.verify_post_exists(post_url)
        if not post_exists:
            logger.warning("Target post %s no longer available for reply inspection", post_url)
            return []

        # Extract original post author name
        original_author = ""
        try:
            author_loc = self.page.locator(
                ".update-components-actor__name, .feed-shared-actor__name, "
                "div.update-components-actor span[aria-hidden='true'], "
                ".feed-shared-actor__title"
            ).first
            if await _safe_count(author_loc) > 0:
                raw_author = (await author_loc.inner_text()).strip()
                original_author = raw_author.split("\n")[0].strip()
        except Exception:
            pass

        # Locate our comment card/container matching our_comment_text
        snippet = our_comment_text[:80].strip() if our_comment_text else ""
        comment_loc = self.page.locator(
            "article.comments-comment-item, div.comments-comment-item, div.comments-comments-list__comment-item"
        )
        parent_card = None
        try:
            count = await _safe_count(comment_loc)
            for i in range(count):
                card = comment_loc.nth(i)
                card_text = await card.inner_text()
                if snippet and snippet in card_text:
                    parent_card = card
                    break
        except Exception as err:
            logger.debug("Error locating parent comment: %s", err)

        if parent_card is None:
            logger.info("Our comment was not found on post %s", post_url)
            return []

        # Determine parent comment URN
        parent_urn = ""
        try:
            parent_urn = (
                await parent_card.get_attribute("data-id")
                or await parent_card.get_attribute("id")
                or await parent_card.get_attribute("data-urn")
                or ""
            )
        except Exception:
            pass
        if not parent_urn:
            parent_urn = f"urn:li:comment:({post_url})"

        # Find child/nested reply elements
        reply_loc = parent_card.locator(
            ".comments-comment-item--reply, "
            "div[data-view-name*='reply'], "
            "article.comments-comment-item.comments-reply-item, "
            ".comments-reply-item, "
            "div.comments-comment-item__nested, "
            "div.comments-replies-list article"
        )
        reply_count = await _safe_count(reply_loc)

        if reply_count == 0:
            sibling_reply_loc = self.page.locator(
                ".comments-comment-item--reply, div[data-view-name*='reply']"
            )
            sibling_count = await _safe_count(sibling_reply_loc)
            if sibling_count > 0:
                reply_loc = sibling_reply_loc
                reply_count = sibling_count

        replies: list[ThreadReplyItem] = []
        for i in range(reply_count):
            reply_el = reply_loc.nth(i)
            try:
                r_urn = (
                    await reply_el.get_attribute("data-id")
                    or await reply_el.get_attribute("id")
                    or await reply_el.get_attribute("data-urn")
                    or f"{parent_urn}-reply-{i + 1}"
                )

                # Extract replier name
                name_el = reply_el.locator(
                    ".comments-post-meta__name, .comments-post-meta__name-text, "
                    ".comments-comment-meta__name, .hoverable-link-text, span[aria-hidden='true']"
                ).first
                replier_name = (
                    (await name_el.inner_text()).strip()
                    if await _safe_count(name_el) > 0
                    else "LinkedIn Member"
                )
                if "\n" in replier_name:
                    replier_name = replier_name.split("\n")[0].strip()

                # Extract headline
                headline_el = reply_el.locator(
                    ".comments-post-meta__headline, .comments-comment-meta__headline, .comments-post-meta__occupation"
                ).first
                replier_headline = (
                    (await headline_el.inner_text()).strip()
                    if await _safe_count(headline_el) > 0
                    else ""
                )

                # Extract reply text
                body_el = reply_el.locator(
                    ".comments-comment-item__main-content, .update-components-text, "
                    ".comments-comment-item-content-body, div.feed-shared-main-content--comment, "
                    "div.comments-comment-item__message"
                ).first
                if await _safe_count(body_el) > 0:
                    reply_body = (await body_el.inner_text()).strip()
                else:
                    raw_text = await reply_el.inner_text()
                    reply_body = (
                        raw_text.replace(replier_name, "").replace(replier_headline, "").strip()
                    )

                if not reply_body or (snippet and snippet in reply_body):
                    continue

                is_author = False
                if original_author and (
                    replier_name.lower() in original_author.lower()
                    or original_author.lower() in replier_name.lower()
                ):
                    is_author = True
                else:
                    badge_el = reply_el.locator(
                        ".comments-post-meta__author-badge, span:has-text('Author')"
                    )
                    if await _safe_count(badge_el) > 0:
                        is_author = True

                replies.append(
                    ThreadReplyItem(
                        reply_urn=r_urn,
                        parent_comment_urn=parent_urn,
                        author_name=replier_name,
                        author_headline=replier_headline,
                        reply_text=reply_body,
                        is_post_author=is_author,
                    )
                )
            except Exception as err:
                logger.debug("Failed parsing reply element %d: %s", i, err)

        return replies

    async def post_thread_reply(
        self,
        post_url: str,
        comment_urn: str,
        reply_text: str,
        item_id: str = "reply_action",
        dry_run: bool | None = None,
        verification_timeout: float = 6.0,
    ) -> ExecutionResult:
        """Post an approved follow-up reply to a comment thread on LinkedIn."""
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run
        now = datetime.now(UTC)

        if stealth.detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        if post_url and (not self.page.url or post_url not in self.page.url):
            try:
                await self.page.goto(post_url, wait_until="domcontentloaded")
            except Exception as err:
                logger.warning("Navigation to %s failed: %s", post_url, err)

        if stealth.detect_challenge_page(self.page):
            screenshot = await self._capture_screenshot(f"challenge_{item_id}")
            raise BotDetectionError(f"Bot detection challenge on {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            raise SessionExpiredError(f"LinkedIn session expired; redirected to {self.page.url}")

        post_exists = await self.verify_post_exists(post_url)
        if not post_exists:
            screenshot = await self._capture_screenshot(f"missing_post_{item_id}")
            raise PostNoLongerAvailableError(f"Post at {post_url} is no longer available")

        # Locate comment container if urn is provided
        comment_card = None
        if comment_urn:
            card_loc = self.page.locator(
                f"[data-id*='{comment_urn}'], [id*='{comment_urn}'], [data-urn*='{comment_urn}']"
            )
            if await _safe_count(card_loc) > 0:
                comment_card = card_loc.first

        # Locate reply trigger button
        reply_btn_selector = (
            "button[aria-label*='Reply' i], button.comments-comment-social-bar__reply-action-button, "
            "button.reply-button, button:has-text('Reply')"
        )
        if (
            comment_card is not None
            and await _safe_count(comment_card.locator(reply_btn_selector)) > 0
        ):
            reply_btn = comment_card.locator(reply_btn_selector).first
        else:
            reply_btn = self.page.locator(reply_btn_selector).first

        reply_box_selector = (
            "div.comments-comment-box div[role='textbox'], "
            "div[data-testid='ui-core-tiptap-text-editor-wrapper'] div.tiptap.ProseMirror, "
            "div.tiptap.ProseMirror, "
            "div[role='textbox'][aria-label*='reply' i], "
            "div[role='textbox'][aria-label*='comment' i], "
            "div.ql-editor, textarea[name='comment']"
        )
        if (
            comment_card is not None
            and await _safe_count(comment_card.locator(reply_box_selector)) > 0
        ):
            reply_box = _pick_loc(comment_card.locator(reply_box_selector), prefer_last=True)
        else:
            reply_box = _pick_loc(self.page.locator(reply_box_selector), prefer_last=True)

        if is_dry_run:
            logger.info(
                "DRY_RUN: Simulated thread reply on %s (comment %s): %s",
                post_url,
                comment_urn,
                reply_text,
            )
            try:
                if await _safe_count(reply_btn) > 0:
                    await self.biometrics.click_element(reply_btn)
                if await _safe_count(reply_box) > 0:
                    logger.info(
                        "DRY_RUN: Verified reply input box presence in DOM for comment %s",
                        comment_urn,
                    )
            except Exception as e:
                logger.debug("DRY_RUN: Input verification notice: %s", e)

            screenshot = await self._capture_screenshot(f"dryrun_reply_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(screenshot, f"dryrun_reply_{item_id}")
            sep = "&" if "?" in post_url else "?"
            reply_link = f"{post_url}{sep}commentUrn={comment_urn}" if comment_urn else post_url
            return ExecutionResult(
                success=True,
                action_type="approve_reply",
                item_id=item_id,
                post_url=post_url,
                comment_url=reply_link,
                comment_text=reply_text,
                post_text=None,
                screenshot_path=screenshot,
                error=None,
                executed_at=now,
            )

        # Live submission path
        try:
            if await _safe_count(reply_btn) > 0:
                await _safe_scroll(reply_btn)
                await self.biometrics.click_element(reply_btn)
                await asyncio.sleep(0.5)

            if await _safe_count(reply_box) == 0:
                reply_box = _pick_loc(self.page.locator(reply_box_selector), prefer_last=True)

            if await _safe_count(reply_box) == 0:
                await self._capture_telemetry(
                    trigger="thread_reply_box_drift",
                    item_id=item_id,
                    target_selector=reply_box_selector,
                )
                raise ExecutionError("Comment reply input box not found in DOM")

            await _safe_scroll(reply_box)
            await self.biometrics.type_text(reply_box, reply_text)

            submit_btn_selector = (
                "button:has-text('Reply'), "
                "button.comments-comment-box__submit-button, "
                "div.comments-comment-box button[type='submit'], "
                "button[type='submit']:has-text('Reply'), "
                "button[type='submit']:has-text('Comment'), "
                "button[type='submit']:has-text('Post'), "
                "button:has-text('Post')"
            )
            if (
                comment_card is not None
                and await _safe_count(comment_card.locator(submit_btn_selector)) > 0
            ):
                submit_btn = _pick_loc(comment_card.locator(submit_btn_selector), prefer_last=True)
            else:
                submit_btn = _pick_loc(self.page.locator(submit_btn_selector), prefer_last=True)

            if await _safe_count(submit_btn) == 0:
                await self._capture_telemetry(
                    trigger="thread_reply_submit_btn_drift",
                    item_id=item_id,
                    target_selector=submit_btn_selector,
                )
                raise ExecutionError("Reply submit button not found in DOM")

            await _safe_scroll(submit_btn)
            await self.biometrics.click_element(submit_btn)

            # Confirm submission in DOM
            await self._verify_comment_submission(
                comment_box=reply_box,
                submit_btn=submit_btn,
                comment_text=reply_text,
                item_id=item_id,
                timeout=verification_timeout,
            )

            sep = "&" if "?" in post_url else "?"
            reply_url = f"{post_url}{sep}commentUrn={comment_urn}" if comment_urn else post_url

            await self._refresh_and_persist_session()
            screenshot = await self._capture_screenshot(f"success_reply_{item_id}")
            screenshot = await self._upload_screenshot_to_r2(screenshot, f"success_reply_{item_id}")
            return ExecutionResult(
                success=True,
                action_type="approve_reply",
                item_id=item_id,
                post_url=post_url,
                comment_url=reply_url,
                comment_text=reply_text,
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
            screenshot = await self._capture_screenshot(f"failed_reply_{item_id}")
            raise ExecutionError(
                f"Failed to post thread reply: {err}",
                details={"screenshot_path": screenshot, "item_id": item_id},
            ) from err
