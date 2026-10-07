"""Unit tests for domain and persistence schemas in agent.models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agent.models import (
    ACTION_CODE_APPROVE_COMMENT,
    ACTION_CODE_APPROVE_POST,
    ACTION_CODE_APPROVE_REACTION,
    ACTION_CODE_EDIT,
    ACTION_CODE_REJECT_COMMENT,
    ACTION_CODE_REJECT_POST,
    ACTION_CODE_REJECT_REACTION,
    CallbackDataPayload,
    CommentDraft,
    DailyCounters,
    EngagementStyle,
    ExecutionResult,
    HistoryEntry,
    HistoryStatus,
    MediaAttachment,
    PendingAction,
    PostIdea,
    PostIdeationContext,
    PostRecord,
    ReactionType,
    RepositoryDispatchPayload,
    RiskFlag,
    ScheduledPost,
    TriageResult,
)


class TestEngagementStyle:
    """Test suite for EngagementStyle enum."""

    def test_enum_values(self) -> None:
        assert EngagementStyle.TECHNICAL_DEEP_DIVE.value == "technical_deep_dive"
        assert EngagementStyle.INQUISITIVE_QUESTION.value == "inquisitive_question"
        assert EngagementStyle.CONTRARIAN_PERSPECTIVE.value == "contrarian_perspective"
        assert EngagementStyle.SUPPORTIVE_SYNTHESIS.value == "supportive_synthesis"

    def test_all_expected_styles_present(self) -> None:
        expected = {
            "technical_deep_dive",
            "inquisitive_question",
            "contrarian_perspective",
            "supportive_synthesis",
        }
        actual = {style.value for style in EngagementStyle}
        assert actual == expected


class TestReactionType:
    """Test suite for ReactionType enum."""

    def test_enum_values(self) -> None:
        assert ReactionType.LIKE.value == "like"
        assert ReactionType.INSIGHTFUL.value == "insightful"
        assert ReactionType.CELEBRATE.value == "celebrate"
        assert ReactionType.SUPPORT.value == "support"
        assert ReactionType.FUNNY.value == "funny"
        assert ReactionType.LOVE.value == "love"

    def test_all_expected_reactions_present(self) -> None:
        expected = {"like", "insightful", "celebrate", "support", "funny", "love"}
        actual = {r.value for r in ReactionType}
        assert actual == expected


class TestTriageResult:
    """Test suite for TriageResult schema."""

    def test_valid_triage_result(self) -> None:
        triage = TriageResult(
            recommendation="comment",
            confidence=0.95,
            reasoning="High signal technical post about Python internals.",
            risk_flags=[RiskFlag.LOW_SIGNAL],
        )
        assert triage.recommendation == "comment"
        assert triage.confidence == 0.95
        assert triage.reasoning.startswith("High signal")
        assert triage.risk_flags == [RiskFlag.LOW_SIGNAL]
        assert triage.engagement_style is None

    def test_triage_result_with_engagement_style(self) -> None:
        triage = TriageResult(
            recommendation="comment",
            confidence=0.9,
            reasoning="Valid technical deep dive post",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
        assert triage.engagement_style == EngagementStyle.TECHNICAL_DEEP_DIVE

        triage_str = TriageResult(
            recommendation="comment",
            confidence=0.85,
            reasoning="Inquisitive post",
            engagement_style="inquisitive_question",  # type: ignore[arg-type]
        )
        assert triage_str.engagement_style == EngagementStyle.INQUISITIVE_QUESTION

    def test_valid_triage_result_with_reaction(self) -> None:
        triage = TriageResult(
            recommendation="react",
            confidence=0.88,
            reasoning="Important milestone release in AI infrastructure",
            reaction_type=ReactionType.CELEBRATE,
        )
        assert triage.recommendation == "react"
        assert triage.reaction_type == "celebrate"
        assert triage.engagement_style is None

    def test_triage_result_invalid_engagement_style(self) -> None:
        with pytest.raises(ValidationError):
            TriageResult(
                recommendation="comment",
                confidence=0.8,
                reasoning="Reason",
                engagement_style="invalid_style",  # type: ignore[arg-type]
            )

    def test_invalid_recommendation(self) -> None:
        with pytest.raises(ValidationError):
            TriageResult(
                recommendation="invalid_action",  # type: ignore[arg-type]
                confidence=0.8,
                reasoning="Reason",
            )

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TriageResult(recommendation="comment", confidence=1.5, reasoning="Over 1.0")

        with pytest.raises(ValidationError):
            TriageResult(recommendation="comment", confidence=-0.1, reasoning="Under 0.0")

    def test_reasoning_max_length(self) -> None:
        long_reasoning = "A" * 241
        with pytest.raises(ValidationError):
            TriageResult(
                recommendation="ignore",
                confidence=0.5,
                reasoning=long_reasoning,
            )

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            TriageResult.model_validate(
                {
                    "recommendation": "comment",
                    "confidence": 0.9,
                    "reasoning": "Valid reasoning",
                    "extra_unexpected_field": "disallowed",
                }
            )


class TestCommentDraft:
    """Test suite for CommentDraft schema."""

    def test_valid_comment_draft(self) -> None:
        draft = CommentDraft(
            draft_comment="Great perspective on distributed lock safety. We found fencing tokens essential.",
            topic_tags=["distributed-systems", "python"],
        )
        assert "fencing tokens" in draft.draft_comment
        assert len(draft.topic_tags) == 2
        assert draft.engagement_style is None

    def test_comment_draft_with_engagement_style(self) -> None:
        draft = CommentDraft(
            draft_comment="Respectfully challenging the thesis with alternative consensus model.",
            topic_tags=["distributed-systems"],
            engagement_style=EngagementStyle.CONTRARIAN_PERSPECTIVE,
        )
        assert draft.engagement_style == EngagementStyle.CONTRARIAN_PERSPECTIVE

        draft_str = CommentDraft(
            draft_comment="Connecting this pattern to real-world cloud scaling.",
            topic_tags=["cloud"],
            engagement_style="supportive_synthesis",  # type: ignore[arg-type]
        )
        assert draft_str.engagement_style == EngagementStyle.SUPPORTIVE_SYNTHESIS

    def test_comment_draft_invalid_engagement_style(self) -> None:
        with pytest.raises(ValidationError):
            CommentDraft(
                draft_comment="Valid draft comment text.",
                engagement_style="invalid_style",  # type: ignore[arg-type]
            )

    def test_empty_comment_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CommentDraft(draft_comment="")

    def test_comment_max_length(self) -> None:
        long_comment = "x" * 601
        with pytest.raises(ValidationError):
            CommentDraft(draft_comment=long_comment)

    def test_topic_tags_max_length(self) -> None:
        too_many_tags = ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"]
        with pytest.raises(ValidationError):
            CommentDraft(
                draft_comment="Valid draft comment text.",
                topic_tags=too_many_tags,
            )


class TestPostIdea:
    """Test suite for PostIdea schema."""

    def test_valid_post_idea(self) -> None:
        idea = PostIdea(
            should_post=True,
            headline="Why Fencing Tokens Matter in Distributed Locks",
            draft_post_text="Full post content discussing consensus and distributed locks...",
            hashtags=["#DistributedSystems", "#SoftwareArchitecture", "#Python"],
            reasoning="Timely topic following industry discussions on consensus bugs.",
        )
        assert idea.should_post is True
        assert idea.headline.startswith("Why Fencing Tokens")
        assert len(idea.hashtags) == 3

    def test_post_idea_bounds(self) -> None:
        # Headline max 120
        with pytest.raises(ValidationError):
            PostIdea(should_post=True, headline="H" * 121)

        # Draft post max 1200
        with pytest.raises(ValidationError):
            PostIdea(should_post=True, draft_post_text="P" * 1201)

        # Hashtags max 3
        with pytest.raises(ValidationError):
            PostIdea(should_post=True, hashtags=["#1", "#2", "#3", "#4"])

        # Reasoning max 240
        with pytest.raises(ValidationError):
            PostIdea(should_post=True, reasoning="R" * 241)


class TestPendingAction:
    """Test suite for PendingAction schema."""

    def test_valid_pending_action(self) -> None:
        action = PendingAction(
            item_id="pending_12345",
            action_type="approve_comment",
            post_urn="urn:li:activity:7123456789",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:7123456789/",
            author_name="Alice Engineer",
            post_excerpt="Discussing actor systems vs event-driven queues.",
            draft_text="Fascinating contrast between mailbox pressure and queue depth.",
            confidence=0.92,
            reasoning="Directly aligns with distributed systems focus area.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
            telegram_chat_id=123456789,
            telegram_message_id=42,
        )
        assert action.item_id == "pending_12345"
        assert action.action_type == "approve_comment"
        assert isinstance(action.created_at, datetime)
        assert action.telegram_message_id == 42
        assert action.engagement_style == EngagementStyle.TECHNICAL_DEEP_DIVE

    def test_serialization_round_trip(self) -> None:
        action = PendingAction(
            item_id="item_abc",
            action_type="approve_post",
            draft_text="Original post draft about architectural fitness functions.",
            confidence=0.88,
            reasoning="Scheduled weekly thought leadership post.",
            engagement_style="supportive_synthesis",
        )
        raw_json = action.model_dump_json()
        restored = PendingAction.model_validate_json(raw_json)
        assert restored.item_id == action.item_id
        assert restored.action_type == "approve_post"
        assert restored.draft_text == action.draft_text
        assert restored.engagement_style == "supportive_synthesis"

    def test_valid_pending_reaction_action(self) -> None:
        action = PendingAction(
            item_id="pending_react_123",
            action_type="approve_reaction",
            reaction_type="insightful",
            post_urn="urn:li:activity:999888",
            post_url="https://linkedin.com/feed/update/999888",
            author_name="Bob Architect",
            post_excerpt="Deep dive on memory barriers",
            draft_text="Reaction: Insightful",
            confidence=0.91,
            reasoning="Outstanding technical explanation",
        )
        assert action.action_type == "approve_reaction"
        assert action.reaction_type == "insightful"


class TestHistoryEntry:
    """Test suite for HistoryEntry schema."""

    def test_valid_history_entry(self) -> None:
        now = datetime.now(UTC)
        entry = HistoryEntry(
            item_id="item_999",
            action_type="approve_comment",
            final_status="executed_success",
            decided_at=now,
            executed_at=now,
            screenshot_path="screenshots/2026-08-30/item_999.png",
            error=None,
        )
        assert entry.final_status == "executed_success"
        assert entry.screenshot_path is not None

    def test_history_status_enum(self) -> None:
        assert HistoryStatus.EXECUTED_SUCCESS.value == "executed_success"
        assert HistoryStatus.REJECTED.value == "rejected"
        assert HistoryStatus.EXPIRED.value == "expired"
        assert HistoryStatus.EXECUTED_FAILED.value == "executed_failed"
        assert HistoryStatus.HALTED.value == "halted"

    def test_invalid_final_status(self) -> None:
        with pytest.raises(ValidationError):
            HistoryEntry(
                item_id="item_1",
                action_type="approve_comment",
                final_status="unknown_status",  # type: ignore[arg-type]
            )


class TestDailyCounters:
    """Test suite for DailyCounters schema."""

    def test_valid_counters(self) -> None:
        counters = DailyCounters(
            date="2026-08-30",
            comments_executed=3,
            posts_executed=1,
            suggestions_sent=5,
        )
        assert counters.date == "2026-08-30"
        assert counters.comments_executed == 3
        assert counters.posts_executed == 1
        assert counters.suggestions_sent == 5

    def test_negative_counters_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DailyCounters(date="2026-08-30", comments_executed=-1)


class TestPostRecord:
    """Test suite for PostRecord schema."""

    def test_valid_post_record(self) -> None:
        record = PostRecord(
            post_urn="urn:li:activity:111",
            post_url="https://linkedin.com/feed/update/urn:li:activity:111",
            author_name="Bob Builder",
            post_text="Sample post text",
            content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        assert record.post_urn == "urn:li:activity:111"
        assert isinstance(record.scraped_at, datetime)


class TestExecutionResult:
    """Test suite for ExecutionResult schema."""

    def test_valid_execution_result(self) -> None:
        result = ExecutionResult(
            success=True,
            action_type="approve_comment",
            item_id="item_123",
            post_url="https://linkedin.com/update/123",
            comment_text="Great insight!",
            screenshot_path="screenshots/item_123.png",
        )
        assert result.success is True
        assert result.error is None
        assert isinstance(result.executed_at, datetime)


class TestPostIdeationContext:
    """Test suite for PostIdeationContext schema."""

    def test_defaults(self) -> None:
        ctx = PostIdeationContext()
        assert ctx.recent_topics == []
        assert ctx.user_focus_areas == []

    def test_populated(self) -> None:
        ctx = PostIdeationContext(
            recent_topics=["distributed lock safety", "langgraph orchestration"],
            user_focus_areas=["Python", "AI Agents"],
        )
        assert len(ctx.recent_topics) == 2
        assert len(ctx.user_focus_areas) == 2


class TestCallbackDataPayload:
    """Test suite for Telegram CallbackDataPayload serialization and parsing."""

    def test_serialize_and_parse(self) -> None:
        payload = CallbackDataPayload(
            action_code=ACTION_CODE_APPROVE_COMMENT,
            item_id="pending_abc123",
        )
        raw = payload.to_callback_data()
        assert raw == "ac:pending_abc123"

        parsed = CallbackDataPayload.from_callback_data(raw)
        assert parsed.action_code == ACTION_CODE_APPROVE_COMMENT
        assert parsed.item_id == "pending_abc123"
        assert parsed.is_approval is True
        assert parsed.is_rejection is False
        assert parsed.canonical_action_type == "approve_comment"

    def test_rejection_properties(self) -> None:
        payload = CallbackDataPayload(
            action_code=ACTION_CODE_REJECT_COMMENT,
            item_id="pending_xyz",
        )
        assert payload.is_approval is False
        assert payload.is_rejection is True
        assert payload.canonical_action_type == "reject_comment"

    def test_post_actions(self) -> None:
        approve_post = CallbackDataPayload(
            action_code=ACTION_CODE_APPROVE_POST,
            item_id="post_1",
        )
        reject_post = CallbackDataPayload(
            action_code=ACTION_CODE_REJECT_POST,
            item_id="post_1",
        )
        assert approve_post.is_approval is True
        assert approve_post.canonical_action_type == "approve_post"
        assert reject_post.is_rejection is True
        assert reject_post.canonical_action_type == "reject_post"

    def test_reaction_actions(self) -> None:
        approve_rx = CallbackDataPayload(
            action_code=ACTION_CODE_APPROVE_REACTION,
            item_id="react_1",
        )
        reject_rx = CallbackDataPayload(
            action_code=ACTION_CODE_REJECT_REACTION,
            item_id="react_1",
        )
        assert approve_rx.is_approval is True
        assert approve_rx.canonical_action_type == "approve_reaction"
        assert reject_rx.is_rejection is True
        assert reject_rx.canonical_action_type == "reject_reaction"

    def test_edit_properties(self) -> None:
        payload = CallbackDataPayload(
            action_code=ACTION_CODE_EDIT,
            item_id="item_edit_999",
        )
        assert payload.is_edit is True
        assert payload.is_approval is False
        assert payload.is_rejection is False
        assert payload.canonical_action_type == "edit"

        raw = payload.to_callback_data()
        assert raw == "ed:item_edit_999"

        parsed = CallbackDataPayload.from_callback_data(raw)
        assert parsed.action_code == ACTION_CODE_EDIT
        assert parsed.item_id == "item_edit_999"
        assert parsed.is_edit is True
        assert parsed.canonical_action_type == "edit"

    def test_edit_aliases(self) -> None:
        payload_alias = CallbackDataPayload(
            action_code="edit",
            item_id="item_edit_1",
        )
        assert payload_alias.is_edit is True

        payload_ed = CallbackDataPayload(
            action_code="ed",
            item_id="item_edit_2",
        )
        assert payload_ed.is_edit is True

    def test_exceeds_64_byte_limit(self) -> None:
        long_item_id = "x" * 63
        payload = CallbackDataPayload(action_code="ac", item_id=long_item_id)
        with pytest.raises(ValueError, match="exceeds Telegram 64-byte limit"):
            payload.to_callback_data()

    def test_invalid_from_callback_data(self) -> None:
        with pytest.raises(ValueError, match="Invalid callback data format"):
            CallbackDataPayload.from_callback_data("invalid_no_colon")

        with pytest.raises(ValueError, match="Invalid callback data format"):
            CallbackDataPayload.from_callback_data("")

    def test_empty_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CallbackDataPayload(action_code="", item_id="valid_id")

        with pytest.raises(ValidationError):
            CallbackDataPayload(action_code="ac", item_id="")


class TestRepositoryDispatchPayload:
    """Test suite for RepositoryDispatchPayload schema."""

    def test_valid_payload(self) -> None:
        dispatch = RepositoryDispatchPayload(
            event_type="execute_approval",
            client_payload={"action": "approve_comment", "item_id": "item_1"},
        )
        assert dispatch.event_type == "execute_approval"
        assert dispatch.client_payload["item_id"] == "item_1"


class TestMediaAttachment:
    """Test suite for MediaAttachment schema."""

    def test_valid_image_attachment(self) -> None:
        attachment = MediaAttachment(
            media_type="image",
            file_name="architecture-diagram.png",
            file_url="https://example.com/assets/arch.png",
            slide_count=1,
        )
        assert attachment.media_type == "image"
        assert attachment.file_name == "architecture-diagram.png"
        assert attachment.slide_count == 1

    def test_valid_carousel_pdf_attachment(self) -> None:
        attachment = MediaAttachment(
            media_type="carousel_pdf",
            file_name="state-machine-guide.pdf",
            slide_count=8,
        )
        assert attachment.media_type == "carousel_pdf"
        assert attachment.slide_count == 8
        assert attachment.file_url == ""

    def test_invalid_slide_count(self) -> None:
        with pytest.raises(ValidationError):
            MediaAttachment(
                media_type="carousel_pdf",
                file_name="guide.pdf",
                slide_count=0,
            )


class TestScheduledPost:
    """Test suite for ScheduledPost schema."""

    def test_valid_scheduled_post_defaults(self) -> None:
        post = ScheduledPost(
            id="post-abc123",
            headline="Contrarian View on LLM Agents",
            post_text="Most agent failures in production stem from uncontrolled state mutability.",
        )
        assert post.id == "post-abc123"
        assert post.status == "draft"
        assert post.media == []
        assert post.topic_pillar == ""
        assert post.scheduled_time is None
        assert isinstance(post.created_at, datetime)

    def test_scheduled_post_with_media_and_time(self) -> None:
        sched_time = datetime(2026, 10, 15, 14, 30, tzinfo=UTC)
        media_item = MediaAttachment(
            media_type="carousel_pdf",
            file_name="agent-playbook.pdf",
            slide_count=6,
        )
        post = ScheduledPost(
            id="post-xyz789",
            headline="5 Rules for Production HITL Agents",
            post_text="Detailed teardown of human-in-the-loop validation.",
            scheduled_time=sched_time,
            status="scheduled",
            media=[media_item],
            topic_pillar="Agent Architecture",
        )
        assert post.status == "scheduled"
        assert len(post.media) == 1
        assert post.media[0].file_name == "agent-playbook.pdf"
        assert post.topic_pillar == "Agent Architecture"
        assert post.scheduled_time == sched_time
