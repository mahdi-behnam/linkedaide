"""Unit tests for ActionExecutor dry run and live write paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
        if "submit" in selector or "submit-button" in selector:
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
