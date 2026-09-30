"""Unit tests for multi-turn thread engagement, reply triage, and follow-up drafting."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr, ValidationError

from agent.browser.executor import ActionExecutor
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    PostNoLongerAvailableError,
)
from agent.llm.chains import LLMChains
from agent.llm.prompts import (
    build_thread_reply_prompt,
    build_thread_triage_prompt,
)
from agent.llm.service import LLMService
from agent.models.schemas import (
    ACTION_CODE_APPROVE_REPLY,
    ACTION_CODE_REJECT_REPLY,
    CALLBACK_ACTION_MAP,
    REVERSE_ACTION_MAP,
    ActiveThreadRecord,
    CallbackDataPayload,
    CommentDraft,
    EngagementStyle,
    ReplyTriageResult,
    ThreadReplyItem,
)


@pytest.fixture
def base_settings(tmp_path: Path) -> Settings:
    """Provide standard test Settings instance."""
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test-key"),
        nim_model_primary="meta/llama-3.1-70b-instruct",
        nim_model_fallback="meta/llama-3.1-8b-instruct",
        telegram_bot_token=SecretStr("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
        telegram_authorized_chat_id=987654321,
        user_focus_areas=["Distributed Systems", "AI Architecture"],
        dry_run=True,
    )


class TestThreadEngagementSchemas:
    """Test suite for ActiveThreadRecord, ThreadReplyItem, and ReplyTriageResult."""

    def test_active_thread_record_defaults_and_validation(self) -> None:
        record = ActiveThreadRecord(
            id="thread-rec-001",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:123456/",
            post_urn="urn:li:activity:123456",
            our_comment_urn="urn:li:comment:(activity:123456,111)",
            our_comment_text="Consensus leases mitigate split-brain risks effectively.",
            post_author="Alice Engineer",
        )

        assert record.id == "thread-rec-001"
        assert record.post_url == "https://www.linkedin.com/feed/update/urn:li:activity:123456/"
        assert record.post_author == "Alice Engineer"
        assert record.status == "active"
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.last_checked_at, datetime)

        # JSON roundtrip
        raw = record.model_dump_json()
        restored = ActiveThreadRecord.model_validate_json(raw)
        assert restored.id == record.id
        assert restored.our_comment_text == record.our_comment_text
        assert restored.status == "active"

    def test_active_thread_record_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            ActiveThreadRecord(
                id="thread-bad",
                post_url="https://linkedin.com/feed/update/1",
                post_urn="urn:li:activity:1",
                our_comment_urn="urn:li:comment:1",
                our_comment_text="Text",
                post_author="Alice",
                status="unknown_status",  # type: ignore[arg-type]
            )

    def test_thread_reply_item_validation(self) -> None:
        reply = ThreadReplyItem(
            reply_urn="urn:li:comment:(activity:123456,222)",
            parent_comment_urn="urn:li:comment:(activity:123456,111)",
            author_name="Bob Systems",
            author_headline="Distributed Systems Architect",
            reply_text="How do you handle clock drift when leases expire?",
            is_post_author=False,
        )

        assert reply.author_name == "Bob Systems"
        assert reply.author_headline == "Distributed Systems Architect"
        assert "clock drift" in reply.reply_text
        assert reply.is_post_author is False
        assert isinstance(reply.created_at, datetime)

        # Roundtrip
        raw = reply.model_dump_json()
        restored = ThreadReplyItem.model_validate_json(raw)
        assert restored.reply_urn == reply.reply_urn
        assert restored.author_name == reply.author_name

    def test_reply_triage_result_validation(self) -> None:
        # Valid reply recommendation
        triage_reply = ReplyTriageResult(
            recommendation="reply",
            confidence=0.94,
            reasoning="Substantive technical question regarding Raft lease clock drift.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
        assert triage_reply.recommendation == "reply"
        assert triage_reply.confidence == 0.94
        assert triage_reply.engagement_style == EngagementStyle.TECHNICAL_DEEP_DIVE

        # Valid ignore recommendation
        triage_ignore = ReplyTriageResult(
            recommendation="ignore",
            confidence=0.98,
            reasoning="Superficial pleasantry containing only 'Thanks for sharing!'.",
            engagement_style=None,
        )
        assert triage_ignore.recommendation == "ignore"
        assert triage_ignore.engagement_style is None

        # Confidence bounds validation
        with pytest.raises(ValidationError):
            ReplyTriageResult(
                recommendation="reply",
                confidence=1.5,
                reasoning="Invalid confidence",
            )
        with pytest.raises(ValidationError):
            ReplyTriageResult(
                recommendation="reply",
                confidence=-0.1,
                reasoning="Invalid confidence",
            )

        # Extra forbidden fields
        with pytest.raises(ValidationError):
            ReplyTriageResult.model_validate(
                {
                    "recommendation": "reply",
                    "confidence": 0.8,
                    "reasoning": "Extra field test",
                    "unexpected_key": 123,
                }
            )


class TestActionCodeMappings:
    """Test suite for 'ar' (approve_reply) and 'rr' (reject_reply) action codes."""

    def test_action_code_constants(self) -> None:
        assert ACTION_CODE_APPROVE_REPLY == "ar"
        assert ACTION_CODE_REJECT_REPLY == "rr"

    def test_callback_and_reverse_action_maps(self) -> None:
        assert CALLBACK_ACTION_MAP[ACTION_CODE_APPROVE_REPLY] == "approve_reply"
        assert CALLBACK_ACTION_MAP[ACTION_CODE_REJECT_REPLY] == "reject_reply"
        assert CALLBACK_ACTION_MAP["ar"] == "approve_reply"
        assert CALLBACK_ACTION_MAP["rr"] == "reject_reply"

        assert REVERSE_ACTION_MAP["approve_reply"] == ACTION_CODE_APPROVE_REPLY
        assert REVERSE_ACTION_MAP["reject_reply"] == ACTION_CODE_REJECT_REPLY

    def test_callback_data_payload_serialization_and_parsing(self) -> None:
        # Approve reply
        payload_ar = CallbackDataPayload(
            action_code=ACTION_CODE_APPROVE_REPLY,
            item_id="thread_item_001",
        )
        data_str_ar = payload_ar.to_callback_data()
        assert data_str_ar == "ar:thread_item_001"

        parsed_ar = CallbackDataPayload.from_callback_data(data_str_ar)
        assert parsed_ar.action_code == "ar"
        assert parsed_ar.item_id == "thread_item_001"
        assert parsed_ar.is_approval is True
        assert parsed_ar.is_rejection is False
        assert parsed_ar.canonical_action_type == "approve_reply"

        # Reject reply
        payload_rr = CallbackDataPayload(
            action_code=ACTION_CODE_REJECT_REPLY,
            item_id="thread_item_002",
        )
        data_str_rr = payload_rr.to_callback_data()
        assert data_str_rr == "rr:thread_item_002"

        parsed_rr = CallbackDataPayload.from_callback_data(data_str_rr)
        assert parsed_rr.action_code == "rr"
        assert parsed_rr.item_id == "thread_item_002"
        assert parsed_rr.is_approval is False
        assert parsed_rr.is_rejection is True
        assert parsed_rr.canonical_action_type == "reject_reply"


class TestThreadPromptBuilders:
    """Test suite for thread prompt template formatting."""

    def test_thread_triage_prompt_formatting(self) -> None:
        prompt = build_thread_triage_prompt()
        messages = prompt.format_messages(
            original_post="Post on distributed databases.",
            our_comment="Fencing tokens prevent split-brain.",
            author_name="Charlie",
            author_headline="Backend Engineer",
            is_post_author="No",
            reply_text="How do fencing tokens interact with ZooKeeper zxid?",
        )
        assert len(messages) == 2
        human_text = messages[1].content
        assert "How do fencing tokens interact with ZooKeeper zxid?" in human_text
        assert "Charlie" in human_text

    def test_thread_reply_prompt_formatting(self) -> None:
        prompt = build_thread_reply_prompt()
        messages = prompt.format_messages(
            original_post="Post on distributed databases.",
            our_comment="Fencing tokens prevent split-brain.",
            author_name="Charlie",
            author_headline="Backend Engineer",
            is_post_author="No",
            reply_text="How do fencing tokens interact with ZooKeeper zxid?",
            triage_reasoning="Sharp technical question on zxid coordination.",
            engagement_style="technical_deep_dive",
        )
        assert len(messages) == 2
        human_text = messages[1].content
        assert "technical_deep_dive" in human_text
        assert "Sharp technical question" in human_text


class TestLLMServiceThreadEngagement:
    """Test suite for LLMService thread reply triage and follow-up drafting."""

    @pytest.mark.asyncio
    async def test_triage_empty_reply_ignores_without_llm(self, base_settings: Settings) -> None:
        mock_triage_chain = AsyncMock()
        mock_chains = LLMChains(
            triage=mock_triage_chain,
            comment=AsyncMock(),
            post_idea=AsyncMock(),
            thread_triage=mock_triage_chain,
        )
        service = LLMService(base_settings, chains=mock_chains)

        empty_reply = ThreadReplyItem(
            reply_urn="urn:1",
            parent_comment_urn="urn:parent",
            author_name="Member",
            reply_text="   \n  ",
        )

        result = await service.triage_thread_reply(
            reply=empty_reply,
            our_comment="Our prior comment text",
            original_post="Original post content",
        )

        assert result.recommendation == "ignore"
        assert result.confidence == 1.0
        assert "empty or contains only whitespace" in result.reasoning
        mock_triage_chain.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_triage_filters_superficial_pleasantry(self, base_settings: Settings) -> None:
        expected_triage = ReplyTriageResult(
            recommendation="ignore",
            confidence=0.98,
            reasoning="Superficial affirmation without technical substance.",
            engagement_style=None,
        )
        mock_thread_triage_chain = AsyncMock()
        mock_thread_triage_chain.ainvoke.return_value = expected_triage

        mock_chains = LLMChains(
            triage=AsyncMock(),
            comment=AsyncMock(),
            post_idea=AsyncMock(),
            thread_triage=mock_thread_triage_chain,
        )
        service = LLMService(base_settings, chains=mock_chains)

        pleasantry_reply = ThreadReplyItem(
            reply_urn="urn:reply:thanks",
            parent_comment_urn="urn:parent:1",
            author_name="Dave",
            reply_text="Thanks! Great point!",
        )

        result = await service.triage_thread_reply(
            reply=pleasantry_reply,
            our_comment="Fencing tokens prevent split-brain.",
            original_post="Distributed consensus patterns.",
        )

        assert result.recommendation == "ignore"
        assert result.confidence == 0.98
        assert mock_thread_triage_chain.ainvoke.called

    @pytest.mark.asyncio
    async def test_triage_prioritizes_substantive_technical_question(
        self, base_settings: Settings
    ) -> None:
        expected_triage = ReplyTriageResult(
            recommendation="reply",
            confidence=0.95,
            reasoning="Incisive technical question on consensus failure modes.",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
        mock_thread_triage_chain = AsyncMock()
        mock_thread_triage_chain.ainvoke.return_value = expected_triage

        mock_chains = LLMChains(
            triage=AsyncMock(),
            comment=AsyncMock(),
            post_idea=AsyncMock(),
            thread_triage=mock_thread_triage_chain,
        )
        service = LLMService(base_settings, chains=mock_chains)

        substantive_reply = ThreadReplyItem(
            reply_urn="urn:reply:question",
            parent_comment_urn="urn:parent:1",
            author_name="Elena",
            author_headline="Distributed Systems Engineer",
            reply_text="How do you handle epoch fencing when the storage backend doesn't support atomic conditional writes?",
            is_post_author=True,
        )

        result = await service.triage_thread_reply(
            reply=substantive_reply,
            our_comment="Epoch fencing tokens guarantee single-writer safety.",
            original_post="Storage layer concurrency models.",
        )

        assert result.recommendation == "reply"
        assert result.confidence == 0.95
        assert result.engagement_style == EngagementStyle.TECHNICAL_DEEP_DIVE

    @pytest.mark.asyncio
    async def test_draft_thread_reply_contextual_and_anti_cliche(
        self, base_settings: Settings
    ) -> None:
        expected_draft = CommentDraft(
            draft_comment="Without atomic conditional writes, you must rely on an external coordinator like Consul sessions or Raft-backed leases to enforce fencing before issuing mutations.",
            topic_tags=["distributed-systems", "storage"],
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
        mock_thread_reply_chain = AsyncMock()
        mock_thread_reply_chain.ainvoke.return_value = expected_draft

        mock_chains = LLMChains(
            triage=AsyncMock(),
            comment=AsyncMock(),
            post_idea=AsyncMock(),
            thread_reply=mock_thread_reply_chain,
        )
        service = LLMService(base_settings, chains=mock_chains)

        reply_item = ThreadReplyItem(
            reply_urn="urn:reply:q1",
            parent_comment_urn="urn:parent:1",
            author_name="Elena",
            reply_text="How do you fence without atomic compare-and-swap?",
        )
        triage = ReplyTriageResult(
            recommendation="reply",
            confidence=0.95,
            reasoning="Substantive technical question",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )

        draft = await service.draft_thread_reply(
            reply=reply_item,
            our_comment="Epoch fencing tokens guarantee single-writer safety.",
            original_post="Storage layer concurrency.",
            triage=triage,
        )

        assert "atomic conditional writes" in draft.draft_comment
        assert len(draft.draft_comment) <= 400
        assert draft.engagement_style == EngagementStyle.TECHNICAL_DEEP_DIVE


class TestBrowserExecutorThreadEngagement:
    """Test suite for ActionExecutor inspect_comment_replies and post_thread_reply."""

    @pytest.mark.asyncio
    async def test_inspect_comment_replies_success(self, base_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
        page.screenshot = AsyncMock()

        # Mock author locator
        author_loc = MagicMock()
        author_loc.count = AsyncMock(return_value=1)
        author_loc.inner_text = AsyncMock(return_value="Sarah Founder")

        # Mock parent comment
        parent_comment = MagicMock()
        parent_comment.inner_text = AsyncMock(
            return_value="Alice: Fencing tokens ensure single-writer safety."
        )
        parent_comment.get_attribute = AsyncMock(
            side_effect=lambda attr: "urn:li:comment:parent-100" if attr == "data-id" else None
        )

        # Mock replies
        reply_1 = MagicMock()
        reply_1.get_attribute = AsyncMock(return_value="urn:li:comment:reply-1")
        name_1 = MagicMock(count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="Bob"))
        headline_1 = MagicMock(
            count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="SRE")
        )
        body_1 = MagicMock(
            count=AsyncMock(return_value=1),
            inner_text=AsyncMock(return_value="How does this behave under network partition?"),
        )
        badge_1 = MagicMock(count=AsyncMock(return_value=0))

        def reply_1_locator(sel: str) -> MagicMock:
            if "badge" in sel or "Author" in sel:
                return badge_1
            if "name" in sel:
                loc = MagicMock()
                loc.first = name_1
                loc.count = name_1.count
                return loc
            if "headline" in sel or "occupation" in sel:
                loc = MagicMock()
                loc.first = headline_1
                loc.count = headline_1.count
                return loc
            if "main-content" in sel or "content-body" in sel or "message" in sel or "update-components-text" in sel:
                loc = MagicMock()
                loc.first = body_1
                loc.count = body_1.count
                return loc
            return MagicMock(count=AsyncMock(return_value=0))

        reply_1.locator = MagicMock(side_effect=reply_1_locator)

        # Reply 2 from the post author
        reply_2 = MagicMock()
        reply_2.get_attribute = AsyncMock(return_value="urn:li:comment:reply-2")
        name_2 = MagicMock(
            count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="Sarah Founder")
        )
        headline_2 = MagicMock(
            count=AsyncMock(return_value=1), inner_text=AsyncMock(return_value="CTO")
        )
        body_2 = MagicMock(
            count=AsyncMock(return_value=1),
            inner_text=AsyncMock(return_value="We adopted this in production last quarter."),
        )
        badge_2 = MagicMock(count=AsyncMock(return_value=1))

        def reply_2_locator(sel: str) -> MagicMock:
            if "badge" in sel or "Author" in sel:
                return badge_2
            if "name" in sel:
                loc = MagicMock()
                loc.first = name_2
                loc.count = name_2.count
                return loc
            if "headline" in sel or "occupation" in sel:
                loc = MagicMock()
                loc.first = headline_2
                loc.count = headline_2.count
                return loc
            if "main-content" in sel or "content-body" in sel or "message" in sel or "update-components-text" in sel:
                loc = MagicMock()
                loc.first = body_2
                loc.count = body_2.count
                return loc
            return MagicMock(count=AsyncMock(return_value=0))

        reply_2.locator = MagicMock(side_effect=reply_2_locator)

        # Parent replies locator
        replies_loc = MagicMock()
        replies_loc.count = AsyncMock(return_value=2)
        replies_loc.nth = MagicMock(side_effect=lambda idx: reply_1 if idx == 0 else reply_2)

        def parent_locator_side_effect(sel: str) -> MagicMock:
            if "reply" in sel:
                return replies_loc
            return MagicMock(count=AsyncMock(return_value=0))

        parent_comment.locator = MagicMock(side_effect=parent_locator_side_effect)

        # Page comments list
        comments_list = MagicMock()
        comments_list.count = AsyncMock(return_value=1)
        comments_list.nth = MagicMock(return_value=parent_comment)

        def page_locator_side_effect(sel: str) -> MagicMock:
            if "actor__name" in sel:
                loc = MagicMock()
                loc.first = author_loc
                loc.count = author_loc.count
                return loc
            if "comments-comment-item" in sel or "comments-list" in sel:
                return comments_list
            return MagicMock(count=AsyncMock(return_value=0))

        page.locator = MagicMock(side_effect=page_locator_side_effect)

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

        replies = await executor.inspect_comment_replies(
            post_url=page.url,
            our_comment_text="Fencing tokens ensure single-writer safety.",
        )

        assert len(replies) == 2
        assert replies[0].author_name == "Bob"
        assert replies[0].is_post_author is False
        assert replies[1].author_name == "Sarah Founder"
        assert replies[1].is_post_author is True

    @pytest.mark.asyncio
    async def test_inspect_comment_replies_our_comment_not_found(
        self, base_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
        comments_list = MagicMock(count=AsyncMock(return_value=0))
        page.locator = MagicMock(return_value=comments_list)

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

        replies = await executor.inspect_comment_replies(
            post_url=page.url,
            our_comment_text="Nonexistent comment text snippet",
        )
        assert replies == []

    @pytest.mark.asyncio
    async def test_inspect_comment_replies_challenge_raises_bot_detection(
        self, base_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/checkpoint/challenge"
        page.screenshot = AsyncMock()

        executor = ActionExecutor(page, base_settings)
        with pytest.raises(BotDetectionError):
            await executor.inspect_comment_replies(
                post_url=page.url,
                our_comment_text="Any text",
            )

    @pytest.mark.asyncio
    async def test_post_thread_reply_dry_run(self, base_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
        page.screenshot = AsyncMock()

        reply_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
        reply_box = MagicMock(count=AsyncMock(return_value=1))

        def locator_side_effect(selector: str) -> MagicMock:
            loc = MagicMock()
            if "Reply" in selector or "reply-button" in selector:
                loc.first = reply_btn
                loc.count = reply_btn.count
                return loc
            if "textbox" in selector or "ql-editor" in selector or "tiptap" in selector:
                loc.first = reply_box
                loc.count = reply_box.count
                return loc
            empty = MagicMock(count=AsyncMock(return_value=0))
            empty.first = empty
            return empty

        page.locator = MagicMock(side_effect=locator_side_effect)

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await executor.post_thread_reply(
            post_url=page.url,
            comment_urn="urn:li:comment:111",
            reply_text="Leases tied to monotonic clocks prevent drift.",
            item_id="dryrun_reply_001",
            dry_run=True,
        )

        assert result.success is True
        assert result.action_type == "approve_reply"
        assert result.item_id == "dryrun_reply_001"
        assert result.comment_text == "Leases tied to monotonic clocks prevent drift."
        assert "dryrun_reply_dryrun_reply_001" in str(result.screenshot_path)

    @pytest.mark.asyncio
    async def test_post_thread_reply_live_success(self, base_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
        page.screenshot = AsyncMock()

        # Elements
        reply_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
        reply_box = MagicMock(
            count=AsyncMock(return_value=1),
            focus=AsyncMock(),
            press_sequentially=AsyncMock(),
            inner_text=AsyncMock(return_value="Lease timeout reply"),
        )
        submit_btn = MagicMock(
            count=AsyncMock(return_value=1),
            click=AsyncMock(),
            is_disabled=AsyncMock(return_value=False),
        )
        comment_item = MagicMock(
            count=AsyncMock(return_value=1),
            inner_text=AsyncMock(return_value="Lease timeout reply in thread"),
        )
        comment_item.filter = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=1)))

        def locator_side_effect(selector: str) -> MagicMock:
            loc = MagicMock()
            if "submit" in selector:
                loc.first = submit_btn
                loc.count = submit_btn.count
                return loc
            if "textbox" in selector or "ql-editor" in selector or "tiptap" in selector:
                loc.first = reply_box
                loc.count = reply_box.count
                return loc
            if "Reply" in selector or "reply-button" in selector:
                loc.first = reply_btn
                loc.count = reply_btn.count
                return loc
            if "comment-item" in selector or "comments-list" in selector:
                return comment_item
            if "toast" in selector or "alert" in selector:
                loc.first = MagicMock(count=AsyncMock(return_value=0))
                loc.count = AsyncMock(return_value=0)
                return loc
            empty = MagicMock(count=AsyncMock(return_value=0))
            empty.first = empty
            return empty

        page.locator = MagicMock(side_effect=locator_side_effect)

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await executor.post_thread_reply(
            post_url=page.url,
            comment_urn="urn:li:comment:111",
            reply_text="Lease timeout reply",
            item_id="live_reply_001",
            dry_run=False,
            verification_timeout=1.0,
        )

        assert result.success is True
        assert result.action_type == "approve_reply"
        assert result.comment_text == "Lease timeout reply"
        assert "success_reply_live_reply_001" in str(result.screenshot_path)
        assert reply_btn.click.called
        assert submit_btn.click.called

    @pytest.mark.asyncio
    async def test_post_thread_reply_missing_post_raises(self, base_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:missing/"
        page.screenshot = AsyncMock()

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=False)  # type: ignore[method-assign]

        with pytest.raises(PostNoLongerAvailableError):
            await executor.post_thread_reply(
                post_url=page.url,
                comment_urn="urn:li:comment:111",
                reply_text="Text",
                item_id="missing_test",
                dry_run=False,
            )

    @pytest.mark.asyncio
    async def test_post_thread_reply_missing_box_raises_execution_error(
        self, base_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
        page.screenshot = AsyncMock()

        reply_btn = MagicMock(count=AsyncMock(return_value=1), click=AsyncMock())
        empty_loc = MagicMock(count=AsyncMock(return_value=0))
        empty_loc.first = empty_loc

        def locator_side_effect(selector: str) -> MagicMock:
            if "Reply" in selector or "reply-button" in selector:
                loc = MagicMock()
                loc.first = reply_btn
                loc.count = reply_btn.count
                return loc
            return empty_loc

        page.locator = MagicMock(side_effect=locator_side_effect)

        executor = ActionExecutor(page, base_settings)
        executor.verify_post_exists = AsyncMock(return_value=True)  # type: ignore[method-assign]

        with pytest.raises(ExecutionError) as exc_info:
            await executor.post_thread_reply(
                post_url=page.url,
                comment_urn="urn:li:comment:111",
                reply_text="Text",
                item_id="fail_box_001",
                dry_run=False,
            )

        assert "Comment reply input box not found in DOM" in str(exc_info.value)
