"""Sanitized DOM telemetry extraction and persistence for selector drift diagnostics."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

from agent.browser.telemetry_sanitizer import (
    EMAIL_REGEX,
    EXCLUDED_TAGS,
    JS_DOM_EXTRACTOR,
    PHONE_REGEX,
    SENSITIVE_ATTR_KEYWORDS,
    VOID_TAGS,
    DOMTelemetryRecord,
    _HTMLToDOMTreeParser,
    _is_sensitive,
    _sanitize_dict_node,
    count_nodes,
    sanitize_dom_tree,
    sanitize_text,
    sanitize_url,
)


async def capture_dom_telemetry(
    page: Page,
    trigger: str,
    telemetry_dir: Path | None = None,
    target_selector: str | None = None,
    item_id: str | None = None,
    timeout_seconds: float = 3.0,
) -> str | None:
    """Capture sanitized structural DOM telemetry on drift or challenge.

    Guarantees:
    - Completely non-blocking: catches all exceptions and returns None.
    - Hard bounded timeout: bounded by timeout_seconds (default 3.0s).
    - Strict sanitization: strips credentials, tokens, cookies, emails, phone numbers.
    - Output written to debug/telemetry/{trigger}_{timestamp}.json.

    Args:
        page: Playwright Page object.
        trigger: Name of triggering condition (e.g. 'feed_container_drift').
        telemetry_dir: Optional override for destination directory.
        target_selector: Optional CSS selector that drifted or failed.
        item_id: Optional action item identifier.
        timeout_seconds: Hard execution timeout for DOM capture.

    Returns:
        str | None: Absolute path of written JSON telemetry file, or None if failed.
    """
    try:
        raw_url = ""
        try:
            if hasattr(page, "url"):
                raw_url = page.url if isinstance(page.url, str) else page.url()
        except Exception:
            raw_url = ""
        url_sanitized = sanitize_url(raw_url)

        async def _eval_dom() -> tuple[dict[str, Any], int]:
            # Try in-browser JS evaluation first
            if hasattr(page, "evaluate") and callable(page.evaluate):
                try:
                    res = await page.evaluate(JS_DOM_EXTRACTOR)
                    if isinstance(res, dict) and "structure" in res:
                        structure = sanitize_dom_tree(res["structure"])
                        return structure, count_nodes(structure)
                    elif isinstance(res, dict):
                        structure = sanitize_dom_tree(res)
                        return structure, count_nodes(structure)
                    elif isinstance(res, str):
                        structure = sanitize_dom_tree(res)
                        return structure, count_nodes(structure)
                except Exception as eval_err:
                    logger.debug("page.evaluate failed, trying page.content: %s", eval_err)

            # Fallback to page.content if evaluate failed or unavailable
            if hasattr(page, "content") and callable(page.content):
                html_str = await page.content()
                if isinstance(html_str, str):
                    structure = sanitize_dom_tree(html_str)
                    return structure, count_nodes(structure)

            return {"tag": "empty", "classes": [], "attrs": {}}, 0

        eval_task = asyncio.create_task(_eval_dom())
        try:
            structure, node_count = await asyncio.wait_for(
                asyncio.shield(eval_task),
                timeout=timeout_seconds,
            )
        except (TimeoutError, asyncio.TimeoutError):
            eval_task.cancel()
            try:
                await eval_task
            except (asyncio.CancelledError, Exception):
                pass
            raise TimeoutError(f"DOM telemetry capture timed out after {timeout_seconds}s")
        except asyncio.CancelledError:
            eval_task.cancel()
            try:
                await eval_task
            except (asyncio.CancelledError, Exception):
                pass
            raise

        timestamp = datetime.now(UTC)
        record = DOMTelemetryRecord(
            telemetry_version="1.0",
            timestamp=timestamp,
            trigger=trigger,
            url_sanitized=url_sanitized,
            target_selector=target_selector,
            item_id=item_id,
            node_count=node_count,
            structure=structure,
        )

        out_dir = telemetry_dir or (Path("debug") / "telemetry")
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_trigger = re.sub(r"[^\w\-]", "_", trigger)
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        out_path = out_dir / f"{safe_trigger}_{ts_str}.json"

        out_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Captured DOM telemetry diagnostic: %s", out_path)
        return str(out_path.resolve())

    except TimeoutError as err:
        logger.warning(
            "DOM telemetry capture timed out after %.1fs for trigger '%s': %s",
            timeout_seconds,
            trigger,
            err,
        )
        return None
    except Exception as err:
        logger.warning(
            "Failed to capture DOM telemetry for trigger '%s': %s",
            trigger,
            err,
        )
        return None


__all__ = [
    "DOMTelemetryRecord",
    "EMAIL_REGEX",
    "EXCLUDED_TAGS",
    "JS_DOM_EXTRACTOR",
    "PHONE_REGEX",
    "SENSITIVE_ATTR_KEYWORDS",
    "VOID_TAGS",
    "_HTMLToDOMTreeParser",
    "_is_sensitive",
    "_sanitize_dict_node",
    "capture_dom_telemetry",
    "count_nodes",
    "sanitize_dom_tree",
    "sanitize_text",
    "sanitize_url",
]
