"""Adversarial challenge and stress-testing suite for Milestone 1 state pruning."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext
from agent.models.schemas import HistoryEntry, PendingAction
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Initialize a clean local git repository fixture."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    state_dir = repo / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
    return repo


@pytest.fixture
def state_store(temp_git_repo: Path) -> GitStateStore:
    return GitStateStore(temp_git_repo)


def test_adv_prune_boundary_conditions(state_store: GitStateStore) -> None:
    """Stress-test: Exact microsecond TTL boundaries, future timestamps, and ancient timestamps."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    ttl_hours = 12

    # 1. Exact boundary: exactly 12.0 hours ago -> NOT expired (elapsed == 12h * 3600)
    item_exact = PendingAction(
        item_id="b_exact",
        action_type="approve_comment",
        created_at=now - timedelta(hours=12),
        post_urn="urn:li:activity:exact",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:exact/",
        author_name="Exact Author",
        post_excerpt="Exact",
        draft_text="Draft Exact",
        confidence=0.9,
        reasoning="Exact TTL boundary",
        telegram_chat_id=123,
        telegram_message_id=10,
    )
    # 2. 1 microsecond beyond TTL: 12h + 1us ago -> EXPIRED
    item_just_over = PendingAction(
        item_id="b_over",
        action_type="approve_comment",
        created_at=now - timedelta(hours=12, microseconds=1),
        post_urn="urn:li:activity:over",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:over/",
        author_name="Over Author",
        post_excerpt="Over",
        draft_text="Draft Over",
        confidence=0.9,
        reasoning="Just over TTL",
        telegram_chat_id=123,
        telegram_message_id=11,
    )
    # 3. 1 microsecond before TTL: 12h - 1us ago -> NOT expired
    item_just_under = PendingAction(
        item_id="b_under",
        action_type="approve_comment",
        created_at=now - timedelta(hours=12) + timedelta(microseconds=1),
        post_urn="urn:li:activity:under",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:under/",
        author_name="Under Author",
        post_excerpt="Under",
        draft_text="Draft Under",
        confidence=0.9,
        reasoning="Just under TTL",
        telegram_chat_id=123,
        telegram_message_id=12,
    )
    # 4. Future timestamp (clock skew): created 2 hours in the future -> NOT expired
    item_future = PendingAction(
        item_id="b_future",
        action_type="approve_comment",
        created_at=now + timedelta(hours=2),
        post_urn="urn:li:activity:future",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:future/",
        author_name="Future Author",
        post_excerpt="Future",
        draft_text="Draft Future",
        confidence=0.9,
        reasoning="Future clock drift",
        telegram_chat_id=123,
        telegram_message_id=13,
    )
    # 5. Ancient item: created 365 days ago -> EXPIRED
    item_ancient = PendingAction(
        item_id="b_ancient",
        action_type="approve_post",
        created_at=now - timedelta(days=365),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft Ancient",
        confidence=0.8,
        reasoning="Ancient item",
        telegram_chat_id=123,
        telegram_message_id=14,
    )

    state_store.write_pending(item_exact)
    state_store.write_pending(item_just_over)
    state_store.write_pending(item_just_under)
    state_store.write_pending(item_future)
    state_store.write_pending(item_ancient)

    assert len(state_store.list_pending()) == 5

    pruned = state_store.prune_expired_pending(ttl_hours=ttl_hours, now=now)

    # Exactly item_just_over and item_ancient should be pruned
    pruned_ids = {p.item_id for p in pruned}
    assert pruned_ids == {"b_over", "b_ancient"}

    # Preserved items
    remaining = state_store.list_pending()
    remaining_ids = {r.item_id for r in remaining}
    assert remaining_ids == {"b_exact", "b_under", "b_future"}


def test_adv_prune_aware_timezones_utc_est_jst(state_store: GitStateStore) -> None:
    """Stress-test: Aware timezone items (UTC, EST, JST) against a non-UTC now reference instant."""
    tz_est = timezone(timedelta(hours=-5))
    tz_jst = timezone(timedelta(hours=9))
    tz_custom = timezone(timedelta(hours=3, minutes=30))

    # Reference instant: 2026-09-02T12:00:00Z
    now_utc = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    now_custom = now_utc.astimezone(tz_custom)  # Same instant in UTC+3:30

    # 1. UTC item expired (20h old)
    item_utc_exp = PendingAction(
        item_id="tz_utc_exp",
        action_type="approve_comment",
        created_at=datetime(2026, 9, 1, 16, 0, 0, tzinfo=UTC),  # 20h old
        post_urn="urn:li:activity:tz1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:tz1/",
        author_name="UTC",
        post_excerpt="UTC",
        draft_text="UTC",
        confidence=0.9,
        reasoning="UTC exp",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    # 2. EST item fresh (2h old): 12:00 UTC is 07:00 EST. Created at 05:00 EST -> 2h old
    item_est_fresh = PendingAction(
        item_id="tz_est_fresh",
        action_type="approve_comment",
        created_at=datetime(2026, 9, 2, 5, 0, 0, tzinfo=tz_est),
        post_urn="urn:li:activity:tz2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:tz2/",
        author_name="EST",
        post_excerpt="EST",
        draft_text="EST",
        confidence=0.9,
        reasoning="EST fresh",
        telegram_chat_id=123,
        telegram_message_id=2,
    )
    # 3. JST item expired (24h old): 12:00 UTC is 21:00 JST. Created at 2026-09-01 21:00 JST -> 24h old
    item_jst_exp = PendingAction(
        item_id="tz_jst_exp",
        action_type="approve_comment",
        created_at=datetime(2026, 9, 1, 21, 0, 0, tzinfo=tz_jst),
        post_urn="urn:li:activity:tz3",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:tz3/",
        author_name="JST",
        post_excerpt="JST",
        draft_text="JST",
        confidence=0.9,
        reasoning="JST exp",
        telegram_chat_id=123,
        telegram_message_id=3,
    )

    state_store.write_pending(item_utc_exp)
    state_store.write_pending(item_est_fresh)
    state_store.write_pending(item_jst_exp)

    # Prune using non-UTC now
    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now_custom)

    pruned_ids = {p.item_id for p in pruned}
    assert pruned_ids == {"tz_utc_exp", "tz_jst_exp"}

    remaining = state_store.list_pending()
    remaining_ids = {r.item_id for r in remaining}
    assert remaining_ids == {"tz_est_fresh"}


def test_adv_prune_mixed_naive_and_aware_timezones_vulnerability(
    state_store: GitStateStore,
) -> None:
    """Stress-test / Finding: Coexistence of naive and timezone-aware datetimes in state/pending/.

    Demonstrates failure mode where list_pending() raises TypeError during sorting when naive
    and aware timestamps coexist.
    """
    # Item with aware timestamp
    item_aware = PendingAction(
        item_id="tz_aware_item",
        action_type="approve_comment",
        created_at=datetime(2026, 9, 1, 16, 0, 0, tzinfo=UTC),
        post_urn="urn:li:activity:aware1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:aware1/",
        author_name="Aware",
        post_excerpt="Aware",
        draft_text="Aware",
        confidence=0.9,
        reasoning="Aware",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    # Item with naive timestamp
    item_naive = PendingAction(
        item_id="tz_naive_item",
        action_type="approve_comment",
        created_at=datetime(2026, 9, 2, 11, 0, 0),  # Naive datetime
        post_urn="urn:li:activity:naive1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:naive1/",
        author_name="Naive",
        post_excerpt="Naive",
        draft_text="Naive",
        confidence=0.9,
        reasoning="Naive",
        telegram_chat_id=123,
        telegram_message_id=2,
    )

    state_store.write_pending(item_aware)
    state_store.write_pending(item_naive)

    # When sorting mixed aware and naive timestamps without key normalization,
    # list_pending() raises TypeError in Python: "TypeError: can't compare offset-naive and offset-aware datetimes"
    with pytest.raises(TypeError, match="can't compare offset-naive and offset-aware datetimes"):
        state_store.list_pending()


def test_adv_prune_corrupted_and_unparseable_pending_files(state_store: GitStateStore) -> None:
    """Stress-test: Corrupted JSON, schema violations, empty files, and hidden files in state/pending/."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    # 1. Valid expired item
    valid_exp = PendingAction(
        item_id="valid_exp",
        action_type="approve_comment",
        created_at=now - timedelta(hours=20),
        post_urn="urn:li:activity:valid1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:valid1/",
        author_name="Valid Exp",
        post_excerpt="Valid",
        draft_text="Draft Valid",
        confidence=0.9,
        reasoning="Valid exp",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    # 2. Valid fresh item
    valid_fresh = PendingAction(
        item_id="valid_fresh",
        action_type="approve_comment",
        created_at=now - timedelta(hours=1),
        post_urn="urn:li:activity:valid2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:valid2/",
        author_name="Valid Fresh",
        post_excerpt="Valid",
        draft_text="Draft Valid Fresh",
        confidence=0.9,
        reasoning="Valid fresh",
        telegram_chat_id=123,
        telegram_message_id=2,
    )
    state_store.write_pending(valid_exp)
    state_store.write_pending(valid_fresh)

    # Write corrupt artifacts directly to state/pending/
    pending_dir = state_store.pending_dir
    (pending_dir / "corrupt_syntax.json").write_text("{ unclosed json: invalid", encoding="utf-8")
    (pending_dir / "empty_file.json").write_text("", encoding="utf-8")
    (pending_dir / "invalid_schema.json").write_text(
        json.dumps({"unknown_field": 123}), encoding="utf-8"
    )
    (pending_dir / ".hidden_file.json").write_text(
        json.dumps({"item_id": "hidden"}), encoding="utf-8"
    )
    (pending_dir / "random.tmp").write_text("temporary file", encoding="utf-8")

    # list_pending should skip corrupted files without throwing
    all_pending = state_store.list_pending()
    assert len(all_pending) == 2
    assert {p.item_id for p in all_pending} == {"valid_exp", "valid_fresh"}

    # prune_expired_pending should succeed smoothly
    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(pruned) == 1
    assert pruned[0].item_id == "valid_exp"

    # Disk state verification
    assert state_store.read_pending("valid_exp") is None
    assert state_store.read_pending("valid_fresh") is not None

    # History audit verification
    history = state_store.read_history()
    assert len(history) == 1
    assert history[0].item_id == "valid_exp"


def test_adv_prune_scale_1000_items(state_store: GitStateStore) -> None:
    """Stress-test: Scale test with 1,000 pending action files (500 expired, 500 fresh)."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    total_count = 1000
    expected_expired = 500
    expected_fresh = 500

    # Batch write 1000 items
    for i in range(total_count):
        age_hours_val: float
        if i < expected_expired:
            # Expired: 13 to 100 hours old
            age_hours_val = float(13 + (i % 80))
            item_id = f"exp_{i:04d}"
        else:
            # Fresh: 0.1 to 11.5 hours old
            age_hours_val = float(0.5 + ((i - expected_expired) % 11))
            item_id = f"fresh_{i:04d}"

        item = PendingAction(
            item_id=item_id,
            action_type="approve_comment" if i % 2 == 0 else "approve_post",
            created_at=now - timedelta(hours=age_hours_val),
            post_urn=f"urn:li:activity:{i}",
            post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{i}/",
            author_name=f"Author {i}",
            post_excerpt=f"Excerpt {i}",
            draft_text=f"Draft {i}",
            confidence=0.85,
            reasoning=f"Reason {i}",
            telegram_chat_id=123,
            telegram_message_id=1000 + i,
        )
        state_store.write_pending(item)

    assert len(state_store.list_pending()) == total_count

    # Measure execution time for pruning 1,000 items
    t_start = time.perf_counter()
    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now)
    duration = time.perf_counter() - t_start

    assert len(pruned) == expected_expired
    assert duration < 5.0, f"Pruning 1,000 items took too long: {duration:.2f}s"

    # Verify disk state
    remaining = state_store.list_pending()
    assert len(remaining) == expected_fresh
    assert all(r.item_id.startswith("fresh_") for r in remaining)

    # Verify history integrity
    history = state_store.read_history()
    assert len(history) == expected_expired
    assert all(h.final_status == "expired" for h in history)
    assert all(h.item_id.startswith("exp_") for h in history)


def test_adv_prune_idempotence(state_store: GitStateStore) -> None:
    """Stress-test: Repeated consecutive executions are strictly idempotent."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    for i in range(10):
        item_exp = PendingAction(
            item_id=f"idem_exp_{i}",
            action_type="approve_comment",
            created_at=now - timedelta(hours=20 + i),
            post_urn=f"urn:li:activity:idem_exp_{i}",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity/1/",
            author_name="User",
            post_excerpt="Post",
            draft_text="Draft",
            confidence=0.9,
            reasoning="Reason",
            telegram_chat_id=123,
            telegram_message_id=i,
        )
        item_fresh = PendingAction(
            item_id=f"idem_fresh_{i}",
            action_type="approve_comment",
            created_at=now - timedelta(hours=1 + (i % 5)),
            post_urn=f"urn:li:activity:idem_fresh_{i}",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity/2/",
            author_name="User",
            post_excerpt="Post",
            draft_text="Draft",
            confidence=0.9,
            reasoning="Reason",
            telegram_chat_id=123,
            telegram_message_id=100 + i,
        )
        state_store.write_pending(item_exp)
        state_store.write_pending(item_fresh)

    # Run 1: Prunes 10 items
    run1 = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(run1) == 10
    assert len(state_store.read_history()) == 10
    assert len(state_store.list_pending()) == 10

    # Run 2: Immediately run again -> Prunes 0 items, history remains 10
    run2 = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(run2) == 0
    assert len(state_store.read_history()) == 10
    assert len(state_store.list_pending()) == 10

    # Run 3: Third run -> Still 0
    run3 = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(run3) == 0
    assert len(state_store.read_history()) == 10


def test_adv_prune_history_preserves_existing_jsonl_records(state_store: GitStateStore) -> None:
    """Stress-test: Appending expiration records preserves existing history entries without corruption."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)

    # Pre-populate history with existing non-expired executions
    pre_entries = [
        HistoryEntry(
            item_id="prior_001",
            action_type="approve_comment",
            final_status="executed_success",
            decided_at=now - timedelta(hours=5),
            executed_at=now - timedelta(hours=5),
            screenshot_path="debug/prior1.png",
            error=None,
        ),
        HistoryEntry(
            item_id="prior_002",
            action_type="approve_post",
            final_status="rejected",
            decided_at=now - timedelta(hours=4),
            executed_at=None,
            screenshot_path=None,
            error=None,
        ),
    ]
    for e in pre_entries:
        state_store.append_history(e)

    assert len(state_store.read_history()) == 2

    # Now prune 2 expired items: item1 is 24h old, item2 is 36h old
    # Because list_pending() sorts by created_at ascending, item2 (36h old) will be ordered before item1 (24h old)
    item1 = PendingAction(
        item_id="exp_hist_1",
        action_type="approve_comment",
        created_at=now - timedelta(hours=24),
        post_urn="urn:li:activity:h1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:h1/",
        author_name="Author",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.9,
        reasoning="Reason",
        telegram_chat_id=123,
        telegram_message_id=1,
    )
    item2 = PendingAction(
        item_id="exp_hist_2",
        action_type="approve_post",
        created_at=now - timedelta(hours=36),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Draft Post",
        confidence=0.8,
        reasoning="Reason",
        telegram_chat_id=123,
        telegram_message_id=2,
    )
    state_store.write_pending(item1)
    state_store.write_pending(item2)

    pruned = state_store.prune_expired_pending(ttl_hours=12, now=now)
    assert len(pruned) == 2

    # Verify all 4 history entries are present in chronological order
    all_hist = state_store.read_history()
    assert len(all_hist) == 4
    assert [h.item_id for h in all_hist] == ["prior_001", "prior_002", "exp_hist_2", "exp_hist_1"]
    assert all_hist[0].final_status == "executed_success"
    assert all_hist[1].final_status == "rejected"
    assert all_hist[2].final_status == "expired"
    assert all_hist[3].final_status == "expired"


@pytest.mark.asyncio
async def test_adv_scout_graph_prune_telegram_chaos_matrix(temp_git_repo: Path) -> None:
    """Stress-test: ScoutGraph with a chaotic matrix of Telegram outcomes, exceptions, and missing chat IDs."""
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=99999,  # Default fallback chat ID
        user_focus_areas=["AI"],
        max_suggestions_per_run=3,
        state_dir=temp_git_repo / "state",
        dry_run=True,
    )
    state_store = GitStateStore(temp_git_repo)
    enforcer = DailyCapEnforcer(settings)

    now = datetime.now(UTC)

    # Create 20 expired pending actions with different telegram configurations:
    # 0..4: msg_id = 0 (no telegram message sent originally)
    # 5..9: msg_id = 500+i, chat_id = 11111 (success)
    # 10..14: msg_id = 600+i, chat_id = 22222 (fails with TimeoutError)
    # 15..19: msg_id = 700+i, chat_id = None (uses default fallback chat_id 99999, fails with HTTP 400)
    for i in range(20):
        if i < 5:
            msg_id = 0
            chat_id = 11111
        elif i < 10:
            msg_id = 500 + i
            chat_id = 11111
        elif i < 15:
            msg_id = 600 + i
            chat_id = 22222
        else:
            msg_id = 700 + i
            chat_id = None  # None -> should fallback to 99999

        item = PendingAction(
            item_id=f"chaos_exp_{i:02d}",
            action_type="approve_comment",
            created_at=now - timedelta(hours=25),
            post_urn=f"urn:li:activity:chaos_{i}",
            post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:chaos_{i}/",
            author_name=f"Chaos {i}",
            post_excerpt=f"Excerpt {i}",
            draft_text=f"Draft {i}",
            confidence=0.9,
            reasoning=f"Reason {i}",
            telegram_chat_id=chat_id,
            telegram_message_id=msg_id,
        )
        state_store.write_pending(item)

    assert len(state_store.list_pending()) == 20

    async def edit_side_effect(chat_id: int, message_id: int, outcome_text: str) -> None:
        if 610 <= message_id < 615:
            raise TimeoutError("Telegram gateway timeout")
        if 715 <= message_id < 720:
            raise Exception("Telegram 400 Bad Request: message to edit not found")
        # Otherwise succeeds

    mock_telegram: Any = MagicMock()
    mock_telegram.edit_to_outcome = AsyncMock(side_effect=edit_side_effect)

    mock_scraper: Any = MagicMock()
    mock_scraper.scrape_feed = AsyncMock(return_value=[])

    context = GraphContext(
        settings=settings,
        state_store=state_store,
        telegram=mock_telegram,
        scraper=mock_scraper,
        enforcer=enforcer,
    )

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": context}})

    # Assert graph executed to completion
    pruned = result.get("pruned_items", [])
    assert len(pruned) == 20

    # Assert all 20 expired files were removed from disk despite Telegram failures
    assert len(state_store.list_pending()) == 0

    # Assert all 20 history entries were logged
    history = state_store.read_history()
    assert len(history) == 20
    assert all(h.final_status == "expired" for h in history)

    # Check Telegram call invocations:
    # 5 items with msg_id=0 should NOT be called.
    # 15 items with msg_id > 0 SHOULD be called.
    assert mock_telegram.edit_to_outcome.call_count == 15

    # Check fallback chat ID 99999 was passed for items 15..19
    calls = mock_telegram.edit_to_outcome.call_args_list
    fallback_calls = [c for c in calls if c.kwargs.get("chat_id") == 99999]
    assert len(fallback_calls) == 5
