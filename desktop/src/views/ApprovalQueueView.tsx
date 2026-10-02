import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";
import {
  Check,
  X,
  ArrowClockwise,
  MagicWand,
  ChatTeardropText,
  Sparkle,
  ArrowSquareOut,
  Quotes,
  MagnifyingGlass,
  CheckCircle,
  WarningCircle,
  Keyboard,
} from "@phosphor-icons/react";
import { useQueueShortcuts } from "../hooks/useQueueShortcuts";
import { KeyboardShortcutsModal } from "../components/KeyboardShortcutsModal";
import { VoiceDictationButton } from "../components/VoiceDictationButton";

export interface PendingItem {
  id: string;
  actionType: "comment" | "post";
  author: string;
  headline: string;
  postUrl: string;
  postExcerpt: string;
  draftText: string;
  confidence: number;
  reasoning: string;
  engagementStyle: string;
  createdAt: string;
  topic: string;
}

interface ToneOption {
  label: string;
  tone: string;
}

const TONE_OPTIONS: ToneOption[] = [
  { label: "More Technical", tone: "technical" },
  { label: "Inquisitive Question", tone: "inquisitive" },
  { label: "Contrarian", tone: "contrarian" },
  { label: "Shorter & Punchier", tone: "shorter" },
];

const TONE_CYCLE = ["technical", "inquisitive", "contrarian", "shorter"];

export interface ApprovalQueueViewProps {
  initialItems?: PendingItem[];
}

export const ApprovalQueueView: React.FC<ApprovalQueueViewProps> = ({
  initialItems,
}) => {
  const { setPendingCount } = useApp();
  const [items, setItems] = useState<PendingItem[]>(() => initialItems ?? []);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => (initialItems ?? [])[0]?.id ?? null
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeRewriteTone, setActiveRewriteTone] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isShortcutsModalOpen, setIsShortcutsModalOpen] = useState<boolean>(false);
  const [currentToneIndex, setCurrentToneIndex] = useState<number>(-1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const queueListRef = useRef<HTMLDivElement | null>(null);

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

      const mapped: PendingItem[] = rawPending.map((p: any) => ({
        id: p.item_id,
        actionType: (p.action_type?.includes("post") ? "post" : "comment") as "comment" | "post",
        author: p.author_name || "Unknown Author",
        headline: p.author_headline || "LinkedIn Member",
        postUrl: p.post_url || "",
        postExcerpt: p.post_excerpt || "",
        draftText: p.draft_text || "",
        confidence: p.confidence ?? 0.85,
        reasoning: p.reasoning || "",
        engagementStyle: p.engagement_style || "Thought Leadership",
        createdAt: p.created_at || new Date().toISOString(),
        topic: "Engineering",
      }));
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
        loadQueue();
      }
    });
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [loadQueue]);

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(
      (item) =>
        item.author.toLowerCase().includes(q) ||
        item.headline.toLowerCase().includes(q) ||
        item.topic.toLowerCase().includes(q) ||
        item.draftText.toLowerCase().includes(q)
    );
  }, [items, searchQuery]);

  const selectedItem = useMemo(() => {
    return items.find((i) => i.id === selectedId) ?? null;
  }, [items, selectedId]);

  const handleDraftChange = (newText: string) => {
    if (!selectedItem) return;
    setItems((prev) =>
      prev.map((it) =>
        it.id === selectedItem.id ? { ...it, draftText: newText } : it
      )
    );
  };

  const handleRewrite = async (tone: string) => {
    if (!selectedItem || activeRewriteTone) return;
    const toneIdx = TONE_CYCLE.indexOf(tone);
    if (toneIdx !== -1) {
      setCurrentToneIndex(toneIdx);
    }
    setActiveRewriteTone(tone);
    setActionError(null);
    try {
      let rewritten: string;
      if (typeof window !== "undefined" && window.api?.rewriteDraft) {
        rewritten = await window.api.rewriteDraft(selectedItem.draftText, tone);
      } else {
        await new Promise((resolve) => setTimeout(resolve, 100));
        rewritten = `${selectedItem.draftText} (${tone} tone update)`;
      }

      if (rewritten) {
        setItems((prev) =>
          prev.map((it) =>
            it.id === selectedItem.id ? { ...it, draftText: rewritten } : it
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
      setActiveRewriteTone(null);
    }
  };

  const handleApprove = async () => {
    if (!selectedItem || isProcessing) return;
    setIsProcessing(true);
    setActionError(null);
    try {
      let result: { success: boolean; error?: string; message?: string };
      if (typeof window !== "undefined" && window.api?.executeAction) {
        result = await window.api.executeAction("approve", selectedItem.id);
      } else {
        result = { success: true, message: `Approved ${selectedItem.id}` };
      }

      if (result.success !== false) {
        const removedId = selectedItem.id;
        const currentIndex = items.findIndex((i) => i.id === removedId);
        const updated = items.filter((i) => i.id !== removedId);
        setItems(updated);
        setPendingCount(updated.length);
        setActionNotice(`Approved and queued action for ${selectedItem.author}.`);
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
  };

  const handleReject = async () => {
    if (!selectedItem || isProcessing) return;
    setIsProcessing(true);
    setActionError(null);
    try {
      let result: { success: boolean; error?: string; message?: string };
      if (typeof window !== "undefined" && window.api?.executeAction) {
        result = await window.api.executeAction("reject", selectedItem.id);
      } else {
        result = { success: true, message: `Rejected ${selectedItem.id}` };
      }

      if (result.success !== false) {
        const removedId = selectedItem.id;
        const currentIndex = items.findIndex((i) => i.id === removedId);
        const updated = items.filter((i) => i.id !== removedId);
        setItems(updated);
        setPendingCount(updated.length);
        setActionNotice(`Rejected action for ${selectedItem.author}.`);
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
  };

  const handleCycleTone = () => {
    if (!selectedItem || activeRewriteTone || isProcessing) return;
    const nextIndex = (currentToneIndex + 1) % TONE_CYCLE.length;
    setCurrentToneIndex(nextIndex);
    handleRewrite(TONE_CYCLE[nextIndex]);
  };

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

  // Draft metrics for LinkedIn sweet-spot
  const currentText = selectedItem?.draftText ?? "";
  const charCount = currentText.length;
  const wordCount = currentText.trim()
    ? currentText.trim().split(/\s+/).length
    : 0;
  const isSweetSpot =
    charCount >= 150 && charCount <= 350 && wordCount >= 25 && wordCount <= 60;

  if (items.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
                Approval Queue
              </h1>
              <span className="rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-0.5 font-mono text-xs text-zinc-400">
                0 Pending
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-400">
              Human authorization boundary: Actions remain pending until explicitly approved or rejected.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="refresh-queue-btn"
              onClick={() => loadQueue()}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-2.5 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
              title="Refresh approval queue"
            >
              <ArrowClockwise
                size={14}
                className={isLoading ? "animate-spin text-zinc-300" : "text-zinc-400"}
              />
              <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
            </button>

            <button
              type="button"
              data-testid="shortcuts-help-btn"
              onClick={() => setIsShortcutsModalOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-2.5 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200"
              title="Keyboard shortcuts cheat sheet (?)"
            >
              <Keyboard size={14} className="text-zinc-400" />
              <span>Shortcuts</span>
              <kbd className="rounded border border-zinc-700/60 bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                ?
              </kbd>
            </button>
          </div>
        </div>

        {fetchError && (
          <div
            data-testid="queue-fetch-error"
            className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300"
          >
            <WarningCircle size={16} className="shrink-0 text-rose-400" />
            <span className="flex-1">{fetchError}</span>
            <button
              type="button"
              onClick={() => loadQueue()}
              className="font-medium underline hover:text-rose-100"
            >
              Retry
            </button>
          </div>
        )}

        <div
          data-testid="empty-queue-state"
          className="flex flex-col items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 p-16 text-center"
        >
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
            <Check size={24} weight="bold" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-100">
            All caught up. Zero pending approvals.
          </h3>
          <p className="mt-1 max-w-sm text-xs text-zinc-400">
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
    <div className="space-y-4">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Approval Queue
            </h1>
            <span
              data-testid="pending-count-pill"
              className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 font-mono text-xs text-amber-300"
            >
              {items.length} Pending
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Human authorization boundary: Review, refine tone, and queue verified actions for edge dispatch.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {actionNotice && (
            <div
              data-testid="action-notice"
              className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-1.5 text-xs text-emerald-300"
            >
              <CheckCircle size={14} className="text-emerald-400" />
              <span>{actionNotice}</span>
            </div>
          )}

          {actionError && (
            <div
              data-testid="action-error"
              className="flex items-center gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs text-rose-300"
            >
              <WarningCircle size={14} className="text-rose-400" />
              <span>{actionError}</span>
            </div>
          )}

          <button
            type="button"
            data-testid="refresh-queue-btn"
            onClick={() => loadQueue()}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-2.5 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
            title="Refresh approval queue"
          >
            <ArrowClockwise
              size={14}
              className={isLoading ? "animate-spin text-zinc-300" : "text-zinc-400"}
            />
            <span>{isLoading ? "Refreshing..." : "Refresh"}</span>
          </button>

          <button
            type="button"
            data-testid="shortcuts-help-btn"
            onClick={() => setIsShortcutsModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 px-2.5 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200"
            title="Keyboard shortcuts cheat sheet (?)"
          >
            <Keyboard size={14} className="text-zinc-400" />
            <span>Shortcuts</span>
            <kbd className="rounded border border-zinc-700/60 bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
              ?
            </kbd>
          </button>
        </div>
      </div>

      {fetchError && (
        <div
          data-testid="queue-fetch-error"
          className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300"
        >
          <WarningCircle size={16} className="shrink-0 text-rose-400" />
          <span className="flex-1">{fetchError}</span>
          <button
            type="button"
            onClick={() => loadQueue()}
            className="font-medium underline hover:text-rose-100"
          >
            Retry
          </button>
        </div>
      )}

      {/* 2-Column Cockpit Layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
        {/* Left Column: Queue List (5 cols) */}
        <div className="space-y-3 lg:col-span-5">
          {/* List Header and Search Filter */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
            <div className="flex items-center justify-between pb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Pending Actions ({filteredItems.length})
              </span>
              <span className="font-mono text-[11px] text-zinc-500">
                Sorted by priority
              </span>
            </div>
            <div className="relative">
              <MagnifyingGlass
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
              />
              <input
                type="text"
                data-testid="queue-search-input"
                placeholder="Search by author, headline, topic..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 py-1.5 pl-8 pr-3 text-xs text-zinc-200 placeholder-zinc-500 transition-colors focus:border-zinc-700 focus:outline-none"
              />
            </div>
          </div>

          {/* Cards List */}
          <div
            ref={queueListRef}
            tabIndex={-1}
            className="space-y-2.5 max-h-[calc(100vh-230px)] overflow-y-auto pr-0.5 outline-none"
          >
            {filteredItems.map((item) => {
              const isSelected = item.id === selectedId;
              return (
                <div
                  key={item.id}
                  data-testid={`pending-card-${item.id}`}
                  onClick={() => setSelectedId(item.id)}
                  className={`cursor-pointer rounded-lg border p-3.5 transition-all text-left ${
                    isSelected
                      ? "bg-zinc-800/50 border-emerald-500/50 ring-1 ring-emerald-500/20"
                      : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700/80 hover:bg-zinc-800/30"
                  }`}
                >
                  {/* Card Badges Row */}
                  <div className="flex flex-wrap items-center justify-between gap-1.5 pb-2">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${
                          item.actionType === "comment"
                            ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                            : "border border-violet-500/20 bg-violet-500/10 text-violet-400"
                        }`}
                      >
                        {item.actionType}
                      </span>
                      <span className="rounded border border-zinc-700/50 bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                        {item.topic}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
                        {Math.round(item.confidence * 100)}% Match
                      </span>
                      <span className="font-mono text-[11px] text-zinc-500">
                        {item.createdAt}
                      </span>
                    </div>
                  </div>

                  {/* Author Info */}
                  <div>
                    <h3 className="text-xs font-semibold text-zinc-100">
                      {item.author}
                    </h3>
                    <p className="text-[11px] text-zinc-400 line-clamp-1">
                      {item.headline}
                    </p>
                  </div>

                  {/* Draft preview snippet */}
                  <p className="mt-2 line-clamp-2 text-xs text-zinc-400 leading-relaxed">
                    {item.draftText}
                  </p>
                </div>
              );
            })}

            {filteredItems.length === 0 && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-8 text-center">
                <p className="text-xs text-zinc-400">
                  No pending actions match your search query.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Inspector & Studio (7 cols) */}
        <div className="space-y-4 lg:col-span-7">
          {selectedItem ? (
            <>
              {/* Target Post Excerpt */}
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 text-xs text-zinc-400">
                  <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                    <Quotes size={15} className="text-emerald-400" />
                    <span>Target Post Excerpt</span>
                  </div>
                  {selectedItem.postUrl && (
                    <a
                      href={selectedItem.postUrl}
                      target="_blank"
                      rel="noreferrer"
                      data-testid="target-post-link"
                      className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 hover:underline"
                    >
                      <span>View on LinkedIn</span>
                      <ArrowSquareOut size={13} />
                    </a>
                  )}
                </div>

                <blockquote
                  data-testid="target-excerpt"
                  className="mt-2.5 border-l-2 border-emerald-500/40 pl-3 text-xs italic leading-relaxed text-zinc-300"
                >
                  "{selectedItem.postExcerpt}"
                </blockquote>

                <div className="mt-2 text-right text-[11px] text-zinc-500">
                  : {selectedItem.author}, {selectedItem.headline}
                </div>
              </div>

              {/* LLM Triage Reasoning */}
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 text-xs">
                  <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                    <Sparkle size={15} className="text-amber-400" />
                    <span>LLM Triage Reasoning</span>
                  </div>
                  <span className="font-mono text-[11px] text-emerald-400">
                    {Math.round(selectedItem.confidence * 100)}% Confidence
                  </span>
                </div>

                <div className="mt-2.5 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="font-mono text-[10px] uppercase text-zinc-500">
                      Recommendation Style
                    </span>
                    <p className="font-medium text-zinc-200 capitalize">
                      {selectedItem.engagementStyle.replace(/_/g, " ")}
                    </p>
                  </div>
                  <div>
                    <span className="font-mono text-[10px] uppercase text-zinc-500">
                      Topic Alignment
                    </span>
                    <p className="font-medium text-zinc-200">
                      {selectedItem.topic}
                    </p>
                  </div>
                </div>

                <div className="mt-2.5 border-t border-zinc-800/60 pt-2">
                  <span className="font-mono text-[10px] uppercase text-zinc-500">
                    Rationale Breakdown
                  </span>
                  <p
                    data-testid="triage-rationale"
                    className="mt-0.5 text-xs leading-relaxed text-zinc-400"
                  >
                    {selectedItem.reasoning}
                  </p>
                </div>
              </div>

              {/* Comment Draft Editor Studio */}
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200">
                    <ChatTeardropText size={15} className="text-emerald-400" />
                    <span>Comment Draft Editor</span>
                  </div>

                  {/* Real-time Character and Word Counter with Sweet-spot Badge */}
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span
                      data-testid="char-word-counter"
                      className="text-zinc-400 text-[11px]"
                    >
                      {charCount} chars · {wordCount} words
                    </span>
                    {isSweetSpot ? (
                      <span
                        data-testid="sweet-spot-badge"
                        className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400"
                      >
                        <Check size={11} weight="bold" />
                        Sweet Spot
                      </span>
                    ) : (
                      <span
                        data-testid="length-indicator"
                        className="rounded-full border border-zinc-800 bg-zinc-950 px-2 py-0.5 text-[10px] text-zinc-500"
                      >
                        {charCount < 150 ? "Target: 150-350 chars" : "Long (> 350)"}
                      </span>
                    )}
                  </div>
                </div>

                {/* Textarea */}
                <div className="mt-3">
                  <textarea
                    ref={textareaRef}
                    data-testid="draft-editor-textarea"
                    aria-label="Comment Draft Editor"
                    value={selectedItem.draftText}
                    onChange={(e) => handleDraftChange(e.target.value)}
                    rows={5}
                    className="w-full resize-y rounded-lg border border-zinc-800 bg-zinc-950/80 p-3 font-sans text-xs leading-relaxed text-zinc-100 placeholder-zinc-600 transition-colors focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/20"
                    placeholder="Enter or refine your LinkedIn draft response..."
                  />
                </div>

                {/* Tone Quick-Pills Bar */}
                <div className="mt-3 rounded-md border border-zinc-800/80 bg-zinc-950/50 p-2.5">
                  <div className="flex items-center justify-between pb-2">
                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-zinc-400">
                      <MagicWand size={13} className="text-amber-400" />
                      <span>AI Tone Quick-Pills</span>
                      <kbd className="ml-1 rounded border border-zinc-700/50 bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
                        T
                      </kbd>
                    </div>
                    <span className="font-mono text-[10px] text-zinc-500">
                      Press T to cycle
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {TONE_OPTIONS.map((opt) => {
                      const isRewritingThis = activeRewriteTone === opt.tone;
                      return (
                        <button
                          key={opt.tone}
                          type="button"
                          data-testid={`tone-pill-${opt.tone}`}
                          disabled={!!activeRewriteTone || isProcessing}
                          onClick={() => handleRewrite(opt.tone)}
                          className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-xs text-zinc-300 transition-all hover:border-zinc-700 hover:bg-zinc-800 active:scale-[0.98] active:translate-y-[1px] disabled:opacity-50"
                        >
                          {isRewritingThis ? (
                            <ArrowClockwise
                              size={12}
                              className="animate-spin text-emerald-400"
                            />
                          ) : (
                            <Sparkle size={12} className="text-zinc-500" />
                          )}
                          <span>{opt.label}</span>
                        </button>
                      );
                    })}
                    <div className="mx-0.5 h-4 w-px bg-zinc-800" />
                    <VoiceDictationButton
                      onTranscript={(text) => {
                        if (selectedItem) {
                          handleDraftChange(
                            selectedItem.draftText
                              ? `${selectedItem.draftText} ${text}`
                              : text
                          );
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Action Buttons Bar */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800/80 pt-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      data-testid="regenerate-action-btn"
                      disabled={isProcessing || !!activeRewriteTone}
                      onClick={() => handleRewrite("regenerate")}
                      className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-all hover:bg-zinc-800/60 active:scale-[0.98] active:translate-y-[1px] disabled:opacity-50"
                    >
                      <ArrowClockwise
                        size={13}
                        className={
                          activeRewriteTone === "regenerate"
                            ? "animate-spin text-emerald-400"
                            : ""
                        }
                      />
                      <span>Regenerate</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      data-testid="reject-action-btn"
                      disabled={isProcessing || !!activeRewriteTone}
                      onClick={handleReject}
                      className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs font-medium text-rose-300 transition-all hover:bg-rose-500/20 active:scale-[0.98] active:translate-y-[1px] disabled:opacity-50"
                    >
                      <X size={13} weight="bold" />
                      <span>Reject</span>
                      <kbd className="ml-1 rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 font-mono text-[10px] text-rose-300">
                        R
                      </kbd>
                    </button>

                    <button
                      type="button"
                      data-testid="approve-action-btn"
                      disabled={isProcessing || !!activeRewriteTone}
                      onClick={handleApprove}
                      className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-zinc-950 transition-all hover:bg-emerald-500 active:scale-[0.98] active:translate-y-[1px] disabled:opacity-50"
                    >
                      <Check size={13} weight="bold" />
                      <span>Approve & Queue</span>
                      <kbd className="ml-1 rounded border border-emerald-700/40 bg-emerald-700/30 px-1.5 py-0.5 font-mono text-[10px] text-zinc-900">
                        A
                      </kbd>
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-12 text-center">
              <p className="text-xs text-zinc-400">
                Select an item from the pending queue to inspect details and edit drafts.
              </p>
            </div>
          )}
        </div>
      </div>

      <KeyboardShortcutsModal
        isOpen={isShortcutsModalOpen}
        onClose={() => setIsShortcutsModalOpen(false)}
      />
    </div>
  );
};
