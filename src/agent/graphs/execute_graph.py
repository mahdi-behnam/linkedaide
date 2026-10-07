"""Execute workflow graph: validate approval, execute LinkedIn action, update state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.errors import BotDetectionError, SessionExpiredError
from agent.graphs.state import ExecuteState, get_graph_context
from agent.llm.voice_memory import VoiceMemoryStore
from agent.models import ActiveThreadRecord, ExecutionResult, HistoryEntry, PendingAction
from agent.safety.circuit_breaker import is_halted, trip_breaker
from agent.telegram.keyboards import build_outcome_message


async def check_halted(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Check if the system is currently halted."""
    context = get_graph_context(config)
    halted, reason = is_halted(
        context.settings.state_dir.parent, context.settings, state_store=context.state_store
    )
    if halted:
        return {"halted_reason": reason, "status": "halted"}
    return {"halted_reason": None, "status": "active"}


async def load_pending(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Load pending action from GitStateStore or fallback to connection candidate / scheduled post."""
    context = get_graph_context(config)
    if not context.state_store:
        return {"pending": None, "status": "missing"}

    item_id = state.get("item_id", "")
    pending = context.state_store.read_pending(item_id)
    if pending is None:
        # Check if item_id matches a connection request candidate
        conn_candidate = context.state_store.read_connection_candidate(item_id)
        if conn_candidate is not None:
            pending = PendingAction(
                item_id=conn_candidate.id,
                action_type="approve_connection",
                created_at=conn_candidate.approved_at or datetime.now(UTC),
                post_url=conn_candidate.profile_url,
                author_name=conn_candidate.target_name,
                author_headline=conn_candidate.target_headline,
                draft_text=conn_candidate.note_text,
                reasoning=conn_candidate.mutual_context,
                telegram_chat_id=context.settings.telegram_authorized_chat_id,
            )
        else:
            # Check if item_id matches a scheduled post
            sched_post = context.state_store.read_scheduled_post(item_id)
            if sched_post is not None:
                sched_created_at: datetime
                if isinstance(sched_post.scheduled_time, str):
                    try:
                        sched_created_at = datetime.fromisoformat(sched_post.scheduled_time)
                    except ValueError:
                        sched_created_at = sched_post.created_at
                elif isinstance(sched_post.scheduled_time, datetime):
                    sched_created_at = sched_post.scheduled_time
                elif sched_post.approved_at is not None:
                    sched_created_at = sched_post.approved_at
                else:
                    sched_created_at = datetime.now(UTC)

                pending = PendingAction(
                    item_id=sched_post.id,
                    action_type="approve_post",
                    created_at=sched_created_at,
                    post_url="",
                    author_name="You",
                    author_headline="",
                    draft_text=sched_post.post_text,
                    reasoning=sched_post.topic_pillar or "Scheduled original post",
                    media_attachments=sched_post.media,
                    telegram_chat_id=context.settings.telegram_authorized_chat_id,
                )
    return {"pending": pending}


async def notify_already_handled(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Notify operator that action was already consumed or does not exist."""
    context = get_graph_context(config)
    chat_id = state.get("telegram_chat_id") or context.settings.telegram_authorized_chat_id
    msg_id = state.get("telegram_message_id")
    if context.telegram and msg_id:
        await context.telegram.edit_to_outcome(
            chat_id=chat_id,
            message_id=msg_id,
            outcome_text="ℹ️ This action was already processed or is no longer available.",
        )
    return {"status": "already_handled"}


async def handle_rejection(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Handle operator reject decision."""
    context = get_graph_context(config)
    item_id = state.get("item_id", "")
    pending = state.get("pending")
    now = datetime.now(UTC)

    entry = HistoryEntry(
        item_id=item_id,
        action_type=pending.action_type if pending else "reject",
        final_status="rejected",
        decided_at=now,
        executed_at=None,
        screenshot_path=None,
        error=None,
    )

    if context.state_store:
        context.state_store.append_history(entry)
        context.state_store.delete_pending(item_id)
        if pending and pending.action_type == "approve_connection":
            context.state_store.update_connection_status(item_id, status="rejected")
        elif pending and pending.action_type == "approve_post":
            sched_post = context.state_store.read_scheduled_post(item_id)
            if sched_post:
                context.state_store.save_scheduled_post(
                    sched_post.model_copy(update={"status": "rejected"})
                )

    chat_id = state.get("telegram_chat_id") or (
        pending.telegram_chat_id if pending else context.settings.telegram_authorized_chat_id
    )
    msg_id = state.get("telegram_message_id") or (pending.telegram_message_id if pending else None)

    if context.telegram and msg_id and chat_id is not None:
        await context.telegram.edit_to_outcome(
            chat_id=chat_id,
            message_id=msg_id,
            outcome_text="❌ Suggestion rejected by operator.",
        )

    return {"outcome": entry, "status": "rejected"}


async def validate_request(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Validate sender authorization, approval TTL, and daily action caps."""
    context = get_graph_context(config)
    chat_id = state.get("telegram_chat_id") or context.settings.telegram_authorized_chat_id
    if not context.telegram or not context.telegram.is_authorized(chat_id, context.settings):
        return {"error": "Unauthorized Telegram sender identity", "status": "validation_failed"}

    pending = state.get("pending")
    if not pending:
        return {"error": "Pending action not found", "status": "validation_failed"}

    if context.enforcer:
        # Pre-scheduled posts originating from the scheduling calendar and queued connections
        # have their own scheduling lifecycle; Telegram pending suggestion TTL only applies to
        # ephemeral feed comment/reply approvals or items in the pending store.
        is_prescheduled = pending.action_type in ("approve_post", "approve_connection") and (
            context.state_store is not None
            and (
                context.state_store.read_scheduled_post(pending.item_id) is not None
                or context.state_store.read_connection_candidate(pending.item_id) is not None
            )
        )
        if not is_prescheduled and not context.enforcer.is_within_ttl(pending):
            return {
                "error": "Pending approval expired (exceeded TTL)",
                "status": "validation_failed_expired",
            }

        if context.state_store:
            counters = context.state_store.load_daily_counters()
            if pending.action_type in ("approve_comment", "approve_reply"):
                can_exec, reason = context.enforcer.can_execute_comment(counters)
                if not can_exec:
                    return {
                        "error": reason or "Daily comment cap reached",
                        "status": "validation_failed_cap",
                    }
            elif pending.action_type == "approve_post":
                can_exec, reason = context.enforcer.can_execute_post(counters)
                if not can_exec:
                    return {
                        "error": reason or "Daily post cap reached",
                        "status": "validation_failed_cap",
                    }
            elif pending.action_type == "approve_connection":
                can_exec, reason = context.enforcer.can_execute_connection(counters)
                if not can_exec:
                    return {
                        "error": reason or "Daily connection cap reached",
                        "status": "validation_failed_cap",
                    }

    return {"status": "validated"}


async def verify_target(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Verify target post still exists and LinkedIn session is authenticated."""
    context = get_graph_context(config)
    pending = state.get("pending")
    if not pending or not context.executor:
        return {"status": "target_verified"}

    item_id = state.get("item_id", "")
    chat_id = state.get("telegram_chat_id") or (
        pending.telegram_chat_id if pending else context.settings.telegram_authorized_chat_id
    )
    msg_id = state.get("telegram_message_id") or (pending.telegram_message_id if pending else None)
    if context.telegram and msg_id and chat_id is not None:
        try:
            await context.telegram.edit_to_outcome(
                chat_id=chat_id,
                message_id=msg_id,
                outcome_text=f"🧭 <b>[2/3] Verifying Target & Session...</b>\n\n<b>Item:</b> <code>{item_id}</code>",
            )
        except Exception:
            pass

    try:
        logged_in = await context.executor.verify_login()
        if not logged_in:
            return {"error": "LinkedIn session is not authenticated", "status": "session_error"}

        if pending.action_type in ("approve_comment", "approve_reply", "approve_reaction"):
            exists = await context.executor.verify_post_exists(pending.post_url)
            if not exists:
                return {"error": "Target post is no longer available", "status": "post_missing"}

        return {"status": "target_verified"}
    except BotDetectionError as err:
        if context.state_store:
            trip_breaker(
                context.settings.state_dir.parent, str(err), state_store=context.state_store
            )
        return {"halted_reason": str(err), "status": "halted_challenge"}
    except SessionExpiredError as err:
        return {"error": str(err), "status": "session_expired"}
    except Exception as err:
        return {"error": str(err), "status": "target_check_error"}


async def execute_browser_action(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Execute approved LinkedIn comment or post action."""
    context = get_graph_context(config)
    pending = state.get("pending")
    if not pending or not context.executor:
        return {"status": "executed_mock"}

    item_id = state.get("item_id", "")
    chat_id = state.get("telegram_chat_id") or (
        pending.telegram_chat_id if pending else context.settings.telegram_authorized_chat_id
    )
    msg_id = state.get("telegram_message_id") or (pending.telegram_message_id if pending else None)
    if context.telegram and msg_id and chat_id is not None:
        try:
            await context.telegram.edit_to_outcome(
                chat_id=chat_id,
                message_id=msg_id,
                outcome_text=f"✍️ <b>[3/3] Submitting to LinkedIn...</b>\n\n<b>Item:</b> <code>{item_id}</code>",
            )
        except Exception:
            pass

    try:
        verification_url = None
        if pending.action_type == "approve_comment":
            result = await context.executor.post_comment(
                post_url=pending.post_url,
                comment_text=pending.draft_text,
                item_id=pending.item_id,
            )
            verification_url = (
                getattr(result, "comment_url", None) or result.post_url or pending.post_url
            )
        elif pending.action_type == "approve_reply":
            result = await context.executor.post_thread_reply(
                post_url=pending.post_url,
                comment_urn=pending.post_urn,
                reply_text=pending.draft_text,
                item_id=pending.item_id,
            )
            verification_url = (
                getattr(result, "comment_url", None) or result.post_url or pending.post_url
            )
        elif pending.action_type == "approve_connection":
            result = await context.executor.send_connection_request(
                profile_url=pending.post_url,
                note_text=pending.draft_text or None,
                item_id=pending.item_id,
            )
            verification_url = getattr(result, "post_url", None) or pending.post_url
        elif pending.action_type == "approve_reaction":
            rx_type = getattr(pending, "reaction_type", None) or "like"
            rx_success = await context.executor.react_to_post(
                reaction_type=rx_type,
                item_id=pending.item_id,
            )
            result = ExecutionResult(
                success=rx_success,
                action_type="approve_reaction",
                item_id=pending.item_id,
                post_url=pending.post_url,
                screenshot_path=None,
                error=None if rx_success else f"Reaction '{rx_type}' execution failed",
                executed_at=datetime.now(UTC),
            )
            verification_url = pending.post_url
        else:
            result = await context.executor.create_post(
                post_text=pending.draft_text,
                item_id=pending.item_id,
                media=getattr(pending, "media_attachments", None) or None,
            )
            verification_url = (
                getattr(result, "published_post_url", None)
                or getattr(result, "post_url", None)
                or None
            )

        now = datetime.now(UTC)
        entry = HistoryEntry(
            item_id=pending.item_id,
            action_type=pending.action_type,
            final_status="executed_success" if result.success else "executed_failed",
            decided_at=now,
            executed_at=now,
            screenshot_path=result.screenshot_path,
            error=result.error,
        )
        if not result.success:
            return {
                "outcome": entry,
                "error": result.error or "Action execution failed",
                "status": "execution_failed",
            }
        return {
            "outcome": entry,
            "status": "execution_success",
            "verification_url": verification_url,
        }
    except BotDetectionError as err:
        if context.state_store:
            trip_breaker(
                context.settings.state_dir.parent, str(err), state_store=context.state_store
            )
        return {"halted_reason": str(err), "status": "halted_challenge"}
    except Exception as err:
        now = datetime.now(UTC)
        entry = HistoryEntry(
            item_id=pending.item_id,
            action_type=pending.action_type,
            final_status="executed_failed",
            decided_at=now,
            executed_at=now,
            screenshot_path=None,
            error=str(err),
        )
        return {"outcome": entry, "error": str(err), "status": "execution_failed"}


async def persist_success(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Persist history, update daily counters, and delete consumed pending item."""
    context = get_graph_context(config)
    if not context.state_store:
        return {}

    pending = state.get("pending")
    outcome = state.get("outcome")

    if outcome:
        context.state_store.append_history(outcome)

    if pending:
        context.state_store.delete_pending(pending.item_id)
        if pending.action_type in ("approve_comment", "approve_reply"):
            context.state_store.increment_comment_count()
            # If comment/reply was successfully executed, index into VoiceMemory for continuous learning
            if outcome and outcome.final_status == "executed_success":
                voice_mem = context.voice_memory or (
                    context.llm.voice_memory if context.llm else None
                )
                if not voice_mem and context.state_store:
                    voice_mem = VoiceMemoryStore(state_store=context.state_store)
                if voice_mem:
                    voice_mem.index_executed_comment(
                        item_id=pending.item_id,
                        comment_text=pending.draft_text,
                        post_excerpt=pending.post_excerpt or pending.reasoning or "",
                    )

            # If a top-level comment was successfully posted, save ActiveThreadRecord for thread monitoring
            if (
                pending.action_type == "approve_comment"
                and outcome
                and outcome.final_status == "executed_success"
            ):
                thread_record = ActiveThreadRecord(
                    id=f"thread-{pending.item_id}",
                    post_url=pending.post_url,
                    post_urn=pending.post_urn,
                    our_comment_urn=f"urn:li:comment:({pending.post_urn})",
                    our_comment_text=pending.draft_text,
                    post_author=pending.author_name,
                )
                context.state_store.save_active_thread(thread_record)
        elif pending.action_type == "approve_post":
            context.state_store.increment_post_count()
            sched_post = context.state_store.read_scheduled_post(pending.item_id)
            if sched_post:
                context.state_store.save_scheduled_post(
                    sched_post.model_copy(update={"status": "published"})
                )
        elif pending.action_type == "approve_connection":
            context.state_store.increment_connection_count()
            context.state_store.update_connection_status(pending.item_id, status="sent")

    return {}


async def notify_success(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Update Telegram suggestion message with success outcome."""
    context = get_graph_context(config)
    pending = state.get("pending")
    chat_id = state.get("telegram_chat_id") or (
        pending.telegram_chat_id if pending else context.settings.telegram_authorized_chat_id
    )
    msg_id = state.get("telegram_message_id") or (pending.telegram_message_id if pending else None)
    verification_url = state.get("verification_url")

    if context.telegram and msg_id and chat_id is not None:
        outcome_text = build_outcome_message(
            item=pending,
            final_status="executed_success",
            verification_url=verification_url,
        )
        await context.telegram.edit_to_outcome(chat_id, msg_id, outcome_text)

    return {"status": "completed_success"}


async def handle_failure(state: ExecuteState, config: RunnableConfig) -> dict[str, Any]:
    """Record failure outcome and update Telegram."""
    context = get_graph_context(config)
    error = state.get("error", "Action execution failed")
    pending = state.get("pending")
    item_id = state.get("item_id", "")
    now = datetime.now(UTC)

    final_status: Literal[
        "rejected", "expired", "executed_success", "executed_failed", "halted"
    ] = "expired" if "expired" in state.get("status", "") else "executed_failed"

    entry = HistoryEntry(
        item_id=item_id,
        action_type=pending.action_type if pending else "execute",
        final_status=final_status,
        decided_at=now,
        executed_at=now,
        screenshot_path=None,
        error=error,
    )

    if context.state_store:
        context.state_store.append_history(entry)
        if pending:
            context.state_store.delete_pending(pending.item_id)
            if pending.action_type == "approve_connection":
                context.state_store.update_connection_status(pending.item_id, status="failed")
            elif pending.action_type == "approve_post":
                sched_post = context.state_store.read_scheduled_post(pending.item_id)
                if sched_post:
                    context.state_store.save_scheduled_post(
                        sched_post.model_copy(update={"status": "failed"})
                    )

    chat_id = state.get("telegram_chat_id") or (
        pending.telegram_chat_id if pending else context.settings.telegram_authorized_chat_id
    )
    msg_id = state.get("telegram_message_id") or (pending.telegram_message_id if pending else None)

    if context.telegram and msg_id and chat_id is not None:
        outcome_text = f"⚠️ Could not execute action: {error}"
        await context.telegram.edit_to_outcome(chat_id, msg_id, outcome_text)

    return {"outcome": entry, "status": "failed"}


# Routing
def route_after_halt(state: ExecuteState) -> str:
    if state.get("halted_reason"):
        return END
    return "load_pending"


def route_by_action(state: ExecuteState) -> str:
    pending = state.get("pending")
    if not pending:
        return "notify_already_handled"
    if state.get("action") == "reject":
        return "handle_rejection"
    return "validate_request"


def route_after_validate(state: ExecuteState) -> str:
    status = state.get("status", "")
    if status == "validated":
        return "verify_target"
    return "handle_failure"


def route_after_target(state: ExecuteState) -> str:
    status = state.get("status", "")
    if status == "target_verified":
        return "execute_browser_action"
    return "handle_failure"


def route_after_exec(state: ExecuteState) -> str:
    if state.get("status") == "execution_success":
        return "persist_success"
    return "handle_failure"


def build_execute_graph() -> Any:
    """Build and compile the deterministic Execute StateGraph."""
    graph = StateGraph(ExecuteState)

    graph.add_node("check_halted", check_halted)
    graph.add_node("load_pending", load_pending)
    graph.add_node("notify_already_handled", notify_already_handled)
    graph.add_node("handle_rejection", handle_rejection)
    graph.add_node("validate_request", validate_request)
    graph.add_node("verify_target", verify_target)
    graph.add_node("execute_browser_action", execute_browser_action)
    graph.add_node("persist_success", persist_success)
    graph.add_node("notify_success", notify_success)
    graph.add_node("handle_failure", handle_failure)

    graph.add_edge(START, "check_halted")
    graph.add_conditional_edges("check_halted", route_after_halt, [END, "load_pending"])
    graph.add_conditional_edges(
        "load_pending",
        route_by_action,
        ["notify_already_handled", "handle_rejection", "validate_request"],
    )
    graph.add_edge("notify_already_handled", END)
    graph.add_edge("handle_rejection", END)
    graph.add_conditional_edges(
        "validate_request", route_after_validate, ["verify_target", "handle_failure"]
    )
    graph.add_conditional_edges(
        "verify_target", route_after_target, ["execute_browser_action", "handle_failure"]
    )
    graph.add_conditional_edges(
        "execute_browser_action", route_after_exec, ["persist_success", "handle_failure"]
    )
    graph.add_edge("persist_success", "notify_success")
    graph.add_edge("notify_success", END)
    graph.add_edge("handle_failure", END)

    return graph.compile()
