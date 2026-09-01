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
    PostNoLongerAvailableError,
    SessionExpiredError,
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
async def test_post_comment_live_success(base_settings: Settings) -> None:
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

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=1)
    submit_btn.click = AsyncMock()

    def locator_side_effect(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit" in selector or "submit-button" in selector:
            loc.first = submit_btn
        elif (
            "textbox" in selector
            or "ql-editor" in selector
            or "ProseMirror" in selector
            or "tiptap" in selector
        ):
            loc.first = comment_box
        elif "comment-button" in selector or "button" in selector:
            loc.first = comment_btn
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Live comment test",
        item_id="live001",
        dry_run=False,
    )

    assert result.success is True
    assert result.comment_text == "Live comment test"
    assert comment_btn.click.called
    assert submit_btn.click.called
