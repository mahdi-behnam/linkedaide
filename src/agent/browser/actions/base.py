"""Shared helper utilities and base typing for browser action mixins."""

from __future__ import annotations

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
