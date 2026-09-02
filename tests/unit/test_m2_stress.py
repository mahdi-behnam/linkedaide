"""Empirical stress tests and adversarial edge cases for Milestone 2.

Covers:
1. Reaction button selector fallback and menu popups.
2. Already-reacted state detection (aria-pressed="true", "unreact", "unlike").
3. Dry-run safety guarantees across all reaction types.
4. Bot detection and session expiration fatal propagation.
5. Non-fatal reaction failures and graceful continuation in post_comment.
6. Dwell simulation timing and bounds.
7. Settings resolution and precedence.
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
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        dry_run=True,
    )


# ==============================================================================
# 1. DRY RUN GUARANTEES ACROSS ALL REACTION TYPES
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reaction_type",
    [
        "like",
        "LIKE",
        "  like  ",
        "insightful",
        "INSIGHTFUL",
        "celebrate",
        "support",
        "love",
        "funny",
        "custom_unknown",
        "",
    ],
)
async def test_react_to_post_dry_run_guarantees_zero_dom_calls(
    base_settings: Settings, reaction_type: str
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    executor = ActionExecutor(page, base_settings)

    result = await executor.react_to_post(
        reaction_type=reaction_type, item_id="stress_dry_run", dry_run=True
    )
    assert result is True
    page.locator.assert_not_called()
    page.screenshot.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reaction_type",
    ["like", "insightful", "celebrate", "support", "love", "funny"],
)
async def test_post_comment_dry_run_guarantees_zero_dom_writes(
    base_settings: Settings, reaction_type: str
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Adversarial dry run comment",
        item_id="adv_dry_001",
        dry_run=True,
        reaction_type=reaction_type,
    )

    assert result.success is True
    assert result.action_type == "approve_comment"
    assert result.comment_text == "Adversarial dry run comment"
    page.locator.assert_not_called()


# ==============================================================================
# 2. ALREADY REACTED STATES (NO TOGGLING / UNLIKING)
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("aria_pressed", "aria_label"),
    [
        ("true", "React Like"),
        ("true", "Like"),
        ("true", ""),
        ("false", "Unreact to post"),
        ("false", "Unlike this post"),
        ("false", "Unreact (Insightful)"),
        (None, "unreact"),
        (None, "unlike"),
        ("true", "Unreact"),
        ("TRUE", "React Like"),
    ],
)
async def test_react_to_post_already_reacted_variants_prevent_click(
    base_settings: Settings, aria_pressed: str | None, aria_label: str
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            aria_pressed if attr == "aria-pressed" else aria_label if attr == "aria-label" else None
        )
    )
    react_btn.click = AsyncMock()
    react_btn.hover = AsyncMock()
    react_btn.first = react_btn
    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="already_reacted_stress", dry_run=False
    )

    assert result is True
    react_btn.click.assert_not_called()
    react_btn.hover.assert_not_called()


@pytest.mark.asyncio
async def test_react_to_post_not_reacted_proceeds_to_click(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
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
        reaction_type="like", item_id="not_reacted_stress", dry_run=False
    )

    assert result is True
    react_btn.click.assert_called_once()


# ==============================================================================
# 3. REACTION MENU POPUP & FALLBACK MECHANICS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reaction_type",
    ["insightful", "celebrate", "support", "love", "funny"],
)
async def test_react_to_post_menu_hover_and_click_success(
    base_settings: Settings, reaction_type: str
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.hover = AsyncMock()
    react_btn.first = react_btn

    menu_item = MagicMock()
    menu_item.count = AsyncMock(return_value=1)
    menu_item.click = AsyncMock()
    menu_item.first = menu_item

    def locator_side_effect(selector: str) -> MagicMock:
        if reaction_type.capitalize() in selector or reaction_type in selector:
            return menu_item
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type=reaction_type, item_id="menu_hover_stress", dry_run=False
    )

    assert result is True
    react_btn.hover.assert_called_once()
    menu_item.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_menu_hover_fails_fallback_to_like(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.hover = AsyncMock(side_effect=TimeoutError("Hover timeout"))
    react_btn.click = AsyncMock()
    react_btn.first = react_btn

    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="insightful", item_id="hover_fail_stress", dry_run=False
    )

    assert result is True
    react_btn.hover.assert_called_once()
    react_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_menu_item_click_fails_fallback_to_like(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.hover = AsyncMock()
    react_btn.click = AsyncMock()
    react_btn.first = react_btn

    menu_item = MagicMock()
    menu_item.count = AsyncMock(return_value=1)
    menu_item.click = AsyncMock(side_effect=RuntimeError("Menu item click intercepted"))
    menu_item.first = menu_item

    def locator_side_effect(selector: str) -> MagicMock:
        if "Insightful" in selector or "insightful" in selector:
            return menu_item
        return react_btn

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="insightful", item_id="menu_click_fail_stress", dry_run=False
    )

    assert result is True
    react_btn.hover.assert_called_once()
    menu_item.click.assert_called_once()
    react_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_react_to_post_both_menu_and_like_fail_returns_false(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"

    react_btn = MagicMock()
    react_btn.count = AsyncMock(return_value=1)
    react_btn.get_attribute = AsyncMock(return_value="false")
    react_btn.hover = AsyncMock()
    react_btn.click = AsyncMock(side_effect=RuntimeError("Element destroyed"))
    react_btn.first = react_btn

    page.locator = MagicMock(return_value=react_btn)

    executor = ActionExecutor(page, base_settings)
    result = await executor.react_to_post(
        reaction_type="like", item_id="total_fail_stress", dry_run=False
    )

    assert result is False


# ==============================================================================
# 4. BOT CHALLENGE & SESSION EXPIRED PROPAGATION
# ==============================================================================


@pytest.mark.asyncio
async def test_react_to_post_challenge_raises_bot_detection_error(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge/123"
    page.screenshot = AsyncMock()
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(BotDetectionError):
        await executor.react_to_post(reaction_type="like", item_id="chal_react", dry_run=False)


@pytest.mark.asyncio
async def test_react_to_post_authwall_raises_session_expired_error(base_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/authwall?trk=rip"
    page.screenshot = AsyncMock()
    executor = ActionExecutor(page, base_settings)

    with pytest.raises(SessionExpiredError):
        await executor.react_to_post(reaction_type="like", item_id="exp_react", dry_run=False)


@pytest.mark.asyncio
async def test_post_comment_challenge_during_reaction_stops_execution(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, base_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(side_effect=BotDetectionError("Challenge detected"))  # type: ignore[method-assign]

    with pytest.raises(BotDetectionError):
        await executor.post_comment(
            post_url=page.url,
            comment_text="Should not post",
            item_id="chal_in_react",
            dry_run=False,
            reaction_type="like",
            simulate_dwell=False,
        )

    executor.react_to_post.assert_called_once()
    page.locator.assert_not_called()


# ==============================================================================
# 5. DWELL TIMING AND HUMAN PAUSES
# ==============================================================================


@pytest.mark.asyncio
async def test_post_comment_dwell_called_before_and_after_reaction(
    base_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Dwell test comment"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="Dwell test comment")
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

    with patch("agent.browser.executor.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await executor.post_comment(
            post_url=page.url,
            comment_text="Dwell test comment",
            item_id="dwell_test_001",
            dry_run=False,
            verification_timeout=1.0,
            reaction_type="like",
            simulate_dwell=True,
        )

        assert result.success is True
        assert mock_dwell.call_count == 2
        # First call before reaction: (1.5, 3.5)
        assert mock_dwell.call_args_list[0].args == (1.5, 3.5)
        # Second call after reaction: (1.0, 2.5)
        assert mock_dwell.call_args_list[1].args == (1.0, 2.5)


# ==============================================================================
# 6. SETTINGS RESOLUTION AND PRECEDENCE
# ==============================================================================


@pytest.mark.asyncio
async def test_post_comment_reaction_precedence(base_settings: Settings) -> None:
    # Case A: Setting disabled, reaction_type=None -> no reaction
    base_settings.enable_pre_comment_reaction = False
    base_settings.default_reaction_type = "like"

    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
        inner_text=AsyncMock(return_value="Precedence comment"),
    )
    submit_btn = MagicMock(
        count=AsyncMock(return_value=1),
        click=AsyncMock(),
        is_disabled=AsyncMock(return_value=False),
    )
    comment_item = MagicMock(
        count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="Precedence comment")
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
        comment_text="Precedence comment",
        item_id="no_react",
        dry_run=False,
        verification_timeout=1.0,
        reaction_type=None,
        simulate_dwell=False,
    )

    assert result.success is True
    executor.react_to_post.assert_not_called()

    # Case B: Setting disabled, but explicit reaction_type="celebrate" -> reactions IS performed
    executor.react_to_post.reset_mock()
    result = await executor.post_comment(
        post_url=page.url,
        comment_text="Precedence comment",
        item_id="explicit_override",
        dry_run=False,
        verification_timeout=1.0,
        reaction_type="celebrate",
        simulate_dwell=False,
    )
    assert result.success is True
    executor.react_to_post.assert_called_once_with(
        reaction_type="celebrate",
        item_id="explicit_override",
        dry_run=False,
    )
