"""Unit tests for ActionExecutor dry run and live write paths."""

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
    PostNoLongerAvailableError,
    SessionExpiredError,
    SubmissionVerificationError,
)


@pytest.fixture
def base_settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        dry_run=True,
    )


@pytest.mark.asyncio
async def test_verify_login_challenge_raises(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(BotDetectionError):
        await executor.verify_login()


@pytest.mark.asyncio
async def test_verify_login_redirect_raises_session_expired(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(SessionExpiredError):
        await executor.verify_login()


@pytest.mark.asyncio
async def test_verify_login_success(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    nav_loc = MagicMock()
    nav_loc.count = AsyncMock(return_value=1)
    page.locator = MagicMock(return_value=nav_loc)

    executor = ActionExecutor(page, base_settings)
    assert await executor.verify_login() is True


@pytest.mark.asyncio
async def test_post_comment_dry_run_does_not_submit(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Insightful post!",
        item_id="dryrun001",
        dry_run=True,
    )

    assert result.success is True
    assert result.action_type == "approve_comment"
    assert result.item_id == "dryrun001"
    assert result.comment_text == "Insightful post!"


@pytest.mark.asyncio
async def test_create_post_dry_run(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    result = await executor.create_post(
        post_text="New original post on AI architecture",
        item_id="dryrun_post001",
        dry_run=True,
    )

    assert result.success is True
    assert result.action_type == "approve_post"
    assert result.post_text == "New original post on AI architecture"


@pytest.mark.asyncio
async def test_post_comment_missing_post_raises_error(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:999/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=False)  # type: ignore[method-assign]

    with pytest.raises(PostNoLongerAvailableError):
        await executor.post_comment(
            post_url=page.url,
            comment_text="Will fail",
            item_id="fail001",
            dry_run=False,
        )


@pytest.mark.asyncio
async def test_post_comment_live_success_verified_via_comment_element(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    # Locators
    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=1)
    comment_btn.click = AsyncMock()

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=1)
    comment_box.focus = AsyncMock()
    comment_box.press_sequentially = AsyncMock()
    comment_box.inner_text = AsyncMock(return_value="Live comment test")

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=1)
    submit_btn.click = AsyncMock()
    submit_btn.is_disabled = AsyncMock(return_value=False)

    comment_item = MagicMock()
    comment_item.count = AsyncMock(return_value=1)
    comment_item.inner_text = AsyncMock(return_value="Live comment test by author")
    comment_item.first = comment_item
    comment_item.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=1)))

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
            return comment_item
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

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Live comment test",
        item_id="live001",
        dry_run=False,
        verification_timeout=1.0,
    )

    assert result.success is True
    assert result.comment_text == "Live comment test"
    assert "success_comment_live001" in str(result.screenshot_path)
    assert comment_btn.click.called
    assert submit_btn.click.called


@pytest.mark.asyncio
async def test_post_comment_live_success_verified_via_input_cleared(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=1)
    comment_btn.click = AsyncMock()

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=1)
    comment_box.focus = AsyncMock()
    comment_box.press_sequentially = AsyncMock()
    # Box is cleared post-submit
    comment_box.inner_text = AsyncMock(return_value="")

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=1)
    submit_btn.click = AsyncMock()
    submit_btn.is_disabled = AsyncMock(return_value=True)

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
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        elif "comment-item" in selector or "comments-list" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
            loc.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Live comment test 2",
        item_id="live002",
        dry_run=False,
        verification_timeout=1.0,
    )

    assert result.success is True
    assert "success_comment_live002" in str(result.screenshot_path)


@pytest.mark.asyncio
async def test_post_comment_live_verification_failure_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    # Box remains full of text
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Still uncleared comment text"),
    )
    # Submit button remains enabled
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
        is_visible=AsyncMock(return_value=True),
        get_attribute=AsyncMock(return_value=None),
    )

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
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        elif "comment-item" in selector or "comments-list" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
            loc.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
            loc.count = comment_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="Live comment test",
            item_id="fail001",
            dry_run=False,
            verification_timeout=0.01,
        )

    assert "could not be verified in DOM" in str(exc_info.value)
    assert "failed_verify_comment_fail001" in str(exc_info.value.details.get("screenshot_path"))
    assert exc_info.value.details.get("item_id") == "fail001"


@pytest.mark.asyncio
async def test_post_comment_live_error_toast_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Comment text"),
    )
    submit_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    error_toast = MagicMock()
    error_toast.count = AsyncMock(return_value=1)
    error_toast.first = error_toast
    error_toast.is_visible = AsyncMock(return_value=True)
    error_toast.inner_text = AsyncMock(return_value="Unable to post comment. Please try again.")

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

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="Live comment test",
            item_id="toast_err_001",
            dry_run=False,
            verification_timeout=1.0,
        )

    assert "LinkedIn comment submission rejected" in str(exc_info.value)
    assert "Unable to post comment" in str(exc_info.value)
    assert "failed_verify_comment_toast_err_001" in str(
        exc_info.value.details.get("screenshot_path")
    )


@pytest.mark.asyncio
async def test_create_post_live_success_verified_via_modal_close(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    start_post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    editor = MagicMock(
        count=AsyncMock(return_value=1), focus=AsyncMock(), press_sequentially=AsyncMock()
    )
    post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    modal_loc = MagicMock()
    modal_loc.count = AsyncMock(return_value=1)
    modal_loc.is_visible = AsyncMock(return_value=False)  # Modal is closed/hidden

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Start a post" in selector or "share-box-feed-entry" in selector:
            loc.first = start_post_btn
            loc.count = start_post_btn.count
        elif "share-box-modal" in selector or "dialog" in selector:
            loc.first = modal_loc
            loc.count = modal_loc.count
            loc.is_visible = modal_loc.is_visible
        elif "ql-editor" in selector or "textbox" in selector:
            loc.first = editor
            loc.count = editor.count
        elif "share-actions__primary-action" in selector or "Post" in selector:
            loc.first = post_btn
            loc.count = post_btn.count
        elif "toast" in selector or "alert" in selector:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.create_post(
        post_text="New original post content",
        item_id="post001",
        dry_run=False,
        verification_timeout=1.0,
    )

    assert result.success is True
    assert result.action_type == "approve_post"
    assert result.post_text == "New original post content"
    assert "success_post_post001" in str(result.screenshot_path)
    assert start_post_btn.click.called
    assert post_btn.click.called


@pytest.mark.asyncio
async def test_create_post_live_success_verified_via_success_toast(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    start_post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    editor = MagicMock(
        count=AsyncMock(return_value=1), focus=AsyncMock(), press_sequentially=AsyncMock()
    )
    post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    modal_loc = MagicMock(count=AsyncMock(return_value=1), is_visible=AsyncMock(return_value=True))

    success_toast = MagicMock()
    success_toast.count = AsyncMock(return_value=1)
    success_toast.first = success_toast
    success_toast.is_visible = AsyncMock(return_value=True)

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "toast-item--success" in selector or "Post successful" in selector:
            return success_toast
        elif (
            "error" in selector
            or "feedback" in selector
            or "alert" in selector
            or "toast" in selector
        ):
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        elif "Start a post" in selector or "share-box-feed-entry" in selector:
            loc.first = start_post_btn
            loc.count = start_post_btn.count
        elif "share-box-modal" in selector or "dialog" in selector or "creation-state" in selector:
            loc.first = modal_loc
            loc.count = modal_loc.count
            loc.is_visible = modal_loc.is_visible
        elif "ql-editor" in selector or "textbox" in selector:
            loc.first = editor
            loc.count = editor.count
        elif "share-actions__primary-action" in selector or "Post" in selector:
            loc.first = post_btn
            loc.count = post_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.create_post(
        post_text="New original post with toast confirmation",
        item_id="post002",
        dry_run=False,
        verification_timeout=1.0,
    )

    assert result.success is True
    assert "success_post_post002" in str(result.screenshot_path)


@pytest.mark.asyncio
async def test_create_post_live_verification_failure_modal_stuck_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    start_post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    editor = MagicMock(
        count=AsyncMock(return_value=1), focus=AsyncMock(), press_sequentially=AsyncMock()
    )
    post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    # Modal remains open and visible
    modal_loc = MagicMock(count=AsyncMock(return_value=1), is_visible=AsyncMock(return_value=True))

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if (
            "error" in selector
            or "feedback" in selector
            or "alert" in selector
            or "toast" in selector
        ):
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        elif "Start a post" in selector or "share-box-feed-entry" in selector:
            loc.first = start_post_btn
            loc.count = start_post_btn.count
        elif "share-box-modal" in selector or "dialog" in selector or "creation-state" in selector:
            loc.first = modal_loc
            loc.count = modal_loc.count
            loc.is_visible = modal_loc.is_visible
        elif "ql-editor" in selector or "textbox" in selector:
            loc.first = editor
            loc.count = editor.count
        elif "share-actions__primary-action" in selector or "Post" in selector:
            loc.first = post_btn
            loc.count = post_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.create_post(
            post_text="Post that gets stuck",
            item_id="failpost001",
            dry_run=False,
            verification_timeout=0.01,
        )

    assert "could not be verified in DOM" in str(exc_info.value)
    assert "modal remained open" in str(exc_info.value)
    assert "failed_verify_post_failpost001" in str(exc_info.value.details.get("screenshot_path"))


@pytest.mark.asyncio
async def test_create_post_live_error_toast_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    start_post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    editor = MagicMock(
        count=AsyncMock(return_value=1), focus=AsyncMock(), press_sequentially=AsyncMock()
    )
    post_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())

    modal_loc = MagicMock(count=AsyncMock(return_value=1), is_visible=AsyncMock(return_value=True))

    error_toast = MagicMock()
    error_toast.count = AsyncMock(return_value=1)
    error_toast.first = error_toast
    error_toast.is_visible = AsyncMock(return_value=True)
    error_toast.inner_text = AsyncMock(return_value="Your post could not be shared. Try again.")

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "toast" in selector or "alert" in selector or "feedback" in selector:
            return error_toast
        elif "Start a post" in selector or "share-box-feed-entry" in selector:
            loc.first = start_post_btn
            loc.count = start_post_btn.count
        elif "share-box-modal" in selector or "dialog" in selector:
            loc.first = modal_loc
            loc.count = modal_loc.count
            loc.is_visible = modal_loc.is_visible
        elif "ql-editor" in selector or "textbox" in selector:
            loc.first = editor
            loc.count = editor.count
        elif "share-actions__primary-action" in selector or "Post" in selector:
            loc.first = post_btn
            loc.count = post_btn.count
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    with pytest.raises(SubmissionVerificationError) as exc_info:
        await executor.create_post(
            post_text="Post that triggers error toast",
            item_id="post_err_001",
            dry_run=False,
            verification_timeout=1.0,
        )

    assert "LinkedIn post creation rejected" in str(exc_info.value)
    assert "Your post could not be shared" in str(exc_info.value)
    assert "failed_verify_post_post_err_001" in str(exc_info.value.details.get("screenshot_path"))


@pytest.mark.asyncio
async def test_create_post_missing_start_button_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    loc = MagicMock(count=AsyncMock(return_value=0))
    loc.first = loc
    page.locator = MagicMock(return_value=loc)

    executor = ActionExecutor(page, base_settings)
    with pytest.raises(ExecutionError) as exc_info:
        await executor.create_post(
            post_text="Will fail early",
            item_id="missing_btn_001",
            dry_run=False,
        )

    assert "Start a post button not found in DOM" in str(exc_info.value)


@pytest.mark.asyncio
async def test_post_comment_missing_input_box_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc

    def locator_side_effect(selector: str) -> MagicMock:
        if "comment-button" in selector or "button" in selector:
            loc = MagicMock()
            loc.first = comment_btn
            loc.count = comment_btn.count
            return loc
        return empty_loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(ExecutionError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="Will fail early",
            item_id="missing_box_001",
            dry_run=False,
        )

    assert "Comment input box not found in DOM" in str(exc_info.value)


@pytest.mark.asyncio
async def test_post_comment_missing_submit_button_raises_execution_error(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
    )
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc

    def locator_side_effect(selector: str) -> MagicMock:
        if (
            "submit" in selector
            or "submit-button" in selector
            or "commentButtonSection" in selector
            or "comment_post" in selector
            or "Post" in selector
        ):
            return empty_loc
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc = MagicMock()
            loc.first = comment_box
            loc.count = comment_box.count
            return loc
        elif "comment-button" in selector or "button" in selector:
            loc = MagicMock()
            loc.first = comment_btn
            loc.count = comment_btn.count
            return loc
        return empty_loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(ExecutionError) as exc_info:
        await executor.post_comment(
            post_url=page.url,
            comment_text="Will fail submit btn",
            item_id="missing_submit_001",
            dry_run=False,
        )

    assert "Comment submit button not found in DOM" in str(exc_info.value)


@pytest.mark.asyncio
async def test_react_to_post_dry_run(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    executor = ActionExecutor(page, base_settings)

    result = await executor.react_to_post(
        reaction_type="like", item_id="dryrun_react", dry_run=True
    )
    assert result is True
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_react_to_post_challenge_raises_bot_detection(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"
    page.screenshot = AsyncMock()
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(BotDetectionError):
        await executor.react_to_post(reaction_type="like", item_id="chal_react", dry_run=False)


@pytest.mark.asyncio
async def test_react_to_post_session_expired_raises(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(SessionExpiredError):
        await executor.react_to_post(reaction_type="like", item_id="exp_react", dry_run=False)


@pytest.mark.asyncio
async def test_react_to_post_missing_button_returns_false(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc
    page.locator = MagicMock(return_value=empty_loc)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="missing_react_btn", dry_run=False
    )
    assert result is False


@pytest.mark.asyncio
async def test_react_to_post_already_reacted_skips_click(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: "true" if attr == "aria-pressed" else "React Like"
    )
    react_btn.click = AsyncMock()
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="already_reacted", dry_run=False
    )
    assert result is True
    react_btn.click.assert_not_called()


@pytest.mark.asyncio
async def test_react_to_post_modern_aria_already_reacted(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: None if attr == "aria-pressed" else "Reaction button state: Like"
    )
    react_btn.click = AsyncMock()
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="already_reacted_modern", dry_run=False
    )
    assert result is True
    react_btn.click.assert_not_called()


@pytest.mark.asyncio
async def test_react_to_post_modern_aria_no_reaction_clicks(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            None if attr == "aria-pressed" else "Reaction button state: no reaction"
        )
    )
    react_btn.click = AsyncMock()
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="like_modern", dry_run=False
    )
    assert result is True
    react_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_live_like_success(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: "false" if attr == "aria-pressed" else "React Like"
    )
    react_btn.click = AsyncMock()
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="like_success", dry_run=False
    )
    assert result is True
    react_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_live_insightful_hover_menu_success(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: "false" if attr == "aria-pressed" else "React Like"
    )
    react_btn.hover = AsyncMock()
    react_btn.first = react_btn

    menu_item = MagicMock()
    menu_item.count = AsyncMock(return_value=1)
    menu_item.click = AsyncMock()
    menu_item.first = menu_item

    def locator_side_effect(selector: str) -> MagicMock:
        if "Insightful" in selector or "insightful" in selector:
            return menu_item
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="insightful", item_id="insightful_success", dry_run=False
    )
    assert result is True
    react_btn.hover.assert_called_once()
    menu_item.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_live_insightful_menu_missing_fallback_to_like(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: "false" if attr == "aria-pressed" else "React Like"
    )
    react_btn.hover = AsyncMock()
    react_btn.click = AsyncMock()
    react_btn.first = react_btn

    empty_menu = MagicMock()
    empty_menu.count = AsyncMock(return_value=0)
    empty_menu.first = empty_menu

    def locator_side_effect(selector: str) -> MagicMock:
        if "Insightful" in selector or "insightful" in selector:
            return empty_menu
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="insightful", item_id="fallback_like", dry_run=False
    )
    assert result is True
    react_btn.hover.assert_called_once()
    react_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_unexpected_error_returns_false(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.locator = MagicMock(side_effect=RuntimeError("DOM disconnected"))

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(reaction_type="like", item_id="err_react", dry_run=False)
    assert result is False


@pytest.mark.asyncio
async def test_post_comment_with_pre_reaction_live(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Pre-reaction comment test"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Pre-reaction comment test"),
    )
    comment_item.first = comment_item
    comment_item.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=1)))

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
            return comment_item
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

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Pre-reaction comment test",
        item_id="pre_react_001",
        dry_run=False,
        verification_timeout=1.0,
        reaction_type="like",
        simulate_dwell=False,
    )

    assert result.success is True
    executor.react_to_post.assert_called_once_with(
        reaction_type="like",
        item_id="pre_react_001",
        dry_run=False,
    )


@pytest.mark.asyncio
async def test_post_comment_with_pre_reaction_from_settings(base_settings: Settings) -> None:
    base_settings.enable_pre_comment_reaction = True
    base_settings.default_reaction_type = "insightful"

    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Settings reaction comment"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Settings reaction comment"),
    )
    comment_item.first = comment_item
    comment_item.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=1)))

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
            return comment_item
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

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Settings reaction comment",
        item_id="pre_react_settings",
        dry_run=False,
        verification_timeout=1.0,
        simulate_dwell=False,
    )

    assert result.success is True
    executor.react_to_post.assert_called_once_with(
        reaction_type="insightful",
        item_id="pre_react_settings",
        dry_run=False,
    )


@pytest.mark.asyncio
async def test_post_comment_with_pre_reaction_dry_run(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Dry run with reaction",
        item_id="dryrun_react_001",
        dry_run=True,
        reaction_type="insightful",
    )

    assert result.success is True
    assert result.action_type == "approve_comment"
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_post_comment_reaction_failure_fallback_continues_commenting(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Non-fatal fallback test"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Non-fatal fallback test"),
    )
    comment_item.first = comment_item
    comment_item.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=1)))

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
            return comment_item
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

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=False)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Non-fatal fallback test",
        item_id="fallback_001",
        dry_run=False,
        verification_timeout=1.0,
        reaction_type="like",
        simulate_dwell=False,
    )

    assert result.success is True
    assert result.comment_text == "Non-fatal fallback test"
    assert submit_btn.click.called


@pytest.mark.asyncio
async def test_post_comment_missing_box_captures_telemetry(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"

    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=0)

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=0)

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Comment" in selector and "button" in selector:
            loc.first = comment_btn
            loc.count = AsyncMock(return_value=0)
        else:
            loc.first = comment_box
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_mock)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with patch(
        "agent.browser.telemetry.capture_dom_telemetry", new_callable=AsyncMock
    ) as mock_telemetry:
        with pytest.raises(ExecutionError, match="Comment input box not found"):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Nice post!",
                item_id="item_drift_box",
                dry_run=False,
            )

        mock_telemetry.assert_awaited_once()
        kwargs = mock_telemetry.call_args.kwargs
        assert kwargs["trigger"] == "comment_box_drift"
        assert kwargs["item_id"] == "item_drift_box"


@pytest.mark.asyncio
async def test_post_comment_missing_submit_button_captures_telemetry(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"

    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=0)
    comment_btn.click = AsyncMock()

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=1)
    comment_box.click = AsyncMock()

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=0)

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if (
            "comments-comment-box__submit-button" in selector
            or "submit" in selector
            or "commentButtonSection" in selector
            or "comment_post" in selector
            or "Post" in selector
        ):
            loc.first = submit_btn
            loc.count = AsyncMock(return_value=0)
        elif (
            "data-control-name='comment'" in selector
            or "comment-button" in selector
            or "Comment" in selector
            or "comment" in selector
        ):
            loc.first = comment_btn
            loc.count = AsyncMock(return_value=0)
        else:
            loc.first = comment_box
            loc.count = AsyncMock(return_value=1)
        return loc

    page.locator = MagicMock(side_effect=locator_mock)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with (
        patch(
            "agent.browser.telemetry.capture_dom_telemetry", new_callable=AsyncMock
        ) as mock_telemetry,
        patch("agent.browser.stealth.humanized_type", new_callable=AsyncMock),
    ):
        with pytest.raises(ExecutionError, match="Comment submit button not found"):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Great update!",
                item_id="item_drift_btn",
                dry_run=False,
                simulate_dwell=False,
            )

        mock_telemetry.assert_awaited_once()
        kwargs = mock_telemetry.call_args.kwargs
        assert kwargs["trigger"] == "comment_submit_btn_drift"
        assert kwargs["item_id"] == "item_drift_btn"


@pytest.mark.asyncio
async def test_post_comment_verification_timeout_captures_telemetry(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"

    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=0)
    comment_btn.click = AsyncMock()

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=1)
    comment_box.click = AsyncMock()
    comment_box.inner_text = AsyncMock(return_value="Still has text")

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=1)
    submit_btn.click = AsyncMock()
    submit_btn.is_visible = AsyncMock(return_value=True)
    submit_btn.get_attribute = AsyncMock(return_value=None)

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit-button" in selector:
            loc.first = submit_btn
            loc.count = AsyncMock(return_value=1)
        elif "button[aria-label*='Comment']" in selector or "comment-button" in selector:
            loc.first = comment_btn
            loc.count = AsyncMock(return_value=0)
        elif "comment-item" in selector:
            loc.count = AsyncMock(return_value=0)
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.count = AsyncMock(return_value=0)
        else:
            loc.first = comment_box
            loc.count = AsyncMock(return_value=1)
        return loc

    page.locator = MagicMock(side_effect=locator_mock)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with (
        patch(
            "agent.browser.telemetry.capture_dom_telemetry", new_callable=AsyncMock
        ) as mock_telemetry,
        patch("agent.browser.stealth.humanized_type", new_callable=AsyncMock),
    ):
        with pytest.raises(SubmissionVerificationError):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Verifying timeout...",
                item_id="item_verify_timeout",
                dry_run=False,
                verification_timeout=0.1,
                simulate_dwell=False,
            )

        mock_telemetry.assert_awaited_once()
        kwargs = mock_telemetry.call_args.kwargs
        assert kwargs["trigger"] == "comment_verification_timeout"
        assert kwargs["item_id"] == "item_verify_timeout"


@pytest.mark.asyncio
async def test_create_post_ui_drift_captures_telemetry(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    start_btn = MagicMock()
    start_btn.count = AsyncMock(return_value=0)
    page.locator.return_value.first = start_btn

    executor = ActionExecutor(page, base_settings)

    with patch(
        "agent.browser.telemetry.capture_dom_telemetry", new_callable=AsyncMock
    ) as mock_telemetry:
        with pytest.raises(ExecutionError, match="Start a post button not found"):
            await executor.create_post(
                post_text="New post test",
                item_id="post_ui_drift_1",
                dry_run=False,
            )

        mock_telemetry.assert_awaited_once()
        kwargs = mock_telemetry.call_args.kwargs
        assert kwargs["trigger"] == "create_post_ui_drift"
        assert kwargs["item_id"] == "post_ui_drift_1"


@pytest.mark.asyncio
async def test_create_post_verification_timeout_captures_telemetry(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    start_btn = MagicMock()
    start_btn.count = AsyncMock(return_value=1)
    start_btn.click = AsyncMock()

    editor = MagicMock()
    editor.count = AsyncMock(return_value=1)

    post_btn = MagicMock()
    post_btn.count = AsyncMock(return_value=1)
    post_btn.click = AsyncMock()

    modal = MagicMock()
    modal.is_visible = AsyncMock(return_value=True)

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Start a post" in selector:
            loc.first = start_btn
            loc.count = AsyncMock(return_value=1)
        elif "share-box-modal" in selector:
            loc.first = modal
            loc.count = AsyncMock(return_value=1)
        elif "ql-editor" in selector or "textbox" in selector:
            loc.first = editor
            loc.count = AsyncMock(return_value=1)
        elif "share-actions__primary-action" in selector:
            loc.first = post_btn
            loc.count = AsyncMock(return_value=1)
        elif "toast" in selector or "alert" in selector:
            loc.count = AsyncMock(return_value=0)
        else:
            loc.count = AsyncMock(return_value=0)
        return loc

    page.locator = MagicMock(side_effect=locator_mock)

    executor = ActionExecutor(page, base_settings)

    with (
        patch(
            "agent.browser.telemetry.capture_dom_telemetry", new_callable=AsyncMock
        ) as mock_telemetry,
        patch("agent.browser.stealth.humanized_type", new_callable=AsyncMock),
    ):
        with pytest.raises(SubmissionVerificationError):
            await executor.create_post(
                post_text="New post timeout test",
                item_id="post_timeout_001",
                dry_run=False,
                verification_timeout=0.1,
            )

        mock_telemetry.assert_awaited_once()
        kwargs = mock_telemetry.call_args.kwargs
        assert kwargs["trigger"] == "create_post_verification_timeout"
        assert kwargs["item_id"] == "post_timeout_001"


@pytest.mark.asyncio
async def test_executor_telemetry_failure_does_not_break_error_workflow(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=0)
    page.locator.return_value.first = comment_box

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with patch(
        "agent.browser.telemetry.capture_dom_telemetry",
        new_callable=AsyncMock,
        side_effect=Exception("Disk full or timeout in telemetry"),
    ):
        with pytest.raises(ExecutionError, match="Comment input box not found"):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Testing resilience",
                item_id="resilience_item",
                dry_run=False,
            )


@pytest.mark.asyncio
async def test_upload_screenshot_to_r2_missing_config_returns_local_path(
    base_settings: Settings, tmp_path: Path
) -> None:
    page = MagicMock()
    executor = ActionExecutor(page, base_settings)
    test_file = tmp_path / "shot.png"
    test_file.write_bytes(b"image-bytes")

    result = await executor._upload_screenshot_to_r2(str(test_file), "test_suffix")
    assert result == str(test_file)


@pytest.mark.asyncio
async def test_upload_screenshot_to_r2_missing_file_returns_path(
    base_settings: Settings,
) -> None:
    base_settings.worker_url = "https://relay.workers.dev"
    base_settings.desktop_api_secret = SecretStr("secret-123")
    page = MagicMock()
    executor = ActionExecutor(page, base_settings)

    result = await executor._upload_screenshot_to_r2("/nonexistent/path/shot.png", "test_suffix")
    assert result == "/nonexistent/path/shot.png"


@pytest.mark.asyncio
async def test_upload_screenshot_to_r2_success(base_settings: Settings, tmp_path: Path) -> None:
    base_settings.worker_url = "https://relay.workers.dev"
    base_settings.desktop_api_secret = SecretStr("secret-123")
    page = MagicMock()
    executor = ActionExecutor(page, base_settings)

    test_file = tmp_path / "success.png"
    test_file.write_bytes(b"png-data-bytes")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock, return_value=mock_resp) as mock_put:
        r2_key = await executor._upload_screenshot_to_r2(str(test_file), "success_comment_abc")
        assert r2_key == "screenshots/success_comment_abc.png"
        mock_put.assert_awaited_once_with(
            "https://relay.workers.dev/api/media/screenshots/success_comment_abc.png",
            content=b"png-data-bytes",
            headers={
                "Authorization": "Bearer secret-123",
                "Content-Type": "image/png",
            },
        )


@pytest.mark.asyncio
async def test_upload_screenshot_to_r2_http_failure_falls_back_to_local_path(
    base_settings: Settings, tmp_path: Path
) -> None:
    base_settings.worker_url = "https://relay.workers.dev"
    base_settings.desktop_api_secret = SecretStr("secret-123")
    page = MagicMock()
    executor = ActionExecutor(page, base_settings)

    test_file = tmp_path / "fail.png"
    test_file.write_bytes(b"png-data-bytes")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock, return_value=mock_resp):
        r2_key = await executor._upload_screenshot_to_r2(str(test_file), "fail_key")
        assert r2_key == str(test_file)


@pytest.mark.asyncio
async def test_upload_screenshot_to_r2_network_exception_falls_back_to_local_path(
    base_settings: Settings, tmp_path: Path
) -> None:
    base_settings.worker_url = "https://relay.workers.dev"
    base_settings.desktop_api_secret = SecretStr("secret-123")
    page = MagicMock()
    executor = ActionExecutor(page, base_settings)

    test_file = tmp_path / "err.png"
    test_file.write_bytes(b"png-data-bytes")

    with patch(
        "httpx.AsyncClient.put",
        new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        r2_key = await executor._upload_screenshot_to_r2(str(test_file), "err_key")
        assert r2_key == str(test_file)


@pytest.mark.asyncio
async def test_post_comment_dry_run_stores_r2_key_when_configured(
    base_settings: Settings, tmp_path: Path
) -> None:
    base_settings.worker_url = "https://relay.workers.dev"
    base_settings.desktop_api_secret = SecretStr("secret-123")
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"

    executor = ActionExecutor(page, base_settings, debug_dir=tmp_path)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    async def fake_screenshot(path: str, full_page: bool = False) -> None:
        Path(path).write_bytes(b"screenshot-bytes")

    page.screenshot = AsyncMock(side_effect=fake_screenshot)

    mock_resp = MagicMock(status_code=200)
    with patch("httpx.AsyncClient.put", new_callable=AsyncMock, return_value=mock_resp) as mock_put:
        result = await executor.post_comment(
            post_url=page.url,
            comment_text="Insightful comment",
            item_id="dry001",
            dry_run=True,
        )
        assert result.success is True
        assert result.screenshot_path == "screenshots/dryrun_comment_dry001.png"
        assert mock_put.await_count == 1
