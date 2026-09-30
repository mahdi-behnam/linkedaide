"""Unit tests for BiometricController advanced behavioral biometrics."""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.browser.biometrics import BiometricController


@pytest.fixture
def mock_page() -> MagicMock:
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.down = AsyncMock()
    page.mouse.up = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_biometrics_init(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    assert controller.page == mock_page
    assert controller.delay_scale == 0.01
    assert controller._current_x == 100.0
    assert controller._current_y == 100.0


@pytest.mark.asyncio
async def test_move_to_bezier_steps_and_endpoint(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    controller._current_x = 50.0
    controller._current_y = 50.0

    target_x = 500.0
    target_y = 400.0
    steps = 25

    await controller.move_to(target_x, target_y, steps=steps)

    assert mock_page.mouse.move.call_count == steps
    last_call = mock_page.mouse.move.call_args_list[-1]
    final_x, final_y = last_call[0]

    assert math.isclose(final_x, target_x, abs_tol=1e-3)
    assert math.isclose(final_y, target_y, abs_tol=1e-3)
    assert controller._current_x == target_x
    assert controller._current_y == target_y


@pytest.mark.asyncio
async def test_move_to_curvature_non_collinear(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    controller._current_x = 0.0
    controller._current_y = 0.0

    target_x = 300.0
    target_y = 0.0
    steps = 20

    await controller.move_to(target_x, target_y, steps=steps)

    # In pure straight line, all y coordinates would be 0.
    # With biological orthogonal curvature, intermediate y values should deflect
    y_values = [call[0][1] for call in mock_page.mouse.move.call_args_list[:-1]]
    non_zero_deflection = any(abs(y) > 0.5 for y in y_values)
    assert non_zero_deflection, "Bézier trajectory should have biological orthogonal deflection"


@pytest.mark.asyncio
async def test_move_to_zero_distance_immediate_return(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    controller._current_x = 200.0
    controller._current_y = 200.0

    await controller.move_to(200.2, 200.3, steps=25)

    assert mock_page.mouse.move.call_count == 1
    assert controller._current_x == 200.2
    assert controller._current_y == 200.3


@pytest.mark.asyncio
async def test_click_element_with_bounding_box(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.bounding_box = AsyncMock(
        return_value={"x": 100.0, "y": 200.0, "width": 100.0, "height": 50.0}
    )

    await controller.click_element(locator)

    # Must move mouse into element bounds
    assert mock_page.mouse.move.called
    last_move = mock_page.mouse.move.call_args_list[-1][0]
    click_x, click_y = last_move

    assert 100.0 <= click_x <= 200.0
    assert 200.0 <= click_y <= 250.0

    # Must perform mouse down and mouse up
    assert mock_page.mouse.down.called
    assert mock_page.mouse.up.called


@pytest.mark.asyncio
async def test_click_element_fallback_when_bounding_box_missing(
    mock_page: MagicMock,
) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.bounding_box = AsyncMock(return_value=None)
    locator.click = AsyncMock()

    await controller.click_element(locator)

    assert locator.click.called
    assert not mock_page.mouse.down.called


@pytest.mark.asyncio
async def test_click_element_fallback_when_bounding_box_zero_size(
    mock_page: MagicMock,
) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.bounding_box = AsyncMock(return_value={"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0})
    locator.click = AsyncMock()

    await controller.click_element(locator)

    assert locator.click.called
    assert not mock_page.mouse.down.called


@pytest.mark.asyncio
async def test_type_text_focus_and_press_sequentially(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.focus = AsyncMock()
    locator.press_sequentially = AsyncMock()

    await controller.type_text(locator, "hi", typo_prob=0.0)

    assert locator.focus.called
    typed_keys = [c[0][0] for c in locator.press_sequentially.call_args_list]
    assert typed_keys == ["h", "i"]


@pytest.mark.asyncio
async def test_type_text_emulates_typos(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.focus = AsyncMock()
    locator.press_sequentially = AsyncMock()
    locator.press = AsyncMock()

    # Force 100% typo probability on a key with defined adjacent keys
    await controller.type_text(locator, "a", typo_prob=1.0)

    # With typo emulation:
    # 1. Typo adjacent key is typed
    # 2. Backspace is pressed
    # 3. Correct key 'a' is typed
    typed_keys = [c[0][0] for c in locator.press_sequentially.call_args_list]
    assert len(typed_keys) == 2
    assert typed_keys[1] == "a"
    assert locator.press.called
    assert locator.press.call_args[0][0] == "Backspace"


@pytest.mark.asyncio
async def test_type_text_punctuation_pause(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    locator = MagicMock()
    locator.focus = AsyncMock()
    locator.press_sequentially = AsyncMock()

    await controller.type_text(locator, "yes!", typo_prob=0.0)

    typed_keys = [c[0][0] for c in locator.press_sequentially.call_args_list]
    assert typed_keys == ["y", "e", "s", "!"]


@pytest.mark.asyncio
async def test_smooth_wheel_scroll_momentum_decay(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)

    total_pixels = 400
    steps = 8
    await controller.smooth_wheel_scroll(total_pixels, steps=steps)

    assert mock_page.mouse.wheel.call_count == steps

    deltas = [call[0][1] for call in mock_page.mouse.wheel.call_args_list]
    # Sum of all step deltas must equal total_pixels
    assert math.isclose(sum(deltas), total_pixels, abs_tol=1e-3)

    # Verify inertial momentum decay: early steps are significantly larger than late steps
    assert deltas[0] > deltas[-2]
    assert deltas[0] > deltas[1]


@pytest.mark.asyncio
async def test_smooth_wheel_scroll_zero_pixels(mock_page: MagicMock) -> None:
    controller = BiometricController(mock_page, delay_scale=0.01)
    await controller.smooth_wheel_scroll(0, steps=5)
    assert not mock_page.mouse.wheel.called
