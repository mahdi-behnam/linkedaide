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

# Elements excluded from telemetry due to lack of structural utility or potential security risk
EXCLUDED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "path",
    "iframe",
    "link",
    "meta",
    "template",
}

# Void HTML tags that cannot have children
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

# Sensitive keywords in attribute names or values requiring redaction
SENSITIVE_ATTR_KEYWORDS = (
    "pass",
    "token",
    "auth",
    "secret",
    "cookie",
    "key",
    "credential",
    "session",
)

# Regex patterns for redacting PII
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")

# In-browser DOM extraction JavaScript function
JS_DOM_EXTRACTOR = r"""
() => {
  const EXCLUDED = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "PATH", "IFRAME", "LINK", "META", "TEMPLATE"]);
  const SENSITIVE = ["pass", "token", "auth", "secret", "cookie", "key", "credential", "session"];
  const EMAIL_RE = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
  const PHONE_RE = /(?:\\+?\\d{1,3}[-.\\s]?)?\\(?\\d{2,4}\\)?[-.\\s]?\\d{3,4}[-.\\s]?\\d{3,4}/g;

  function redact(str) {
    if (!str) return "";
    return str.replace(EMAIL_RE, "[REDACTED_EMAIL]").replace(PHONE_RE, "[REDACTED_PHONE]");
  }

  function isSens(str) {
    if (!str) return false;
    const lower = str.toLowerCase();
    return SENSITIVE.some(k => lower.includes(k));
  }

  let count = 0;
  const MAX_NODES = 500;
  const MAX_DEPTH = 10;
  const MAX_CHILDREN = 50;

  function traverse(el, depth) {
    if (!el || count >= MAX_NODES || depth > MAX_DEPTH) return null;
    const tag = (el.tagName || "").toLowerCase();
    if (!tag || EXCLUDED.has(el.tagName)) return null;

    count++;
    const classes = el.classList ? Array.from(el.classList).slice(0, 20) : [];
    const role = el.getAttribute ? el.getAttribute("role") : null;
    const attrs = {};

    if (el.attributes) {
      for (let i = 0; i < el.attributes.length; i++) {
        const attr = el.attributes[i];
        const name = attr.name.toLowerCase();
        const val = attr.value;
        if (isSens(name)) {
          attrs[name] = "[REDACTED]";
        } else if (name === "value") {
          attrs[name] = (el.type === "password" || isSens(el.name) || isSens(el.id)) ? "[REDACTED_PASSWORD]" : "[REDACTED_VALUE]";
        } else if (name === "type" && val === "password") {
          attrs[name] = "password";
        } else if (name.startsWith("data-") || name.startsWith("aria-") || ["id", "name", "role", "href", "placeholder", "title"].includes(name)) {
          if (isSens(val) && !["role"].includes(name)) {
            attrs[name] = "[REDACTED]";
          } else {
            attrs[name] = redact(val).slice(0, 150);
          }
        }
      }
    }

    let text = "";
    if (el.childNodes) {
      for (let i = 0; i < el.childNodes.length; i++) {
        const child = el.childNodes[i];
        if (child.nodeType === 3) {
          const t = (child.textContent || "").trim();
          if (t) text += (text ? " " : "") + t;
        }
      }
    }
    if (text) {
      text = redact(text).slice(0, 100);
    }

    const res = { tag: tag, classes: classes, attrs: attrs };
    if (role) res.role = role;
    if (text) res.text = text;

    if (el.children && depth < MAX_DEPTH && count < MAX_NODES) {
      const children = [];
      const len = Math.min(el.children.length, MAX_CHILDREN);
      for (let i = 0; i < len; i++) {
        if (count >= MAX_NODES) break;
        const c = traverse(el.children[i], depth + 1);
        if (c) children.push(c);
      }
      if (children.length > 0) {
        res.children = children;
      }
    }
    return res;
  }

  const root = document.body || document.documentElement;
  const structure = traverse(root, 0) || { tag: "empty", classes: [], attrs: {} };
  return { structure: structure, node_count: count };
}
"""


class DOMTelemetryRecord(BaseModel):
    """Telemetry diagnostic record capturing sanitized DOM structure."""

    telemetry_version: str = "1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trigger: str
    url_sanitized: str
    target_selector: str | None = None
    item_id: str | None = None
    node_count: int = 0
    structure: dict[str, Any] = Field(default_factory=dict)


def sanitize_url(raw_url: str) -> str:
    """Sanitize URL by removing userinfo and redacting sensitive query parameters."""
    if not raw_url:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        netloc = parsed.netloc.split("@")[-1]
        if not parsed.query:
            return urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        safe_params: list[tuple[str, str]] = []
        for k, v in params:
            lower_k = k.lower()
            if any(s in lower_k for s in SENSITIVE_ATTR_KEYWORDS):
                safe_params.append((k, "[REDACTED]"))
            else:
                safe_params.append((k, v))
        new_query = urllib.parse.urlencode(safe_params)
        return urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, "", new_query, ""))
    except Exception:
        return "[UNPARSEABLE_URL]"


def sanitize_text(text: str) -> str:
    """Redact emails and phone numbers from raw text."""
    if not text:
        return ""
    redacted = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    redacted = PHONE_REGEX.sub("[REDACTED_PHONE]", redacted)
    return redacted.strip()


def _is_sensitive(text: str) -> bool:
    """Check whether text contains sensitive credential or auth keywords."""
    if not text:
        return False
    lower = text.lower()
    return any(keyword in lower for keyword in SENSITIVE_ATTR_KEYWORDS)


def count_nodes(structure: dict[str, Any]) -> int:
    """Recursively count nodes in a structural DOM tree."""
    if not structure:
        return 0
    count = 1
    for child in structure.get("children", []):
        if isinstance(child, dict):
            count += count_nodes(child)
    return count


class _HTMLToDOMTreeParser(HTMLParser):
    """Offline HTML parser converting raw HTML into a sanitized DOM tree."""

    def __init__(
        self,
        max_depth: int = 10,
        max_nodes: int = 500,
        max_children: int = 50,
    ) -> None:
        super().__init__()
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_children = max_children
        self.total_nodes = 0
        self.root: dict[str, Any] | None = None
        self.stack: list[dict[str, Any]] = []
        self.skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in EXCLUDED_TAGS or self.skip_stack:
            self.skip_stack.append(tag_lower)
            return

        if self.total_nodes >= self.max_nodes or len(self.stack) >= self.max_depth:
            return

        classes: list[str] = []
        role: str | None = None
        sanitized_attrs: dict[str, str] = {}
        input_type: str = "text"

        for attr_name, attr_val in attrs:
            name = attr_name.lower()
            val = attr_val or ""
            if name == "class":
                classes = [c for c in val.split() if not _is_sensitive(c)][:20]
            elif name == "role":
                role = val
            elif name == "type":
                input_type = val.lower()
                sanitized_attrs[name] = "password" if input_type == "password" else val[:50]
            elif _is_sensitive(name):
                sanitized_attrs[name] = "[REDACTED]"
            elif name == "value":
                if input_type == "password" or _is_sensitive(sanitized_attrs.get("name", "")):
                    sanitized_attrs[name] = "[REDACTED_PASSWORD]"
                else:
                    sanitized_attrs[name] = "[REDACTED_VALUE]"
            elif (
                name.startswith("data-")
                or name.startswith("aria-")
                or name in {"id", "name", "href", "placeholder", "title"}
            ):
                if _is_sensitive(val) and name not in {"role"}:
                    sanitized_attrs[name] = "[REDACTED]"
                else:
                    sanitized_attrs[name] = sanitize_text(val)[:150]

        node: dict[str, Any] = {
            "tag": tag_lower,
            "classes": classes,
            "attrs": sanitized_attrs,
        }
        if role:
            node["role"] = role

        if self.root is None:
            self.root = node
        elif self.stack:
            parent = self.stack[-1]
            children = parent.setdefault("children", [])
            if len(children) < self.max_children:
                children.append(node)

        self.total_nodes += 1
        if tag_lower not in VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if self.skip_stack:
            if self.skip_stack[-1] == tag_lower:
                self.skip_stack.pop()
            return

        if self.stack and self.stack[-1]["tag"] == tag_lower:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.skip_stack or not self.stack:
            return
        current = self.stack[-1]
        text = sanitize_text(data)
        if text:
            existing = current.get("text", "")
            combined = f"{existing} {text}".strip() if existing else text
            current["text"] = combined[:100]


def _sanitize_dict_node(
    node: dict[str, Any],
    depth: int,
    counter: list[int],
    max_depth: int = 10,
    max_nodes: int = 500,
    max_children: int = 50,
) -> dict[str, Any] | None:
    """Sanitize an existing node dictionary structure."""
    if counter[0] >= max_nodes or depth > max_depth:
        return None

    tag = str(node.get("tag", "")).lower()
    if not tag or tag in EXCLUDED_TAGS:
        return None

    counter[0] += 1

    classes = [
        str(c) for c in node.get("classes", []) if isinstance(c, str) and not _is_sensitive(c)
    ][:20]

    raw_attrs = node.get("attrs", {})
    attrs: dict[str, str] = {}
    input_type = ""
    if isinstance(raw_attrs, dict):
        if "type" in raw_attrs:
            input_type = str(raw_attrs["type"]).lower()

        for k, v in raw_attrs.items():
            name = str(k).lower()
            val = str(v)
            if _is_sensitive(name):
                attrs[name] = "[REDACTED]"
            elif name == "value":
                if input_type == "password" or _is_sensitive(str(raw_attrs.get("name", ""))):
                    attrs[name] = "[REDACTED_PASSWORD]"
                else:
                    attrs[name] = "[REDACTED_VALUE]"
            elif name == "type" and val == "password":
                attrs[name] = "password"
            elif (
                name.startswith("data-")
                or name.startswith("aria-")
                or name in {"id", "name", "role", "href", "placeholder", "title"}
            ):
                if _is_sensitive(val) and name != "role":
                    attrs[name] = "[REDACTED]"
                else:
                    attrs[name] = sanitize_text(val)[:150]

    res: dict[str, Any] = {
        "tag": tag,
        "classes": classes,
        "attrs": attrs,
    }

    role = node.get("role")
    if role and isinstance(role, str):
        res["role"] = role

    text = node.get("text")
    if text and isinstance(text, str):
        sanitized_t = sanitize_text(text)[:100]
        if sanitized_t:
            res["text"] = sanitized_t

    raw_children = node.get("children", [])
    if isinstance(raw_children, list) and depth < max_depth and counter[0] < max_nodes:
        sanitized_children: list[dict[str, Any]] = []
        for child in raw_children:
            if len(sanitized_children) >= max_children or counter[0] >= max_nodes:
                break
            if isinstance(child, dict):
                sc = _sanitize_dict_node(
                    child,
                    depth + 1,
                    counter,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                    max_children=max_children,
                )
                if sc is not None:
                    sanitized_children.append(sc)
        if sanitized_children:
            res["children"] = sanitized_children

    return res


def sanitize_dom_tree(root_element_or_dict: dict[str, Any] | str) -> dict[str, Any]:
    """Deterministically sanitize structural DOM nodes from either HTML or dict representation.

    Args:
        root_element_or_dict: Raw HTML string or DOM node dictionary.

    Returns:
        dict[str, Any]: Sanitized DOM node tree dictionary.
    """
    if isinstance(root_element_or_dict, str):
        parser = _HTMLToDOMTreeParser()
        try:
            parser.feed(root_element_or_dict)
            parser.close()
        except Exception as err:
            logger.debug("Failed parsing HTML string in sanitize_dom_tree: %s", err)
        return parser.root or {"tag": "empty", "classes": [], "attrs": {}}

    node = root_element_or_dict
    if "structure" in node and isinstance(node["structure"], dict):
        node = node["structure"]
    counter = [0]
    sanitized = _sanitize_dict_node(node, depth=0, counter=counter)
    return sanitized or {"tag": "empty", "classes": [], "attrs": {}}


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
