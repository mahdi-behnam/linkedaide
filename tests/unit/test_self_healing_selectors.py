"""Unit tests for 4-tier self-healing selector engine and fallback pyramid hierarchy."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.browser.selectors import (
    LINKEDIN_SELECTORS,
    SelectorTier,
    SelfHealingSelectorEngine,
)
from agent.errors import SelectorDriftError


@pytest.fixture
def mock_page() -> MagicMock:
    """Fixture providing a mocked Playwright Page."""
    page = MagicMock()
    return page


@pytest.fixture
def mock_state_store() -> MagicMock:
    """Fixture providing a mocked BaseStateStore."""
    store = MagicMock()
    store.get_key.return_value = None
    return store


def _configure_locator_visibility(
    mock_page: MagicMock, visibility_map: dict[str, bool | Exception]
) -> dict[str, MagicMock]:
    """Helper to configure visibility for multiple selectors on mock_page."""
    locators: dict[str, MagicMock] = {}

    def locator_side_effect(selector: str) -> MagicMock:
        if selector not in locators:
            loc = MagicMock()
            outcome = visibility_map.get(selector, False)
            if isinstance(outcome, Exception):
                loc.first.is_visible = AsyncMock(side_effect=outcome)
            else:
                loc.first.is_visible = AsyncMock(return_value=outcome)
            loc.first.click = AsyncMock()
            locators[selector] = loc
        return locators[selector]

    mock_page.locator.side_effect = locator_side_effect
    return locators


@pytest.mark.asyncio
async def test_tier_1_immediate_resolution(
    mock_page: MagicMock, mock_state_store: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Tier 1: Canonical selector succeeds immediately without warnings or store writes."""
    candidates = [
        "button[data-control-name='comment_post']",  # Tier 1 (canonical)
        "button[role='button'][aria-label='Post comment']",  # Tier 2 (AXTree)
        "button:has-text('Comment')",  # Tier 3 (Text heuristic)
    ]
    _configure_locator_visibility(
        mock_page,
        {
            candidates[0]: True,
            candidates[1]: True,
            candidates[2]: True,
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)

    with caplog.at_level(logging.WARNING):
        loc, sel = await engine.resolve_locator(mock_page, "comment_submit", candidates)

    assert sel == candidates[0]
    assert loc is not None
    # No self-healing warning should be emitted for canonical success
    assert "self-healing healed" not in caplog.text
    # State store should not be written to when canonical works
    mock_state_store.put_key.assert_not_called()
    assert "comment_submit" not in engine.overrides


@pytest.mark.asyncio
async def test_tier_2_fallback_resolution_when_tier_1_fails(
    mock_page: MagicMock, mock_state_store: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Tier 2 fallback: Tier 1 fails, Tier 2 succeeds; triggers warning and store update."""
    candidates = [
        "button[data-control-name='comment_post']",  # Tier 1 fails
        "button[role='button'][aria-label='Post comment']",  # Tier 2 succeeds
        "button:has-text('Comment')",  # Tier 3
    ]
    _configure_locator_visibility(
        mock_page,
        {
            candidates[0]: False,
            candidates[1]: True,
            candidates[2]: False,
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)

    with caplog.at_level(logging.WARNING):
        loc, sel = await engine.resolve_locator(mock_page, "comment_submit", candidates)

    assert sel == candidates[1]
    assert loc is not None
    # Warning must be logged
    assert (
        "Canonical selector for comment_submit failed; self-healing healed to tier candidate"
        in caplog.text
    )
    assert candidates[1] in caplog.text

    # In-memory override updated
    assert engine.overrides["comment_submit"] == candidates[1]

    # Store persistence called
    mock_state_store.put_key.assert_called_once_with(
        "selector_overrides", {"comment_submit": candidates[1]}
    )


@pytest.mark.asyncio
async def test_tier_3_fallback_resolution_when_tier_1_and_2_fail(
    mock_page: MagicMock, mock_state_store: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Tier 3 fallback: Tier 1 & 2 fail, Tier 3 text heuristic succeeds."""
    candidates = [
        "div[data-control-name='comment_box']",  # Tier 1 fails
        "div[role='textbox'][aria-label*='comment' i]",  # Tier 2 fails
        "div.ql-editor:has-text('Add a comment')",  # Tier 3 succeeds
    ]
    _configure_locator_visibility(
        mock_page,
        {
            candidates[0]: False,
            candidates[1]: False,
            candidates[2]: True,
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)

    with caplog.at_level(logging.WARNING):
        loc, sel = await engine.resolve_locator(mock_page, "comment_box", candidates)

    assert sel == candidates[2]
    assert engine.overrides["comment_box"] == candidates[2]
    mock_state_store.put_key.assert_called_once_with(
        "selector_overrides", {"comment_box": candidates[2]}
    )


@pytest.mark.asyncio
async def test_tier_4_dynamic_override_used_first(
    mock_page: MagicMock, mock_state_store: MagicMock
) -> None:
    """Tier 4: Cached override from previous runs is verified first, skipping earlier tiers."""
    candidates = [
        "button[data-control-name='comment_post']",  # Canonical
        "button[role='button']",
    ]
    cached_override = "button.cached-healed-selector"

    mock_state_store.get_key.return_value = {"comment_submit": cached_override}

    _configure_locator_visibility(
        mock_page,
        {
            cached_override: True,
            candidates[0]: True,  # Even though canonical is also present, cached is used
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)
    assert engine.overrides["comment_submit"] == cached_override

    loc, sel = await engine.resolve_locator(mock_page, "comment_submit", candidates)
    assert sel == cached_override


@pytest.mark.asyncio
async def test_tier_4_stale_override_falls_back_to_candidates(
    mock_page: MagicMock, mock_state_store: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Tier 4 stale override: Cached override fails, falls back to candidates."""
    candidates = [
        "button[data-control-name='comment_post']",  # Canonical fails
        "button.new-fallback-tier2",  # New fallback succeeds
    ]
    stale_override = "button.old-stale-selector"

    mock_state_store.get_key.return_value = f'{{"comment_submit": "{stale_override}"}}'

    _configure_locator_visibility(
        mock_page,
        {
            stale_override: False,
            candidates[0]: False,
            candidates[1]: True,
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)
    with caplog.at_level(logging.WARNING):
        loc, sel = await engine.resolve_locator(mock_page, "comment_submit", candidates)

    assert sel == candidates[1]
    assert engine.overrides["comment_submit"] == candidates[1]
    mock_state_store.put_key.assert_called_with(
        "selector_overrides", {"comment_submit": candidates[1]}
    )


@pytest.mark.asyncio
async def test_total_drift_failure_raises_selector_drift_error(
    mock_page: MagicMock, mock_state_store: MagicMock
) -> None:
    """Total drift: All candidate selectors fail, raises SelectorDriftError."""
    candidates = [
        "button[data-control-name='submit']",
        "button[role='button']",
        "button:has-text('Submit')",
    ]
    _configure_locator_visibility(
        mock_page,
        {
            candidates[0]: False,
            candidates[1]: False,
            candidates[2]: False,
        },
    )

    engine = SelfHealingSelectorEngine(state_store=mock_state_store)

    with pytest.raises(SelectorDriftError) as exc_info:
        await engine.resolve_locator(mock_page, "post_submit", candidates)

    assert "All self-healing selector candidates failed for 'post_submit'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_find_and_click(mock_page: MagicMock) -> None:
    """Test find_and_click resolves and clicks the element."""
    candidates = ["button.primary", "button.secondary"]
    locators = _configure_locator_visibility(
        mock_page,
        {
            candidates[0]: False,
            candidates[1]: True,
        },
    )

    engine = SelfHealingSelectorEngine()
    await engine.find_and_click(mock_page, "test_action", candidates)

    locators[candidates[1]].first.click.assert_awaited_once()


def test_selector_tier_and_catalog() -> None:
    """Test SelectorTier enum and LINKEDIN_SELECTORS catalog integrity."""
    assert SelectorTier.TIER_1_CANONICAL == 1
    assert SelectorTier.TIER_2_AXTREE == 2
    assert SelectorTier.TIER_3_SEMANTIC_TEXT == 3
    assert SelectorTier.TIER_4_DYNAMIC_CACHE == 4

    assert "comment_box" in LINKEDIN_SELECTORS
    assert "comment_submit" in LINKEDIN_SELECTORS
    assert "post_input" in LINKEDIN_SELECTORS
    assert "post_editor" in LINKEDIN_SELECTORS
    assert "post_submit" in LINKEDIN_SELECTORS
    assert len(LINKEDIN_SELECTORS["comment_box"]) >= 3
