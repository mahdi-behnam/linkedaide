"""Adversarial resilience and bot challenge stress tests for Milestone 2.

Empirically challenges:
1. Bot challenge detection before and during pre-comment reaction (BotDetectionError + screenshot).
2. Authwall / login redirect detection before and during reaction (SessionExpiredError).
3. Non-fatal DOM error degradation (missing reaction button, selector timeout, DOM exception) allowing comment submission to proceed.
4. Humanized dwell simulation execution and abort safety under fatal vs non-fatal conditions.
5. Case-insensitivity, whitespace tolerance, and unknown reaction fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.browser.executor import ActionExecutor
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    SessionExpiredError,
)


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test-challenger"),
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        dry_run=False,
    )


# ==============================================================================
# 1. BOT CHALLENGE DETECTION AND PROPAGATION TESTS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "challenge_url",
    [
        "https://www.linkedin.com/checkpoint/challenge/AZ12345",
        "https://www.linkedin.com/checkpoint/lg/login-challenge",
        "https://www.linkedin.com/security-verification?trk=checkpoint",
        "https://www.linkedin.com/feed/?captcha=required",
        "https://www.linkedin.com/checkpoint/arkoselabs-verify",
        "https://www.linkedin.com/feed/unusual activity",
        "https://www.linkedin.com/checkpoint/verify your identity",
        "https://www.linkedin.com/checkpoint/quick verification",
    ],
)
async def test_react_to_post_detects_all_challenge_patterns(
    base_settings: Settings, challenge_url: str
) -> None:
    """Verify react_to_post detects every known challenge pattern, takes screenshot, and raises."""
    page = MagicMock()
    page.url = challenge_url
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)

    with pytest.raises(BotDetectionError) as exc_info:
        await executor.react_to_post(
            reaction_type="like",
            item_id="chal_test_item",
            dry_run=False,
        )

    assert "Bot challenge during reaction check" in str(exc_info.value)
    # Verify screenshot was captured for challenge
    page.screenshot.assert_called_once()
    # Verify no DOM clicks or element lookups took place
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_post_comment_challenge_during_reaction_aborts_immediately(
    base_settings: Settings,
) -> None:
    """Verify that if a bot challenge triggers during pre-comment reaction,

    post_comment immediately propagates BotDetectionError and NEVER attempts
    comment typing, submitting, or post-dwell.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    # Mock react_to_post raising BotDetectionError
    executor.react_to_post = AsyncMock(  # type: ignore[method-assign]
        side_effect=BotDetectionError("Bot challenge detected on reaction")
    )

    with (
        patch("agent.browser.executor.humanized_dwell", new_callable=AsyncMock) as mock_dwell,
        pytest.raises(BotDetectionError) as exc_info,
    ):
        await executor.post_comment(
            post_url=page.url,
            comment_text="This comment must NOT be posted",
            item_id="bot_halt_001",
            dry_run=False,
            reaction_type="like",
            simulate_dwell=True,
        )

    assert "Bot challenge detected on reaction" in str(exc_info.value)
    # Pre-dwell was called once before reaction
    assert mock_dwell.call_count == 1
    # Reaction was attempted
    executor.react_to_post.assert_called_once()
    # Post-dwell and comment typing/submitting were NEVER reached
    page.locator.assert_not_called()


# ==============================================================================
# 2. AUTHWALL / LOGIN EXPIRATION DETECTION TESTS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authwall_url",
    [
        "https://www.linkedin.com/uas/login",
        "https://www.linkedin.com/login?fromSignIn=true",
        "https://www.linkedin.com/authwall?trk=rip",
        "https://www.linkedin.com/authwall",
    ],
)
async def test_react_to_post_detects_all_authwall_patterns(
    base_settings: Settings, authwall_url: str
) -> None:
    """Verify react_to_post detects every login/authwall pattern and raises SessionExpiredError."""
    page = MagicMock()
    page.url = authwall_url

    executor = ActionExecutor(page, base_settings)

    with pytest.raises(SessionExpiredError) as exc_info:
        await executor.react_to_post(
            reaction_type="like",
            item_id="authwall_test_item",
            dry_run=False,
        )

    assert "LinkedIn session expired during reaction check" in str(exc_info.value)
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_post_comment_session_expired_during_reaction_aborts_immediately(
    base_settings: Settings,
) -> None:
    """Verify SessionExpiredError during reaction propagates out of post_comment."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(  # type: ignore[method-assign]
        side_effect=SessionExpiredError("Session redirected to login")
    )

    with (
        patch("agent.browser.executor.humanized_dwell", new_callable=AsyncMock) as mock_dwell,
        pytest.raises(SessionExpiredError) as exc_info,
    ):
        await executor.post_comment(
            post_url=page.url,
            comment_text="This comment must NOT be posted",
            item_id="expired_halt_001",
            dry_run=False,
            reaction_type="insightful",
            simulate_dwell=True,
        )

    assert "Session redirected to login" in str(exc_info.value)
    assert mock_dwell.call_count == 1
    page.locator.assert_not_called()


# ==============================================================================
# 3. NON-FATAL DOM DEGRADATION & COMMENT PROCEEDING TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_react_to_post_missing_button_graceful_return_false(
    base_settings: Settings,
) -> None:
    """Verify missing reaction button returns False gracefully and logs warning without raising."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc
    page.locator = MagicMock(return_value=empty_loc)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="missing_btn", dry_run=False
    )
    assert result is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_exception",
    [
        RuntimeError("DOM node disconnected"),
        TimeoutError("Locator.click timed out after 3000ms"),
        Exception("Unexpected layout perturbation"),
    ],
)
async def test_react_to_post_catches_non_fatal_dom_errors(
    base_settings: Settings, error_exception: Exception
) -> None:
    """Verify react_to_post catches non-fatal DOM exceptions, logs warning, and returns False."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.click = AsyncMock(side_effect=error_exception)
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="dom_err_item", dry_run=False
    )
    assert result is False


@pytest.mark.asyncio
async def test_post_comment_proceeds_and_succeeds_when_pre_reaction_fails(
    base_settings: Settings,
) -> None:
    """Verify that when pre-reaction returns False (button missing or click error),

    post_comment proceeds with comment typing, submitting, and verification.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Valid comment text"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Valid comment text"),
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
    # Simulate react_to_post returning False due to non-fatal failure
    executor.react_to_post = AsyncMock(return_value=False)  # type: ignore[method-assign]

    with patch("agent.browser.executor.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await executor.post_comment(
            post_url=page.url,
            comment_text="Valid comment text",
            item_id="fallback_verify_001",
            dry_run=False,
            reaction_type="insightful",
            simulate_dwell=True,
        )

    assert result.success is True
    assert result.comment_text == "Valid comment text"
    assert result.error is None
    # Both dwell pauses occurred
    assert mock_dwell.call_count == 2
    # Submit button was clicked
    submit_btn.click.assert_called_once()


# ==============================================================================
# 4. ADVERSARIAL INPUT AND NORMALIZATION STRESS TESTS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_reaction", "expected_click_type"),
    [
        ("  LIKE  ", "like"),
        ("LiKe", "like"),
        ("", "like"),
        ("  ", "like"),
        ("  insightful  ", "insightful"),
        ("INSIGHTFUL", "insightful"),
        ("Celebrate", "celebrate"),
        ("SUPPORT", "support"),
        ("LOVE", "love"),
        ("funny", "funny"),
    ],
)
async def test_react_to_post_reaction_type_normalization(
    base_settings: Settings, raw_reaction: str, expected_click_type: str
) -> None:
    """Verify reaction_type is stripped and case-normalized properly."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.click = AsyncMock()
    react_btn.hover = AsyncMock()
    react_btn.first = react_btn

    menu_item = MagicMock()
    menu_item.count = AsyncMock(return_value=1)
    menu_item.click = AsyncMock()
    menu_item.first = menu_item

    def locator_side_effect(selector: str) -> MagicMock:
        if "data-test-reaction-type" in selector or "reactions-menu" in selector:
            return menu_item
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type=raw_reaction, item_id="norm_test", dry_run=False
    )
    assert result is True

    if expected_click_type == "like":
        react_btn.click.assert_called_once()
    else:
        react_btn.hover.assert_called_once()
        menu_item.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_unknown_reaction_falls_back_to_like(
    base_settings: Settings,
) -> None:
    """Verify unknown reaction type tries hover, finds 0 items, logs warning, and clicks Like."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:99999/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.hover = AsyncMock()
    react_btn.click = AsyncMock()
    react_btn.first = react_btn

    empty_menu = MagicMock()
    empty_menu.count = AsyncMock(return_value=0)
    empty_menu.first = empty_menu

    def locator_side_effect(selector: str) -> MagicMock:
        if "data-test-reaction-type" in selector or "reactions-menu" in selector:
            return empty_menu
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="totally_custom_type", item_id="unknown_reaction", dry_run=False
    )

    assert result is True
    react_btn.hover.assert_called_once()
    react_btn.click.assert_called_once()
