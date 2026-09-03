"""Unit tests for browser DOM telemetry diagnostics and sanitization."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.browser.telemetry import (
    DOMTelemetryRecord,
    capture_dom_telemetry,
    count_nodes,
    sanitize_dom_tree,
    sanitize_text,
    sanitize_url,
)


def test_sanitize_url_redacts_credentials_and_tokens() -> None:
    raw_url = "https://user:password@www.linkedin.com/feed/?auth_token=secret123&trk=feed_nav&session_key=xyz456"
    sanitized = sanitize_url(raw_url)

    assert "password@" not in sanitized
    assert "user:" not in sanitized
    assert "secret123" not in sanitized
    assert "xyz456" not in sanitized
    assert "auth_token=%5BREDACTED%5D" in sanitized or "auth_token=[REDACTED]" in sanitized
    assert "trk=feed_nav" in sanitized


def test_sanitize_text_redacts_emails_and_phone_numbers() -> None:
    sample_text = (
        "Contact me at founder@startup.io or support@domain.co.uk. "
        "Call +1 (555) 123-4567 or +44 20 7946 0958 for urgent matters."
    )
    sanitized = sanitize_text(sample_text)

    assert "founder@startup.io" not in sanitized
    assert "support@domain.co.uk" not in sanitized
    assert "555" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_PHONE]" in sanitized


def test_sanitize_dom_tree_from_html_strips_sensitive_elements_and_attrs() -> None:
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <script>alert("evil");</script>
        <style>body { color: red; }</style>
      </head>
      <body>
        <svg><path d="M10 10"/></svg>
        <div class="user-profile container" data-token="super-secret-token" data-view="profile">
          <input type="password" name="pwd" value="SecretPassword123"/>
          <input type="text" name="email" value="alice@example.com"/>
          <p class="bio">Reach me at test@example.com or +1 800-555-0199.</p>
        </div>
      </body>
    </html>
    """
    tree = sanitize_dom_tree(html)

    # Convert tree to JSON string for easy structural assertions
    tree_json = json.dumps(tree)

    assert "script" not in tree_json.lower() or '"tag": "script"' not in tree_json
    assert '"tag": "style"' not in tree_json
    assert '"tag": "svg"' not in tree_json
    assert '"tag": "path"' not in tree_json
    assert "super-secret-token" not in tree_json
    assert "SecretPassword123" not in tree_json
    assert "alice@example.com" not in tree_json
    assert "[REDACTED_PASSWORD]" in tree_json
    assert "[REDACTED_VALUE]" in tree_json
    assert "[REDACTED_EMAIL]" in tree_json
    assert "[REDACTED_PHONE]" in tree_json


def test_sanitize_dom_tree_from_dict_strips_sensitive_data() -> None:
    raw_dict = {
        "tag": "div",
        "classes": ["feed-card", "secret_auth_token"],
        "attrs": {
            "id": "post-101",
            "data-auth": "bearer token123",
            "type": "text",
            "value": "user input text",
        },
        "text": "Email me at dev@example.com",
        "children": [
            {"tag": "script", "text": "var x = 1;"},
            {"tag": "p", "text": "Call +1-800-555-1212"},
        ],
    }

    sanitized = sanitize_dom_tree(raw_dict)

    assert sanitized["tag"] == "div"
    assert "secret_auth_token" not in sanitized["classes"]
    assert sanitized["attrs"]["data-auth"] == "[REDACTED]"
    assert sanitized["attrs"]["value"] == "[REDACTED_VALUE]"
    assert "[REDACTED_EMAIL]" in sanitized.get("text", "")
    assert len(sanitized.get("children", [])) == 1
    assert sanitized["children"][0]["tag"] == "p"
    assert "[REDACTED_PHONE]" in sanitized["children"][0]["text"]


def test_sanitize_dom_tree_bounds_depth_and_node_count() -> None:
    # Construct a deeply nested tree (>15 levels)
    current: dict[str, Any] = {"tag": "div", "children": []}
    root = current
    for i in range(20):
        child: dict[str, Any] = {"tag": "div", "attrs": {"id": f"depth-{i}"}, "children": []}
        current["children"] = [child]
        current = child

    sanitized = sanitize_dom_tree(root)

    # Traverse depth
    depth = 0
    node: dict[str, Any] | None = sanitized
    while node and "children" in node and node["children"]:
        depth += 1
        node = node["children"][0]

    assert depth <= 10


def test_count_nodes() -> None:
    tree = {
        "tag": "div",
        "children": [
            {"tag": "p"},
            {"tag": "span", "children": [{"tag": "b"}]},
        ],
    }
    assert count_nodes(tree) == 4


def test_dom_telemetry_record_model() -> None:
    record = DOMTelemetryRecord(
        trigger="test_trigger",
        url_sanitized="https://www.linkedin.com/feed/",
        target_selector="div.feed",
        item_id="pending_123",
        node_count=5,
        structure={"tag": "div"},
    )
    dumped = record.model_dump()
    assert dumped["telemetry_version"] == "1.0"
    assert dumped["trigger"] == "test_trigger"
    assert dumped["target_selector"] == "div.feed"
    assert dumped["item_id"] == "pending_123"
    assert dumped["node_count"] == 5


@pytest.mark.asyncio
async def test_capture_dom_telemetry_success(tmp_path: Path) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/?auth=token"
    mock_structure = {
        "structure": {
            "tag": "main",
            "classes": ["scaffold-layout__main"],
            "attrs": {"id": "main-content"},
            "children": [
                {
                    "tag": "div",
                    "classes": ["feed-shared-update-v2"],
                    "attrs": {"data-urn": "urn:li:activity:1001"},
                    "text": "Hello world from test",
                }
            ],
        },
        "node_count": 2,
    }
    page.evaluate = AsyncMock(return_value=mock_structure)

    output_path = await capture_dom_telemetry(
        page,
        trigger="feed_container_drift",
        telemetry_dir=tmp_path,
        target_selector="main",
        item_id="test_item",
    )

    assert output_path is not None
    file_path = Path(output_path)
    assert file_path.exists()

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["telemetry_version"] == "1.0"
    assert data["trigger"] == "feed_container_drift"
    assert data["target_selector"] == "main"
    assert data["item_id"] == "test_item"
    assert data["node_count"] == 2
    assert data["structure"]["tag"] == "main"
    assert "token" not in data["url_sanitized"]


@pytest.mark.asyncio
async def test_capture_dom_telemetry_fallback_to_page_content(tmp_path: Path) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(side_effect=Exception("JS evaluation failed"))
    page.content = AsyncMock(
        return_value="<html><body><div class='feed-card'>Post content</div></body></html>"
    )

    output_path = await capture_dom_telemetry(
        page,
        trigger="fallback_drift",
        telemetry_dir=tmp_path,
    )

    assert output_path is not None
    file_path = Path(output_path)
    assert file_path.exists()

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["trigger"] == "fallback_drift"
    assert data["structure"]["tag"] in {"html", "body", "div"}
    assert data["node_count"] >= 1


@pytest.mark.asyncio
async def test_capture_dom_telemetry_non_blocking_on_page_exception(tmp_path: Path) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(side_effect=Exception("Browser crashed"))
    page.content = AsyncMock(side_effect=Exception("Page closed"))

    output_path = await capture_dom_telemetry(
        page,
        trigger="crash_drift",
        telemetry_dir=tmp_path,
    )

    # Must return None and not raise
    assert output_path is None


@pytest.mark.asyncio
async def test_capture_dom_telemetry_non_blocking_on_timeout(tmp_path: Path) -> None:
    async def slow_evaluate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(5.0)
        return {}

    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(side_effect=slow_evaluate)
    page.content = AsyncMock(side_effect=slow_evaluate)

    start_time = asyncio.get_event_loop().time()
    output_path = await capture_dom_telemetry(
        page,
        trigger="timeout_drift",
        telemetry_dir=tmp_path,
        timeout_seconds=0.1,
    )
    elapsed = asyncio.get_event_loop().time() - start_time

    assert output_path is None
    assert elapsed < 1.0


def test_sanitize_dom_tree_offline_fixtures() -> None:
    fixtures_dir = Path("tests") / "fixtures" / "linkedin_feed_snapshots"
    feed_path = fixtures_dir / "feed.html"
    challenge_path = fixtures_dir / "challenge.html"

    if feed_path.exists():
        feed_tree = sanitize_dom_tree(feed_path.read_text(encoding="utf-8"))
        assert feed_tree["tag"] == "html"
        assert count_nodes(feed_tree) > 3

    if challenge_path.exists():
        challenge_tree = sanitize_dom_tree(challenge_path.read_text(encoding="utf-8"))
        assert challenge_tree["tag"] == "html"
        challenge_json = json.dumps(challenge_tree)
        assert "checkpoint-challenge" in challenge_json


def test_sanitize_url_empty_and_error_handling() -> None:
    assert sanitize_url("") == ""
    assert sanitize_url("https://[invalid-ipv6") == "[UNPARSEABLE_URL]"


def test_sanitize_text_empty() -> None:
    assert sanitize_text("") == ""


def test_count_nodes_empty() -> None:
    assert count_nodes({}) == 0


def test_sanitize_dom_tree_wrapper_structure_and_roles() -> None:
    wrapped = {
        "structure": {
            "tag": "div",
            "role": "navigation",
            "attrs": {
                "type": "password",
                "value": "supersecret",
                "data-secret": "token123",
            },
            "children": [{"tag": "span", "attrs": {"id": f"c_{i}"}} for i in range(60)],
        }
    }
    sanitized = sanitize_dom_tree(wrapped)
    assert sanitized["tag"] == "div"
    assert sanitized.get("role") == "navigation"
    assert sanitized["attrs"]["type"] == "password"
    assert sanitized["attrs"]["value"] == "[REDACTED_PASSWORD]"
    assert sanitized["attrs"]["data-secret"] == "[REDACTED]"
    # Max children is capped at 50
    assert len(sanitized.get("children", [])) <= 50


def test_html_parser_role_and_depth_limits() -> None:
    nested = (
        "<div role='main'>"
        + "<div>" * 15
        + "<span role='button' data-token='secret'>Click</span>"
        + "</div>" * 15
        + "</div>"
    )
    tree = sanitize_dom_tree(nested)
    assert tree["tag"] == "div"
    assert tree.get("role") == "main"


@pytest.mark.asyncio
async def test_capture_dom_telemetry_evaluate_direct_dict_and_url_error(tmp_path: Path) -> None:
    page = MagicMock()
    type(page).url = property(lambda _self: (_ for _ in ()).throw(RuntimeError("URL unavailable")))
    page.evaluate = AsyncMock(return_value={"tag": "div", "attrs": {"id": "direct_dict"}})

    output_path = await capture_dom_telemetry(
        page,
        trigger="direct_dict_drift",
        telemetry_dir=tmp_path,
    )
    assert output_path is not None
    data = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert data["structure"]["tag"] == "div"
    assert data["url_sanitized"] == ""


@pytest.mark.asyncio
async def test_capture_dom_telemetry_evaluate_returns_html_str(tmp_path: Path) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value="<div id='feed-eval'><p>Evaluated HTML</p></div>")

    output_path = await capture_dom_telemetry(
        page,
        trigger="html_eval_drift",
        telemetry_dir=tmp_path,
    )
    assert output_path is not None
    data = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert data["structure"]["tag"] in {"div", "p"}


@pytest.mark.asyncio
async def test_capture_dom_telemetry_no_evaluate_no_content_returns_empty_structure(
    tmp_path: Path,
) -> None:
    page = MagicMock(spec=[])
    page.url = "https://www.linkedin.com/feed/"

    output_path = await capture_dom_telemetry(
        page,
        trigger="no_eval_no_content",
        telemetry_dir=tmp_path,
    )
    assert output_path is not None
    data = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert data["structure"]["tag"] == "empty"
    assert data["node_count"] == 0


def test_sanitize_html_attribute_value_sensitive() -> None:
    html = (
        '<div id="test-id" data-custom="my-super-secret-token" aria-label="normal label">Text</div>'
    )
    tree = sanitize_dom_tree(html)
    assert tree["attrs"]["data-custom"] == "[REDACTED]"
    assert tree["attrs"]["aria-label"] == "normal label"


def test_sanitize_dict_attribute_value_sensitive_and_limits() -> None:
    dict_node = {
        "tag": "div",
        "attrs": {
            "data-custom": "contains_secret_word",
            "role": "button",
        },
        "children": [{"tag": "p", "children": [{"tag": "span"}]}],
    }
    from agent.browser.telemetry import _sanitize_dict_node

    res_limited = _sanitize_dict_node(dict_node, depth=11, counter=[0], max_depth=10)
    assert res_limited is None

    res_sanitized = _sanitize_dict_node(dict_node, depth=0, counter=[0])
    assert res_sanitized is not None
    assert res_sanitized["attrs"]["data-custom"] == "[REDACTED]"


def test_sanitize_dom_tree_parser_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent.browser import telemetry

    def broken_feed(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Parser failure")

    monkeypatch.setattr(telemetry._HTMLToDOMTreeParser, "feed", broken_feed)
    res = telemetry.sanitize_dom_tree("<html><body>Some text</body></html>")
    assert res["tag"] == "empty"
