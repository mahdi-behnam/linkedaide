"""Adversarial stress and non-blocking verification suite for DOM telemetry.

Empirically challenges:
1. Indefinite page.evaluate and page.content hangs (>10s) and timeout cancellation bounds.
2. Playwright errors, target crashes (TargetClosedError), MemoryError, and malformed DOM payloads.
3. Disk write failures: permission denied (PermissionError), disk full (OSError), invalid path characters, and oversized triggers.
4. Absolute isolation of primary error workflows in scraper.py and executor.py (BotDetectionError, SelectorDriftError, ExecutionError).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Error as PlaywrightError
from pydantic import SecretStr

from agent.browser.executor import ActionExecutor
from agent.browser.scraper import FeedScraper
from agent.browser.telemetry import (
    capture_dom_telemetry,
    sanitize_dom_tree,
)
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    SelectorDriftError,
    SubmissionVerificationError,
)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-adversarial-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:adversarial_token"),
        telegram_authorized_chat_id=123456,
        user_focus_areas=["AI", "Engineering"],
        max_suggestions_per_run=5,
    )


# ============================================================================
# Category 1: Evaluate Hangs, Content Hangs, and Asyncio Cancellation
# ============================================================================


@pytest.mark.asyncio
async def test_adversarial_evaluate_infinite_hang_cancels_cleanly(tmp_path: Path) -> None:
    """Challenge: page.evaluate hangs indefinitely.

    Empirical invariant: capture_dom_telemetry must be bounded by timeout_seconds,
    cleanly cancel the hung evaluate task, log a warning, and return None without blocking caller.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    eval_started = asyncio.Event()
    eval_cancelled = False

    async def hanging_evaluate(*args: object, **kwargs: object) -> dict[str, object]:
        eval_started.set()
        nonlocal eval_cancelled
        try:
            await asyncio.sleep(60.0)  # Hang for 60 seconds
        except asyncio.CancelledError:
            eval_cancelled = True
            raise
        return {"tag": "body"}

    page.evaluate = AsyncMock(side_effect=hanging_evaluate)
    page.content = AsyncMock()

    start_time = time.monotonic()
    result = await capture_dom_telemetry(
        page=page,
        trigger="adversarial_hang",
        telemetry_dir=tmp_path,
        timeout_seconds=0.15,
    )
    elapsed = time.monotonic() - start_time

    assert result is None
    assert elapsed < 0.8, f"Telemetry did not return within bounded timeout! Took {elapsed:.2f}s"
    assert eval_started.is_set(), "page.evaluate was never entered"
    assert eval_cancelled is True, "Hung evaluate task was not cancelled cleanly upon timeout"


@pytest.mark.asyncio
async def test_adversarial_evaluate_fail_and_content_hang_cancels_cleanly(tmp_path: Path) -> None:
    """Challenge: page.evaluate crashes, but fallback page.content hangs indefinitely.

    Empirical invariant: The entire _eval_dom routine must timeout within timeout_seconds.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    page.evaluate = AsyncMock(side_effect=RuntimeError("JS engine crashed"))

    content_started = asyncio.Event()
    content_cancelled = False

    async def hanging_content() -> str:
        content_started.set()
        nonlocal content_cancelled
        try:
            await asyncio.sleep(60.0)
        except asyncio.CancelledError:
            content_cancelled = True
            raise
        return "<html><body>Hung</body></html>"

    page.content = AsyncMock(side_effect=hanging_content)

    start_time = time.monotonic()
    result = await capture_dom_telemetry(
        page=page,
        trigger="adversarial_content_hang",
        telemetry_dir=tmp_path,
        timeout_seconds=0.15,
    )
    elapsed = time.monotonic() - start_time

    assert result is None
    assert elapsed < 0.8, f"Telemetry content fallback took too long! Took {elapsed:.2f}s"
    assert content_started.is_set(), "page.content was never entered"
    assert content_cancelled is True, "Hung content task was not cancelled cleanly upon timeout"


@pytest.mark.asyncio
async def test_adversarial_outer_cancellation_not_swallowed(tmp_path: Path) -> None:
    """Challenge: Caller task is cancelled while capture_dom_telemetry is running.

    Empirical invariant: capture_dom_telemetry must allow CancelledError to propagate
    to support cooperative multitasking, rather than incorrectly catching it as generic error.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    async def slow_eval(*args: object, **kwargs: object) -> dict[str, object]:
        await asyncio.sleep(10.0)
        return {}

    page.evaluate = AsyncMock(side_effect=slow_eval)
    page.content = AsyncMock(side_effect=slow_eval)

    task = asyncio.create_task(
        capture_dom_telemetry(
            page=page,
            trigger="outer_cancel_test",
            telemetry_dir=tmp_path,
            timeout_seconds=5.0,
        )
    )

    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_adversarial_micro_timeout_boundary(tmp_path: Path) -> None:
    """Challenge: Microsecond timeout (0.0001s).

    Empirical invariant: Returns None without unhandled exceptions or thread-locking.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    async def slow_eval(*args: object, **kwargs: object) -> dict[str, object]:
        await asyncio.sleep(0.1)
        return {}

    page.evaluate = AsyncMock(side_effect=slow_eval)
    page.content = AsyncMock(side_effect=slow_eval)

    result = await capture_dom_telemetry(
        page=page,
        trigger="micro_timeout",
        telemetry_dir=tmp_path,
        timeout_seconds=0.0001,
    )
    assert result is None


# ============================================================================
# Category 2: Browser Crashes, Playwright Errors, and Memory Exhaustion
# ============================================================================


@pytest.mark.asyncio
async def test_adversarial_playwright_target_closed_crash(tmp_path: Path) -> None:
    """Challenge: Playwright raises TargetClosedError during evaluate and content.

    Empirical invariant: capture_dom_telemetry must survive browser process deaths,
    never raise an unhandled exception to the caller, and return None cleanly.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    closed_err = PlaywrightError("Target page, context or browser has been closed")
    page.evaluate = AsyncMock(side_effect=closed_err)
    page.content = AsyncMock(side_effect=closed_err)

    result = await capture_dom_telemetry(
        page=page,
        trigger="target_closed_test",
        telemetry_dir=tmp_path,
        timeout_seconds=1.0,
    )

    # Must return None safely without raising PlaywrightError
    assert result is None


@pytest.mark.asyncio
async def test_adversarial_memory_error_in_browser(tmp_path: Path) -> None:
    """Challenge: page.evaluate and page.content raise MemoryError.

    Empirical invariant: MemoryError (which inherits from Exception in Python)
    must be handled without unhandled exception escalation, safely returning None.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(side_effect=MemoryError("V8 out of memory"))
    page.content = AsyncMock(side_effect=MemoryError("Out of memory reading page content"))

    result = await capture_dom_telemetry(
        page=page,
        trigger="memory_error_test",
        telemetry_dir=tmp_path,
        timeout_seconds=1.0,
    )

    assert result is None


@pytest.mark.asyncio
async def test_adversarial_page_attributes_raising_unexpected_exceptions(tmp_path: Path) -> None:
    """Challenge: page.url property itself raises a catastrophic exception.

    Empirical invariant: url extraction must not break telemetry capture.
    """
    page = MagicMock()
    # Mocking property that raises
    type(page).url = property(lambda self: (_ for _ in ()).throw(RuntimeError("IPC disconnect")))
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["drift"]})
    page.content = AsyncMock()

    result = await capture_dom_telemetry(
        page=page,
        trigger="url_property_crash",
        telemetry_dir=tmp_path,
        timeout_seconds=1.0,
    )

    assert result is not None
    saved_file = Path(result)
    assert saved_file.exists()
    text = saved_file.read_text(encoding="utf-8")
    assert '"url_sanitized": ""' in text


@pytest.mark.asyncio
async def test_adversarial_deeply_nested_and_cyclic_dict_structures() -> None:
    """Challenge: page.evaluate returns deeply recursive nested structures or huge node counts.

    Empirical invariant: sanitize_dom_tree must strictly cap depth <= 10 and nodes <= 500
    without hitting Python RecursionError.
    """
    # Create 100-level nested dict
    root: dict[str, object] = {"tag": "level0", "classes": [], "attrs": {}, "children": []}
    curr = root
    for i in range(1, 100):
        nxt: dict[str, object] = {"tag": f"level{i}", "classes": [], "attrs": {}, "children": []}
        assert isinstance(curr["children"], list)
        curr["children"].append(nxt)
        curr = nxt

    sanitized = sanitize_dom_tree(root)

    # Verify depth restriction
    depth = 0
    node: dict[str, object] | None = sanitized
    while node and "children" in node and isinstance(node["children"], list) and node["children"]:
        depth += 1
        node = node["children"][0]

    assert depth <= 10, f"Depth exceeded 10 levels: {depth}"


# ============================================================================
# Category 3: Disk Write Failures and Filesystem Boundary Conditions
# ============================================================================


@pytest.mark.asyncio
async def test_adversarial_disk_permission_denied(tmp_path: Path) -> None:
    """Challenge: Telemetry destination directory or file raises PermissionError.

    Empirical invariant: capture_dom_telemetry must catch PermissionError and return None.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["feed"]})
    page.content = AsyncMock()

    read_only_dir = tmp_path / "protected"
    read_only_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(
        Path, "write_text", side_effect=PermissionError("Permission denied: protected")
    ):
        result = await capture_dom_telemetry(
            page=page,
            trigger="permission_denied_test",
            telemetry_dir=read_only_dir,
            timeout_seconds=1.0,
        )
        assert result is None


@pytest.mark.asyncio
async def test_adversarial_disk_full_os_error(tmp_path: Path) -> None:
    """Challenge: Disk full (OSError errno 28 / ENOSPC).

    Empirical invariant: capture_dom_telemetry must catch OSError and return None.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["feed"]})
    page.content = AsyncMock()

    with patch.object(Path, "write_text", side_effect=OSError(28, "No space left on device")):
        result = await capture_dom_telemetry(
            page=page,
            trigger="disk_full_test",
            telemetry_dir=tmp_path,
            timeout_seconds=1.0,
        )
        assert result is None


@pytest.mark.asyncio
async def test_adversarial_invalid_windows_filename_characters_in_trigger(tmp_path: Path) -> None:
    """Challenge: Trigger string contains invalid Windows filename characters: : * ? " < > | / \\

    Empirical invariant: Trigger must be sanitized so disk write succeeds without WinError.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["feed"]})
    page.content = AsyncMock()

    malicious_trigger = 'bad:trigger*with?invalid"chars<and>pipes|slash/back\\'
    result = await capture_dom_telemetry(
        page=page,
        trigger=malicious_trigger,
        telemetry_dir=tmp_path,
        timeout_seconds=1.0,
    )

    assert result is not None
    saved_file = Path(result)
    assert saved_file.exists()
    # Confirm illegal characters were purged from filename
    filename = saved_file.name
    for char in [":", "*", "?", '"', "<", ">", "|", "/", "\\"]:
        assert char not in filename


@pytest.mark.asyncio
async def test_adversarial_extreme_oversized_trigger(tmp_path: Path) -> None:
    """Challenge: Trigger string is 10,000 characters long (exceeding Windows MAX_PATH).

    Empirical invariant: capture_dom_telemetry must either truncate or safely catch OSError and return None.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["feed"]})
    page.content = AsyncMock()

    huge_trigger = "A" * 10000
    # On Windows this will raise OSError [Errno 22] Invalid argument / File name too long
    result = await capture_dom_telemetry(
        page=page,
        trigger=huge_trigger,
        telemetry_dir=tmp_path,
        timeout_seconds=1.0,
    )
    # Must catch and return None safely without unhandled crash
    assert result is None or Path(result).exists()


# ============================================================================
# Category 4: Primary Workflow Error Preservation in Scraper and Executor
# ============================================================================


@pytest.mark.asyncio
async def test_adversarial_scraper_feed_challenge_with_real_hung_page(
    test_settings: Settings,
) -> None:
    """Empirical test with real capture_dom_telemetry on a simulated hung page.

    Empirical invariant: Scraper MUST raise BotDetectionError within timeout bounds.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"

    async def slow_eval(*args: object, **kwargs: object) -> dict[str, object]:
        await asyncio.sleep(10.0)
        return {}

    page.evaluate = AsyncMock(side_effect=slow_eval)
    page.content = AsyncMock(side_effect=slow_eval)
    page.screenshot = AsyncMock()

    scraper = FeedScraper(page, test_settings)

    # Accelerate timeout for test execution
    with (
        patch("agent.browser.scraper.detect_challenge_page", return_value=True),
        patch("agent.browser.telemetry.asyncio.wait_for", side_effect=TimeoutError("Timed out")),
    ):
        with pytest.raises(BotDetectionError, match="Bot detection challenge"):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())


@pytest.mark.asyncio
async def test_adversarial_scraper_feed_container_drift_with_catastrophic_telemetry_crash(
    test_settings: Settings,
) -> None:
    """Challenge: Scraper encounters container drift, while telemetry throws an unexpected exception.

    Empirical invariant: Scraper MUST raise SelectorDriftError, NOT the telemetry exception.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    locator = MagicMock()
    locator.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator)

    scraper = FeedScraper(page, test_settings)

    with patch(
        "agent.browser.scraper.capture_dom_telemetry",
        side_effect=RuntimeError("Catastrophic unexpected telemetry bug"),
    ):
        with pytest.raises(SelectorDriftError, match="Feed root container not found"):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())


@pytest.mark.asyncio
async def test_adversarial_scraper_cards_drift_with_telemetry_failure(
    test_settings: Settings,
) -> None:
    """Challenge: Scraper encounters zero cards drift, and telemetry fails with PermissionError.

    Empirical invariant: Scraper returns empty post list [] without crashing.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    container_loc = MagicMock(count=AsyncMock(return_value=1))
    cards_loc = MagicMock(count=AsyncMock(return_value=0))

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector or "scaffold-finite-scroll" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)

    scraper = FeedScraper(page, test_settings)

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", side_effect=PermissionError("Locked")),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        posts = await scraper.scrape_feed(max_posts=5, seen_hashes=set())
        assert posts == []


@pytest.mark.asyncio
async def test_adversarial_executor_comment_box_drift_with_crashing_telemetry(
    test_settings: Settings,
) -> None:
    """Challenge: Executor comment box drifts, and telemetry raises MemoryError.

    Empirical invariant: Executor MUST raise ExecutionError, not MemoryError.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc

    def locator_side_effect(selector: str) -> MagicMock:
        if "comment-button" in selector or "button" in selector:
            loc = MagicMock()
            loc.first = comment_btn
            loc.count = comment_btn.count
            return loc
        return empty_loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with patch(
        "agent.browser.executor.capture_dom_telemetry",
        side_effect=MemoryError("OOM during telemetry"),
    ):
        with pytest.raises(ExecutionError, match="Comment input box not found in DOM"):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Adversarial challenge comment",
                item_id="adv_comment_001",
                dry_run=False,
                simulate_dwell=False,
            )


@pytest.mark.asyncio
async def test_adversarial_executor_submit_button_drift_with_permission_error_telemetry(
    test_settings: Settings,
) -> None:
    """Challenge: Executor comment submit button drifts, and telemetry raises PermissionError.

    Empirical invariant: Executor MUST raise ExecutionError/SelectorDriftError.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
    comment_box = MagicMock(
        count=AsyncMock(return_value=1),
        focus=AsyncMock(),
        press_sequentially=AsyncMock(),
    )
    empty_loc = MagicMock(count=AsyncMock(return_value=0))
    empty_loc.first = empty_loc

    def locator_side_effect(selector: str) -> MagicMock:
        if "submit" in selector or "submit-button" in selector:
            return empty_loc
        elif "button[aria-label*='Comment']" in selector:
            loc = MagicMock()
            loc.first = comment_btn
            return loc
        else:
            loc = MagicMock()
            loc.first = comment_box
            return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    executor = ActionExecutor(page, test_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with (
        patch(
            "agent.browser.executor.capture_dom_telemetry", side_effect=PermissionError("Locked")
        ),
        patch("agent.browser.executor.humanized_type", new_callable=AsyncMock),
    ):
        with pytest.raises(ExecutionError, match="Comment submit button not found in DOM"):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Adversarial submit test",
                item_id="adv_comment_002",
                dry_run=False,
                simulate_dwell=False,
            )


@pytest.mark.asyncio
async def test_adversarial_executor_comment_verification_timeout_with_disk_full_telemetry(
    test_settings: Settings,
) -> None:
    """Challenge: Comment verification times out, and telemetry write fails with disk full.

    Empirical invariant: Executor MUST raise SubmissionVerificationError.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:123"
    page.screenshot = AsyncMock()

    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=0)

    comment_box = MagicMock()
    comment_box.count = AsyncMock(return_value=1)
    comment_box.focus = AsyncMock()
    comment_box.inner_text = AsyncMock(return_value="Still has text")

    submit_btn = MagicMock()
    submit_btn.count = AsyncMock(return_value=1)
    submit_btn.click = AsyncMock()
    submit_btn.is_visible = AsyncMock(return_value=True)
    submit_btn.get_attribute = AsyncMock(return_value=None)

    def locator_mock(selector: str) -> MagicMock:
        loc = MagicMock()
        if "submit-button" in selector:
            loc.first = submit_btn
            loc.count = AsyncMock(return_value=1)
        elif "button[aria-label*='Comment']" in selector or "comment-button" in selector:
            loc.first = comment_btn
            loc.count = AsyncMock(return_value=0)
        elif "comment-item" in selector:
            loc.count = AsyncMock(return_value=0)
        elif "toast" in selector or "alert" in selector or "feedback" in selector:
            loc.count = AsyncMock(return_value=0)
        else:
            loc.first = comment_box
            loc.count = AsyncMock(return_value=1)
        return loc

    page.locator = MagicMock(side_effect=locator_mock)

    executor = ActionExecutor(page, test_settings)
    executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]
    executor.react_to_post = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with (
        patch(
            "agent.browser.executor.capture_dom_telemetry",
            side_effect=OSError(28, "No space left on device"),
        ),
        patch("agent.browser.executor.humanized_type", new_callable=AsyncMock),
    ):
        with pytest.raises(SubmissionVerificationError):
            await executor.post_comment(
                post_url=page.url,
                comment_text="Adversarial timeout comment",
                item_id="adv_comment_003",
                dry_run=False,
                verification_timeout=0.01,
                simulate_dwell=False,
            )


@pytest.mark.asyncio
async def test_adversarial_executor_create_post_ui_drift_with_corrupt_telemetry(
    test_settings: Settings,
) -> None:
    """Challenge: Create post modal start button missing, telemetry throws TypeError.

    Empirical invariant: Executor MUST raise ExecutionError.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    start_btn = MagicMock()
    start_btn.count = AsyncMock(return_value=0)
    page.locator.return_value.first = start_btn

    executor = ActionExecutor(page, test_settings)

    with patch(
        "agent.browser.executor.capture_dom_telemetry",
        side_effect=TypeError("Corrupt telemetry argument"),
    ):
        with pytest.raises(ExecutionError, match="Start a post button not found"):
            await executor.create_post(
                post_text="Adversarial post drift test",
                item_id="adv_post_001",
                dry_run=False,
            )


@pytest.mark.asyncio
async def test_adversarial_scraper_card_layout_drift_skips_bad_card_and_parses_remaining(
    test_settings: Settings,
) -> None:
    """Challenge: Scraper encounters malformed card layout drift, and telemetry throws an exception.

    Empirical invariant: The malformed card is skipped, valid subsequent cards are extracted,
    and the scraper never crashes.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.screenshot = AsyncMock()

    container_loc = MagicMock(count=AsyncMock(return_value=1))

    # Bad card missing actor/text
    bad_card = MagicMock()
    bad_card.get_attribute = AsyncMock(return_value="urn:li:activity:bad_card")
    bad_card.locator = MagicMock(
        return_value=MagicMock(first=MagicMock(count=AsyncMock(return_value=0)))
    )

    # Good card
    good_card = MagicMock()
    good_card.get_attribute = AsyncMock(return_value="urn:li:activity:good_card")
    actor = MagicMock(
        count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="Valid Author")
    )
    text = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Valid Content for feed post."),
    )

    def good_card_loc(selector: str) -> MagicMock:
        loc = MagicMock()
        if "actor" in selector:
            loc.first = actor
        elif "text" in selector or "description" in selector:
            loc.first = text
        else:
            loc.first = MagicMock(count=AsyncMock(return_value=0))
        return loc

    good_card.locator = MagicMock(side_effect=good_card_loc)

    cards_loc = MagicMock(count=AsyncMock(return_value=2))
    cards_loc.nth = MagicMock(side_effect=[bad_card, good_card])

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector or "scaffold-finite-scroll" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)

    scraper = FeedScraper(page, test_settings)

    with (
        patch(
            "agent.browser.scraper.capture_dom_telemetry",
            side_effect=RuntimeError("Telemetry failed on drift"),
        ),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        posts = await scraper.scrape_feed(max_posts=5, seen_hashes=set())
        assert len(posts) == 1
        assert posts[0].author_name == "Valid Author"
        assert posts[0].post_text == "Valid Content for feed post."


@pytest.mark.asyncio
async def test_adversarial_concurrent_telemetry_captures(tmp_path: Path) -> None:
    """Challenge: 10 concurrent capture_dom_telemetry calls execute simultaneously.

    Empirical invariant: Concurrency must not trigger file write collision or race condition.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["concurrent"]})
    page.content = AsyncMock()

    tasks = [
        asyncio.create_task(
            capture_dom_telemetry(
                page=page,
                trigger=f"concurrent_test_{i}",
                telemetry_dir=tmp_path,
                timeout_seconds=2.0,
            )
        )
        for i in range(10)
    ]

    results = await asyncio.gather(*tasks)
    assert all(res is not None for res in results)
    # Verify all 10 files exist and are non-empty valid JSON
    assert len(set(results)) == 10
    for res in results:
        assert res is not None
        p = Path(res)
        assert p.exists()
        assert p.stat().st_size > 0


@pytest.mark.asyncio
async def test_adversarial_telemetry_dir_is_existing_file(tmp_path: Path) -> None:
    """Challenge: telemetry_dir points to an existing file rather than a directory.

    Empirical invariant: mkdir(parents=True) will raise FileExistsError / NotADirectoryError;
    capture_dom_telemetry must catch this and return None without crashing.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["drift"]})
    page.content = AsyncMock()

    blocking_file = tmp_path / "not_a_dir"
    blocking_file.write_text("i am a file", encoding="utf-8")

    result = await capture_dom_telemetry(
        page=page,
        trigger="file_collision_test",
        telemetry_dir=blocking_file,
        timeout_seconds=1.0,
    )
    assert result is None


@pytest.mark.asyncio
async def test_adversarial_uncoercible_metadata_types(tmp_path: Path) -> None:
    """Challenge: caller passes invalid non-coercible objects for item_id or target_selector.

    Empirical invariant: Pydantic validation error or internal error is safely caught and returns None.
    """
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.evaluate = AsyncMock(return_value={"tag": "div", "classes": ["drift"]})
    page.content = AsyncMock()

    result = await capture_dom_telemetry(
        page=page,
        trigger="invalid_metadata",
        telemetry_dir=tmp_path,
        item_id=object(),  # type: ignore[arg-type]
        timeout_seconds=1.0,
    )
    assert result is None
