import React, { useState, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { ConnectionRequestAction } from "../types";
import {
  UserPlus,
  Check,
  X,
  Sparkle,
  ArrowSquareOut,
  ChatText,
  ShieldCheck,
} from "@phosphor-icons/react";

export interface OutreachQueueViewProps {
  initialItems?: ConnectionRequestAction[];
}

type ToneType = "casual" | "technical" | "concise";

export const OutreachQueueView: React.FC<OutreachQueueViewProps> = ({ initialItems }) => {
  const {
    connectionQueue: contextQueue,
    executeConnectionAction,
    quota,
  } = useApp();

  const [items, setItems] = useState<ConnectionRequestAction[]>(
    () => initialItems || contextQueue || []
  );

  const [selectedId, setSelectedId] = useState<string>(() => {
    const list = initialItems || contextQueue || [];
    return list.length > 0 ? list[0].id : "";
  });

  const selectedCandidate = useMemo(() => {
    return items.find((item) => item.id === selectedId) || items[0] || null;
  }, [items, selectedId]);

  const [notes, setNotes] = useState<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    const list = initialItems || contextQueue || [];
    for (const item of list) {
      map[item.id] = item.note_text || "";
    }
    return map;
  });

  const currentNote = selectedCandidate ? (notes[selectedCandidate.id] ?? selectedCandidate.note_text ?? "") : "";
  const charCount = currentNote.length;
  const isOverLimit = charCount > 300;
  const isWarning = charCount > 280 && charCount <= 300;

  const handleNoteChange = (text: string) => {
    if (!selectedCandidate) return;
    setNotes((prev) => ({
      ...prev,
      [selectedCandidate.id]: text,
    }));
  };

  const handleToneSelect = async (tone: ToneType) => {
    if (!selectedCandidate) return;
    const name = selectedCandidate.target_name.split(" ")[0] || "there";
    const context = selectedCandidate.mutual_context || "your recent post";

    let rewritten = "";
    if (tone === "casual") {
      rewritten = `Hey ${name}, loved your recent insights on ${context.toLowerCase().replace(/^commented on /i, "")}. Would be great to connect and stay in touch!`;
    } else if (tone === "technical") {
      rewritten = `Hi ${name}, great discussion regarding ${context.toLowerCase().replace(/^commented on /i, "")}. We are exploring similar architecture tradeoffs and I would value connecting.`;
    } else if (tone === "concise") {
      rewritten = `Hi ${name}, following your work on distributed systems. Would love to connect here on LinkedIn.`;
    }

    if (typeof window !== "undefined" && window.api?.rewriteDraft) {
      try {
        const apiRewritten = await window.api.rewriteDraft(currentNote || rewritten, tone);
        if (apiRewritten && apiRewritten.trim()) {
          rewritten = apiRewritten;
        }
      } catch {
        // Fallback to local tone template
      }
    }

    if (rewritten.length > 300) {
      rewritten = rewritten.slice(0, 300);
    }
    handleNoteChange(rewritten);
  };

  const [isProcessing, setIsProcessing] = useState(false);

  const handleApprove = async () => {
    if (!selectedCandidate || isOverLimit || isProcessing) return;
    setIsProcessing(true);
    try {
      const noteToSend = notes[selectedCandidate.id] ?? selectedCandidate.note_text ?? "";
      await executeConnectionAction("approve", selectedCandidate.id, noteToSend);
      setItems((prev) =>
        prev.map((c) =>
          c.id === selectedCandidate.id
            ? { ...c, status: "approved", note_text: noteToSend, approved_at: new Date().toISOString() }
            : c
        )
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!selectedCandidate || isProcessing) return;
    setIsProcessing(true);
    try {
      await executeConnectionAction("reject", selectedCandidate.id);
      setItems((prev) =>
        prev.map((c) =>
          c.id === selectedCandidate.id
            ? { ...c, status: "rejected" }
            : c
        )
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const pendingCount = items.filter((c) => c.status === "pending").length;
  const connectionsSent = quota?.connectionsSent ?? 2;
  const connectionsMax = quota?.connectionsMax ?? 10;
  const quotaPercent = Math.min(100, Math.round((connectionsSent / connectionsMax) * 100));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Header bar */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800/80 px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
            <UserPlus size={20} weight="bold" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold text-zinc-100">Outreach Queue</h1>
              <span
                data-testid="pending-count-pill"
                className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400"
              >
                {pendingCount} Pending
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Human-in-the-loop connection request review and 300-character personalized note studio
            </p>
          </div>
        </div>

        {/* Daily Connection Cap Quota Badge */}
        <div
          data-testid="connection-quota-badge"
          className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3.5 py-1.5"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-md border border-zinc-700/60 bg-zinc-800/80 text-emerald-400">
            <ShieldCheck size={16} weight="bold" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center justify-between gap-4 text-[11px]">
              <span className="font-medium text-zinc-300">Daily Cap Quota</span>
              <span className="font-mono font-semibold text-emerald-400">
                {connectionsSent} / {connectionsMax}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-28 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${quotaPercent}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 2-Column Cockpit Layout */}
      <div className="grid flex-1 grid-cols-12 overflow-hidden">
        {/* Left Column: Candidate List */}
        <div className="col-span-5 flex flex-col border-r border-zinc-800/80 bg-zinc-900/30">
          <div className="border-b border-zinc-800/80 px-4 py-3">
            <span className="text-xs font-medium tracking-wider text-zinc-400 uppercase">
              Connection Candidates ({items.length})
            </span>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto p-4">
            {items.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 text-center">
                <UserPlus size={28} className="text-zinc-600" />
                <p className="mt-2 text-sm text-zinc-400">No connection candidates queued</p>
                <p className="text-xs text-zinc-600">Feed scout runs will surface high-signal contacts</p>
              </div>
            ) : (
              items.map((candidate) => {
                const isSelected = selectedCandidate?.id === candidate.id;
                const statusColors = {
                  pending: "border-amber-500/30 bg-amber-500/10 text-amber-400",
                  approved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
                  rejected: "border-zinc-700 bg-zinc-800 text-zinc-400",
                  sent: "border-cyan-500/30 bg-cyan-500/10 text-cyan-400",
                  failed: "border-rose-500/30 bg-rose-500/10 text-rose-400",
                };

                return (
                  <div
                    key={candidate.id}
                    data-testid={`candidate-card-${candidate.id}`}
                    onClick={() => setSelectedId(candidate.id)}
                    className={`cursor-pointer rounded-lg border p-3.5 transition-all duration-150 ${
                      isSelected
                        ? "border-emerald-500/50 bg-zinc-900/90 shadow-sm shadow-emerald-950/20"
                        : "border-zinc-800/80 bg-zinc-900/40 hover:border-zinc-700 hover:bg-zinc-900/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-zinc-700 bg-zinc-800 text-xs font-semibold text-zinc-200">
                          {candidate.target_name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <h3 className="text-sm font-medium text-zinc-100">{candidate.target_name}</h3>
                          <p className="text-xs text-zinc-400 line-clamp-1">{candidate.target_headline}</p>
                        </div>
                      </div>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase ${
                          statusColors[candidate.status] || statusColors.pending
                        }`}
                      >
                        {candidate.status}
                      </span>
                    </div>

                    {candidate.mutual_context && (
                      <div className="mt-2.5 flex items-center gap-1.5 rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[11px] text-emerald-400">
                        <ChatText size={13} weight="bold" className="shrink-0" />
                        <span className="line-clamp-1">{candidate.mutual_context}</span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Candidate Inspector & Note Studio */}
        <div className="col-span-7 flex flex-col overflow-y-auto bg-zinc-950/40 p-6">
          {selectedCandidate ? (
            <div className="flex flex-col space-y-5">
              {/* Profile Overview Card */}
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3.5">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full border border-zinc-700 bg-zinc-800 text-sm font-bold text-zinc-100">
                      {selectedCandidate.target_name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-zinc-100">
                        {selectedCandidate.target_name}
                      </h2>
                      <p className="text-xs text-zinc-400">{selectedCandidate.target_headline}</p>
                    </div>
                  </div>

                  <a
                    href={selectedCandidate.profile_url}
                    target="_blank"
                    rel="noreferrer"
                    data-testid="profile-link"
                    className="flex items-center gap-1.5 rounded-lg border border-zinc-700/80 bg-zinc-800/80 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-600 hover:bg-zinc-700 hover:text-white"
                  >
                    <span>View Profile</span>
                    <ArrowSquareOut size={14} />
                  </a>
                </div>

                {/* Mutual Interaction Citation Blockquote */}
                {selectedCandidate.mutual_context && (
                  <div className="mt-4 rounded-lg border border-zinc-800/90 bg-zinc-950/60 p-3.5">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
                      <Sparkle size={14} weight="fill" />
                      <span>Mutual Interaction Context</span>
                    </div>
                    <blockquote
                      data-testid="mutual-context-quote"
                      className="mt-1.5 border-l-2 border-emerald-500/50 pl-3 text-xs leading-relaxed text-zinc-300 italic"
                    >
                      {selectedCandidate.mutual_context}
                    </blockquote>
                  </div>
                )}
              </div>

              {/* 300-Character Note Studio */}
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ChatText size={18} className="text-emerald-400" />
                    <h3 className="text-sm font-semibold text-zinc-100">Personalized Note Studio</h3>
                  </div>

                  {/* Character countdown pill */}
                  <div
                    data-testid="char-count-pill"
                    className={`rounded-full border px-2.5 py-0.5 font-mono text-xs ${
                      isOverLimit
                        ? "border-rose-500/40 bg-rose-500/10 font-bold text-rose-400"
                        : isWarning
                        ? "border-amber-500/40 bg-amber-500/10 font-semibold text-amber-400"
                        : "border-zinc-700 bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {charCount} / 300 chars
                  </div>
                </div>

                {/* Character Progress Bar */}
                <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    data-testid="char-progress-bar"
                    className={`h-full rounded-full transition-all duration-150 ${
                      isOverLimit
                        ? "bg-rose-500"
                        : isWarning
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.min(100, (charCount / 300) * 100)}%` }}
                  />
                </div>

                {/* Tone Quick-Pills */}
                <div className="mt-3.5 flex items-center gap-2">
                  <span className="text-xs text-zinc-500">Tone Quick-Pills:</span>
                  <button
                    type="button"
                    data-testid="tone-pill-casual"
                    onClick={() => handleToneSelect("casual")}
                    className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-800/80 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-300 active:scale-[0.98]"
                  >
                    <Sparkle size={12} />
                    <span>Casual</span>
                  </button>
                  <button
                    type="button"
                    data-testid="tone-pill-technical"
                    onClick={() => handleToneSelect("technical")}
                    className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-800/80 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-300 active:scale-[0.98]"
                  >
                    <Sparkle size={12} />
                    <span>Technical</span>
                  </button>
                  <button
                    type="button"
                    data-testid="tone-pill-concise"
                    onClick={() => handleToneSelect("concise")}
                    className="flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-800/80 px-2.5 py-1 text-xs text-zinc-300 transition hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-300 active:scale-[0.98]"
                  >
                    <Sparkle size={12} />
                    <span>Concise</span>
                  </button>
                </div>

                {/* Large Styled Textarea */}
                <div className="mt-3">
                  <textarea
                    data-testid="note-editor-textarea"
                    rows={4}
                    value={currentNote}
                    onChange={(e) => handleNoteChange(e.target.value)}
                    placeholder="Add a personalized note to accompany your connection request (max 300 chars)..."
                    className={`w-full rounded-lg border bg-zinc-950/80 p-3 text-sm leading-relaxed text-zinc-100 placeholder-zinc-500 transition focus:outline-none focus:ring-1 ${
                      isOverLimit
                        ? "border-rose-500/60 focus:border-rose-500 focus:ring-rose-500/30"
                        : "border-zinc-800 focus:border-emerald-500/60 focus:ring-emerald-500/30"
                    }`}
                  />
                </div>

                {isOverLimit && (
                  <p
                    data-testid="limit-warning-text"
                    className="mt-1 text-xs font-medium text-rose-400"
                  >
                    Note exceeds the strict 300 character limit by {charCount - 300} characters. Please shorten it before sending.
                  </p>
                )}
                {isWarning && (
                  <p
                    data-testid="approaching-warning-text"
                    className="mt-1 text-xs font-medium text-amber-400"
                  >
                    Approaching 300 character limit ({300 - charCount} characters remaining).
                  </p>
                )}

                {/* Action Buttons */}
                <div className="mt-5 flex items-center justify-end gap-3 border-t border-zinc-800/80 pt-4">
                  <button
                    type="button"
                    data-testid="reject-button"
                    onClick={handleReject}
                    disabled={isProcessing || selectedCandidate.status === "rejected"}
                    className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-medium text-rose-400 transition hover:border-rose-800 hover:bg-rose-950/30 hover:text-rose-300 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <X size={15} weight="bold" />
                    <span>Reject</span>
                  </button>

                  <button
                    type="button"
                    data-testid="approve-button"
                    onClick={handleApprove}
                    disabled={
                      isProcessing ||
                      isOverLimit ||
                      selectedCandidate.status === "approved" ||
                      selectedCandidate.status === "sent"
                    }
                    className="flex items-center gap-1.5 rounded-lg border border-emerald-500/50 bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-950/40 transition hover:bg-emerald-500 active:scale-[0.98] disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-800 disabled:text-zinc-500 disabled:shadow-none"
                  >
                    <Check size={15} weight="bold" />
                    <span>
                      {selectedCandidate.status === "approved"
                        ? "Approved"
                        : "Approve & Send Invitation"}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-center text-zinc-500">
              <UserPlus size={36} className="text-zinc-700" />
              <p className="mt-2 text-sm">Select a candidate on the left to inspect details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
