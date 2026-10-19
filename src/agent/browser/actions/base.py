"""Shared helper utilities and base typing for browser action mixins."""

from __future__ import annotations

import inspect
from typing import Any


async def _safe_count(locator: Any) -> int:
    """Safely count locator elements handling Playwright async and unit test mocks."""
    try:
        cnt = locator.count()
        if hasattr(cnt, "__await__"):
            cnt_val = await cnt
            return int(cnt_val)
        return int(cnt)
    except Exception:
        return 0


async def _safe_scroll(locator: Any) -> None:
    """Safely scroll element into view handling Playwright async and unit test mocks."""
    try:
        if hasattr(locator, "scroll_into_view_if_needed"):
            res = locator.scroll_into_view_if_needed()
            if inspect.isawaitable(res):
                await res
    except Exception:
        pass


async def _safe_mouse_move(page: Any, x: float = 0, y: float = 0) -> None:
    """Safely move mouse handling Playwright async and unit test mocks."""
    try:
        if hasattr(page, "mouse") and hasattr(page.mouse, "move"):
            res = page.mouse.move(x, y)
            if inspect.isawaitable(res):
                await res
    except Exception:
        pass


async def _safe_wait_for(locator: Any, state: str = "visible", timeout: float = 5000) -> None:
    """Safely wait for element state handling Playwright async and unit test mocks."""
    try:
        if hasattr(locator, "wait_for"):
            res = locator.wait_for(state=state, timeout=timeout)
            if inspect.isawaitable(res):
                await res
    except Exception:
        pass
