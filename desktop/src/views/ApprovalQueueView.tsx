import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";
import {
  Check,
  ArrowClockwise,
  WarningCircle,
  Keyboard,
  Sparkle,
} from "@phosphor-icons/react";
import { useQueueShortcuts } from "../hooks/useQueueShortcuts";
import { useDeepNavigation, highlightAndScrollTo } from "../hooks/useDeepNavigation";
import { KeyboardShortcutsModal } from "../components/KeyboardShortcutsModal";
import { QueueLeftPane, FilterType } from "../components/queue/QueueLeftPane";
import { QueueWorkspaceHeader } from "../components/queue/QueueWorkspaceHeader";
import { QueueTargetSection } from "../components/queue/QueueTargetSection";
import { QueueRationaleSection } from "../components/queue/QueueRationaleSection";
import { QueueDraftEditorSection } from "../components/queue/QueueDraftEditorSection";
import { QueueSafetyFooter } from "../components/queue/QueueSafetyFooter";
import { PendingItem } from "../components/queue/QueueTriageCard";

export type { PendingItem };

const TONE_CYCLE = ["technical", "inquisitive", "contrarian", "shorter"];

export const mapRawPending = (rawPending: any[]): PendingItem[] => {
  return rawPending.map((p: any) => {
    let actionType: "comment" | "post" | "reaction" | "reply" = "comment";
    const rawType = (p.action_type || "").toLowerCase();
    if (rawType.includes("reaction")) {
      actionType = "reaction";
    } else if (rawType.includes("post")) {
      actionType = "post";
    } else if (rawType.includes("reply")) {
      actionType = "reply";
    }

    return {
      id: p.item_id,
      actionType,
      reactionType: p.reaction_type || "like",
      author: p.author_name || (actionType === "post" ? "You (Draft)" : "Unknown Author"),
      headline: p.author_headline || (actionType === "post" ? "Original Post Suggestion" : "LinkedIn Member"),
      postUrl: p.post_url || "",
      postExcerpt: p.post_excerpt || "",
      draftText: p.draft_text || (actionType === "reaction" ? `Reaction: ${p.reaction_type || "like"}` : ""),
      confidence: p.confidence ?? 0.85,
      reasoning: p.reasoning || "",
      engagementStyle: p.engagement_style || "Thought Leadership",
      createdAt: p.created_at || new Date().toISOString(),
      topic: "Engineering",
    };
  });
};

export interface ApprovalQueueViewProps {
  initialItems?: PendingItem[];
}

export const ApprovalQueueView: React.FC<ApprovalQueueViewProps> = ({
  initialItems,
}) => {
  const { setPendingCount, quota, nextScoutTime, autoRefreshInterval } = useApp();
  const [items, setItems] = useState<PendingItem[]>(() => initialItems ?? []);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => (initialItems ?? [])[0]?.id ?? null
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [activeRewriteTone, setActiveRewriteTone] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isShortcutsModalOpen, setIsShortcutsModalOpen] = useState<boolean>(false);
  const [, setCurrentToneIndex] = useState<number>(-1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const queueListRef = useRef<HTMLDivElement | null>(null);
  const toneIndexRef = useRef<number>(-1);
  const isRewritingRef = useRef<boolean>(false);
  const itemsRef = useRef<PendingItem[]>(items);
  itemsRef.current = items;

  useDeepNavigation(
    "queue",
    useCallback((target) => {
      if (target.itemId) {
        const cleanId = target.itemId.replace(/^queue-/, "");
        const matched = itemsRef.current.find(
          (i) => i.id === cleanId || i.id === target.itemId
        );
        if (matched) {
          setSelectedId(matched.id);
          setTimeout(() => {
            highlightAndScrollTo(`queue-item-${matched.id}`);
            highlightAndScrollTo(`pending-card-${matched.id}`);
            textareaRef.current?.focus();
          }, 120);
        }
      }
    }, [])
  );

  const loadQueue = useCallback(async () => {
    if (initialItems !== undefined) return;
    if (typeof window === "undefined" || !window.api?.fetchState) return;

    setIsLoading(true);
    setFetchError(null);
    try {
      const state = await window.api.fetchState();
      if (!state) return;
      const rawPending =
        state.pending_actions ||
        state.pendingActions ||
        state.pending ||
        [];

      const mapped = mapRawPending(rawPending);
      setItems(mapped);
      setSelectedId((prev) => (mapped.some((m) => m.id === prev) ? prev : mapped[0]?.id ?? null));
      setPendingCount(mapped.length);
    } catch (err) {
      setFetchError(
        err instanceof Error ? err.message : "Failed to load approval queue."
      );
    } finally {
      setIsLoading(false);
    }
  }, [initialItems, setPendingCount]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.api?.onRealtimeEvent) return;
    const unsubscribe = window.api.onRealtimeEvent((event: any) => {
      if (event?.type === "queue_updated" || event?.type === "action_executed") {
        if (event?.state) {
          const rawPending =
            event.state.pending_actions ||
            event.state.pendingActions ||
            event.state.pending ||
            [];
          const mapped = mapRawPending(rawPending);
          setItems(mapped);
          setSelectedId((prev) => (mapped.some((m) => m.id === prev) ? prev : mapped[0]?.id ?? null));
          setPendingCount(mapped.length);
        } else {
          loadQueue();
        }
      }
    });
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [loadQueue, setPendingCount]);

  const filteredItems = useMemo(() => {
    let result = items;
    if (filterType !== "all") {
      result = result.filter((i) => i.actionType === filterType);
    }
    if (!searchQuery.trim()) return result;
    const q = searchQuery.toLowerCase();
    return result.filter(
      (item) =>
        item.author.toLowerCase().includes(q) ||
        item.headline.toLowerCase().includes(q) ||
        item.topic.toLowerCase().includes(q) ||
        item.draftText.toLowerCase().includes(q)
    );
  }, [items, filterType, searchQuery]);

  const selectedItem = useMemo(() => {
    return items.find((i) => i.id === selectedId) ?? null;
  }, [items, selectedId]);

  const selectedItemRef = useRef<PendingItem | null>(null);
  selectedItemRef.current = selectedItem;

  const handleDraftChange = useCallback((newText: string) => {
    const current = selectedItemRef.current;
    if (!current) return;
    setItems((prev) =>
      prev.map((it) =>
        it.id === current.id ? { ...it, draftText: newText } : it
      )
    );
  }, []);

  const handleRewrite = useCallback(async (tone: string) => {
    const current = selectedItemRef.current;
    if (!current) return;
    if (isRewritingRef.current) return;
    isRewritingRef.current = true;

    const toneIdx = TONE_CYCLE.indexOf(tone);
    if (toneIdx !== -1) {
      toneIndexRef.current = toneIdx;
      setCurrentToneIndex(toneIdx);
    }
    setActiveRewriteTone(tone);
    setActionError(null);
    try {
      let rewritten: string;
      if (typeof window !== "undefined" && window.api?.rewriteDraft) {
        rewritten = await window.api.rewriteDraft(current.draftText, tone);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 50));
        rewritten = `${current.draftText} (${tone} tone update)`;
      }

      if (rewritten) {
        setItems((prev) =>
          prev.map((it) =>
            it.id === current.id ? { ...it, draftText: rewritten } : it
          )
        );
        setActionNotice(`Draft tone updated: ${tone}.`);
        setTimeout(() => setActionNotice(null), 3000);
      }
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to rewrite draft."
      );
    } finally {
      isRewritingRef.current = false;
      setActiveRewriteTone(null);
    }
  }, []);

  const handleCycleTone = useCallback(() => {
    if (!selectedItemRef.current || isProcessing) return;
    const nextIndex = (toneIndexRef.current + 1) % TONE_CYCLE.length;
    toneIndexRef.current = nextIndex;
    setCurrentToneIndex(nextIndex);
    handleRewrite(TONE_CYCLE[nextIndex]);
  }, [isProcessing, handleRewrite]);

  const handleReactionChange = useCallback((newReaction: string) => {
    const current = selectedItemRef.current;
    if (!current) return;
    setItems((prev) =>
      prev.map((item) =>
        item.id === current.id ? { ...item, reactionType: newReaction } : item
      )
    );
  }, []);

  const [isDraftingPostIdea, setIsDraftingPostIdea] = useState<boolean>(false);

  const handleDraftPostIdea = useCallback(async () => {
    if (isDraftingPostIdea) return;
    setIsDraftingPostIdea(true);
    setActionError(null);
    try {
      if (typeof window !== "undefined" && window.api?.triggerIdeate) {
        await window.api.triggerIdeate();
        setActionNotice("Post ideation triggered. Drafts will appear in queue shortly.");
      } else {
        setActionNotice("Post ideation triggered.");
      }
      setTimeout(() => setActionNotice(null), 4000);
      setTimeout(() => {
        loadQueue();
      }, 1500);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to trigger post ideation."
      );
    } finally {
      setIsDraftingPostIdea(false);
    }
  }, [isDraftingPostIdea, loadQueue]);

  const handleApprove = useCallback(async () => {
    const current = selectedItemRef.current;
    if (!current || isProcessing) return;
    setIsProcessing(true);
    setActionError(null);
    try {
      let result: { success: boolean; error?: string; message?: string };
      if (typeof window !== "undefined" && window.api?.executeAction) {
        const payloadText =
          current.actionType === "reaction" ? current.reactionType : current.draftText;
        result = await window.api.executeAction("approve", current.id, payloadText);
      } else {
        result = { success: true, message: `Approved ${current.id}` };
      }

      if (result.success !== false) {
        const removedId = current.id;
        const currentList = itemsRef.current;
        const currentIndex = currentList.findIndex((i) => i.id === removedId);
        const updated = currentList.filter((i) => i.id !== removedId);
        setItems(updated);
        setPendingCount(updated.length);
        setActionNotice(`Approved and queued action for ${current.author}.`);
        setTimeout(() => setActionNotice(null), 3000);

        if (updated.length > 0) {
          const nextIndex = Math.min(currentIndex, updated.length - 1);
          setSelectedId(updated[nextIndex].id);
        } else {
          setSelectedId(null);
        }
      } else {
        setActionError(result.error || "Approval dispatch failed.");
      }
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Approval dispatch failed."
      );
    } finally {
      setIsProcessing(false);
    }
  }, [isProcessing, setPendingCount]);

  const handleReject = useCallback(async () => {
    const current = selectedItemRef.current;
    if (!current || isProcessing) return;
    setIsProcessing(true);
    setActionError(null);
    try {
      let result: { success: boolean; error?: string; message?: string };
      if (typeof window !== "undefined" && window.api?.executeAction) {
        result = await window.api.executeAction("reject", current.id);
      } else {
        result = { success: true, message: `Rejected ${current.id}` };
      }

      if (result.success !== false) {
        const removedId = current.id;
        const currentList = itemsRef.current;
        const currentIndex = currentList.findIndex((i) => i.id === removedId);
        const updated = currentList.filter((i) => i.id !== removedId);
        setItems(updated);
        setPendingCount(updated.length);
        setActionNotice(`Rejected action for ${current.author}.`);
        setTimeout(() => setActionNotice(null), 3000);

        if (updated.length > 0) {
          const nextIndex = Math.min(currentIndex, updated.length - 1);
          setSelectedId(updated[nextIndex].id);
        } else {
          setSelectedId(null);
        }
      } else {
        setActionError(result.error || "Rejection dispatch failed.");
      }
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Rejection dispatch failed."
      );
    } finally {
      setIsProcessing(false);
    }
  }, [isProcessing, setPendingCount]);

  useQueueShortcuts({
    items: filteredItems,
    selectedId,
    onSelectId: (id) => setSelectedId(id),
    onApprove: handleApprove,
    onReject: handleReject,
    onCycleTone: handleCycleTone,
    onToggleShortcuts: () => setIsShortcutsModalOpen((prev) => !prev),
    onCloseShortcuts: () => setIsShortcutsModalOpen(false),
    isShortcutsOpen: isShortcutsModalOpen,
    textareaRef,
    queueListRef,
  });

  const commentsRemaining = Math.max(
    0,
    (quota?.commentsMax ?? 15) - (quota?.commentsExecuted ?? 0)
  );

  // Empty queue state
  if (items.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold tracking-tight text-on-surface">
                Approval Queue
              </h1>
              <span
                data-testid="pending-count-pill"
                className="font-sans text-[11px] text-on-surface-variant font-medium tabular-nums"
              >
                0 Pending
              </span>
            </div>
            <p className="mt-1 text-xs text-on-surface-variant">
              Human authorization boundary: Actions remain pending until explicitly approved or rejected.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="draft-post-idea-btn"
              onClick={handleDraftPostIdea}
              disabled={isDraftingPostIdea}
              className="flex items-center gap-1.5 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-50"
              title="Draft new post idea"
            >
              <Sparkle
                size={13}
                className={isDraftingPostIdea ? "animate-spin text-primary" : "text-primary"}
                weight="fill"
              />
              <span>{isDraftingPostIdea ? "Drafting..." : "Draft Post Idea"}</span>
            </button>

            <button
              type="button"
              data-testid="refresh-queue-btn"
              onClick={() => loadQueue()}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-50"
              title="Refresh approval queue"
            >
              <ArrowClockwise
                size={13}
                className={isLoading ? "animate-spin text-primary" : "text-on-surface-variant"}
              />
              <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
            </button>

            <button
              type="button"
              data-testid="shortcuts-help-btn"
              onClick={() => setIsShortcutsModalOpen(true)}
              className="flex items-center gap-1.5 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-high"
              title="Keyboard shortcuts cheat sheet (?)"
            >
              <Keyboard size={13} className="text-on-surface-variant" />
              <span>Shortcuts</span>
              <kbd className="rounded border border-outline bg-surface-container-highest px-1 py-0.2 font-sans text-[10px] text-on-surface-variant">
                ?
              </kbd>
            </button>
          </div>
        </div>

        {fetchError && (
          <div
            data-testid="queue-fetch-error"
            className="flex items-center gap-2 rounded-md border border-error/30 bg-error/10 p-3 text-xs text-error"
          >
            <WarningCircle size={15} className="shrink-0" />
            <span className="flex-1">{fetchError}</span>
            <button
              type="button"
              onClick={() => loadQueue()}
              className="font-medium underline hover:opacity-80"
            >
              Retry
            </button>
          </div>
        )}

        <div
          data-testid="empty-queue-state"
          className="flex flex-col items-center justify-center rounded-lg border border-outline/60 bg-surface-container-low p-12 text-center shadow-2xs"
        >
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-md border border-tertiary/30 bg-tertiary/10 text-tertiary">
            <Check size={20} weight="bold" />
          </div>
          <h3 className="text-sm font-semibold text-on-surface">
            All caught up. Zero pending approvals.
          </h3>
          <p className="mt-1 max-w-sm text-xs text-on-surface-variant leading-relaxed">
            All suggestions have been reviewed. Trigger a Scout cycle from Command Center to evaluate new feed posts.
          </p>
        </div>

        <KeyboardShortcutsModal
          isOpen={isShortcutsModalOpen}
          onClose={() => setIsShortcutsModalOpen(false)}
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-2.75rem)] -m-5 overflow-hidden bg-surface text-on-surface">
      {/* LEFT PANE: Triage Queue List (Things 3 / Apple Mail column) */}
      <QueueLeftPane
        items={items}
        filteredItems={filteredItems}
        selectedId={selectedId}
        onSelectId={(id) => setSelectedId(id)}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        filterType={filterType}
        onFilterChange={setFilterType}
        isLoading={isLoading}
        onRefresh={() => loadQueue()}
        onOpenShortcuts={() => setIsShortcutsModalOpen(true)}
        queueListRef={queueListRef}
        autoRefreshInterval={autoRefreshInterval}
        onDraftPostIdea={handleDraftPostIdea}
        isDraftingPostIdea={isDraftingPostIdea}
      />

      {/* RIGHT PANE: Reading & Approval Workspace (Detail Canvas) */}
      <main className="flex-1 flex flex-col bg-surface overflow-y-auto min-w-0">
        {selectedItem ? (
          <>
            {/* Top Header Bar */}
            <QueueWorkspaceHeader
              item={selectedItem}
              onApprove={handleApprove}
              onReject={handleReject}
              onRegenerate={() => handleRewrite("regenerate")}
              isProcessing={isProcessing}
              isRewriting={!!activeRewriteTone}
              actionNotice={actionNotice}
              actionError={actionError}
            />

            {/* Reading & Studio Content Area */}
            <div className="w-full max-w-[760px] mx-auto px-8 py-8 flex flex-col gap-8">
              {/* SECTION 1: Original LinkedIn Context */}
              <QueueTargetSection item={selectedItem} />

              {/* SECTION 2: Synthesis & Rationale */}
              <QueueRationaleSection item={selectedItem} />

              {/* SECTION 3: Proposed Response & Draft Editor */}
              <QueueDraftEditorSection
                draftText={selectedItem.draftText}
                onDraftChange={handleDraftChange}
                onRewrite={handleRewrite}
                activeRewriteTone={activeRewriteTone}
                onApprove={handleApprove}
                onReject={handleReject}
                onRegenerate={() => handleRewrite("regenerate")}
                isProcessing={isProcessing}
                textareaRef={textareaRef}
                initialDraftText={selectedItem.draftText}
                actionType={selectedItem.actionType}
                reactionType={selectedItem.reactionType}
                onReactionChange={handleReactionChange}
              />

              {/* SECTION 4: Safety & Edge Dispatch Guarantee footer */}
              <QueueSafetyFooter
                commentsRemaining={commentsRemaining}
                commentsMax={quota?.commentsMax ?? 15}
                nextScoutTime={nextScoutTime}
              />
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center p-12 text-center text-on-surface-variant">
            <p className="text-xs">
              Select an item from the pending queue to inspect details and edit drafts.
            </p>
          </div>
        )}
      </main>

      <KeyboardShortcutsModal
        isOpen={isShortcutsModalOpen}
        onClose={() => setIsShortcutsModalOpen(false)}
      />
    </div>
  );
};
