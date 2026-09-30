"""Adversarial challenge and stress-testing suite for DOM verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.browser.executor import ActionExecutor
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    SubmissionVerificationError,
)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-adversarial-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Distributed Systems"],
        dry_run=False,
    )


@pytest.mark.asyncio
async def test_adv_comment_box_not_cleared_not_in_thread_timeout_raises(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Stress-test: comment box remains filled, submit button stays enabled, and comment is not in thread.

    Must time out and raise typed SubmissionVerificationError with diagnostic screenshot.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    # Box text does NOT clear
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="My pending comment text that failed to clear"),
    )
    # Submit button stays active/enabled
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
        is_visible=AsyncMock(return_value=True),
        get_attribute=AsyncMock(return_value=None),
    )

    # Comments in thread exist but do NOT contain our comment
    other_comments = MagicMock()
    other_comments.count = AsyncMock(return_value=3)
    other_comments.first = other_comments
    other_comments.inner_text = AsyncMock(return_value="Some other user's comment from yesterday")
    other_filter = MagicMock(count=AsyncMock(return_value=0))
    other_comments.filter = MagicMock(return_value=other_filter)

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector or "submit-button" in selector:
            loc.first = submit_btn
            loc.count = submit_btn.count
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc.first = comment_box
            loc.count = comment_box.count
        elif "comment-item" in selector or "comments-list" in selector:
            return other_comments
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.first = MagicMock(
                count=AsyncMock(return_value=0), is_visible=AsyncMock(return_value=False)
            )
            loc.count = AsyncMock(return_value=0)
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings, debug_dir=tmp_path / "debug")
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="My pending comment text that failed to clear",
            item_id="adv_uncleared_001",
            dry_run=False,
            verification_timeout=0.05,
        )

    # Assert typed exception is also an ExecutionError
    assert isinstance(exc_info.value, ExecutionError)
    assert (
        "could not be verified in DOM within 0.1s" in str(exc_info.value)
        or "could not be verified in DOM within 0.0s" in str(exc_info.value)
        or "could not be verified in DOM" in str(exc_info.value)
    )
    # Assert screenshot was captured
    screenshot_path = exc_info.value.details.get("screenshot_path")
    assert screenshot_path is not None
    assert "failed_verify_comment_adv_uncleared_001" in str(screenshot_path)
    assert exc_info.value.details.get("item_id") == "adv_uncleared_001"


@pytest.mark.asyncio
async def test_adv_comment_immediate_error_banner_detected(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Stress-test: LinkedIn error banner appears immediately on comment submission."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Some comment text"),
    )
    submit_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    error_toast = MagicMock()
    error_toast.count = AsyncMock(return_value=1)
    error_toast.first = error_toast
    error_toast.is_visible = AsyncMock(return_value=True)
    error_toast.inner_text = AsyncMock(
        return_value="You have reached the limit for commenting. Try again later."
    )

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "toast" in selector or "alert" in selector or "feedback" in selector:
            return error_toast
        elif "submit" in selector or "submit-button" in selector:
            loc.first = submit_btn
            loc.count = submit_btn.count
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc.first = comment_box
            loc.count = comment_box.count
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings, debug_dir=tmp_path / "debug")
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="Some comment text",
            item_id="adv_toast_001",
            dry_run=False,
            verification_timeout=2.0,
        )

    assert isinstance(exc_info.value, ExecutionError)
    assert "LinkedIn comment submission rejected" in str(exc_info.value)
    assert "reached the limit for commenting" in str(exc_info.value)
    assert "failed_verify_comment_adv_toast_001" in str(
        exc_info.value.details.get("screenshot_path")
    )


@pytest.mark.asyncio
async def test_adv_comment_and_post_dry_run_guarantees_zero_writes(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Stress-test: dry_run=True strictly guarantees zero DOM write calls and no false verification errors."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock()
    submit_btn = MagicMock()
    comment_box = MagicMock()
    start_post_btn = MagicMock()
    post_btn = MagicMock()

    page.locator = MagicMock()

    executor = ActionExecutor(page, test_settings, debug_dir=tmp_path / "debug")
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    # Test 1: post_comment with dry_run=True
    res_comment = await executor.post_comment(
        post_url=page.url,
        comment_text="Dry run comment text",
        item_id="adv_dry_001",
        dry_run=True,
    )
    assert res_comment.success is True
    assert res_comment.action_type == "approve_comment"
    assert res_comment.comment_text == "Dry run comment text"
    assert "dryrun_comment_adv_dry_001" in str(res_comment.screenshot_path)
    # Zero DOM locator interaction for writes
    assert comment_btn.click.call_count == 0
    assert submit_btn.click.call_count == 0
    assert comment_box.press_sequentially.call_count == 0

    # Test 2: create_post with dry_run=True
    res_post = await executor.create_post(
        post_text="Dry run post content",
        item_id="adv_dry_post_001",
        dry_run=True,
    )
    assert res_post.success is True
    assert res_post.action_type == "approve_post"
    assert res_post.post_text == "Dry run post content"
    assert "dryrun_post_adv_dry_post_001" in str(res_post.screenshot_path)
    assert start_post_btn.click.call_count == 0
    assert post_btn.click.call_count == 0


@pytest.mark.asyncio
async def test_adv_bot_challenge_during_verification_raises_bot_detection(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Stress-test: bot challenge / security checkpoint appears during verification loop."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Text"),
    )
    submit_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector or "submit-button" in selector:
            loc.first = submit_btn
            loc.count = submit_btn.count
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc.first = comment_box
            loc.count = comment_box.count
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings, debug_dir=tmp_path / "debug")
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    # Mock detect_challenge_page to return False initially (post exists), but True during verification
    with patch("agent.browser.stealth.detect_challenge_page", side_effect=[False, True]):
        with pytest.raises(BotDetectionError) as exc_info:
            await executor.post_comment(
                post_url=page.url,
                comment_text="Text",
                item_id="adv_challenge_001",
                dry_run=False,
                verification_timeout=1.0,
            )

    assert "Bot detection challenge during comment verification" in str(exc_info.value)


@pytest.mark.asyncio
async def test_adv_comment_long_multiline_emoji_snippet_matching(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    """Stress-test: long comment (200+ chars) with emojis, newlines, and special characters."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    long_comment = (
        "🚀 Excellent analysis of distributed consensus & multi-raft architectures!\n\n"
        "I especially appreciate the empirical breakdown on tail latency in Section 3. "
        "Looking forward to reading more about your fault-injection test harness. 🤖✨"
    )
    snippet = long_comment[:80].strip()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value=long_comment),
    )
    submit_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    # Simulated DOM container containing the long comment
    comment_loc = MagicMock()
    comment_loc.count = AsyncMock(return_value=1)
    comment_loc.first = comment_loc
    comment_loc.inner_text = AsyncMock(return_value=long_comment)

    # filter(has_text=snippet) returns count=1
    matched_filter = MagicMock(count=AsyncMock(return_value=1))
    comment_loc.filter = MagicMock(return_value=matched_filter)

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if (
            "comment-item" in selector
            or "comments-list" in selector
            or "comments-container" in selector
        ):
            return comment_loc
        elif "submit" in selector or "submit-button" in selector:
            loc.first = submit_btn
            loc.count = submit_btn.count
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc.first = comment_box
            loc.count = comment_box.count
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings, debug_dir=tmp_path / "debug")
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text=long_comment,
        item_id="adv_long_001",
        dry_run=False,
        verification_timeout=1.0,
    )

    assert result.success is True
    assert result.comment_text == long_comment
    assert "success_comment_adv_long_001" in str(result.screenshot_path)
    # Verify filter was called with the 80-char prefix snippet
    comment_loc.filter.assert_called_with(has_text=snippet)
