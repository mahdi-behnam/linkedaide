import React, { useState } from "react";
import { useApp } from "../context/AppContext";
import {
  Inbox,
  Check,
  X,
  ArrowSquareOut,
  CheckCircle,
} from "../components/icons";

interface PendingItem {
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
}

const initialPendingItems: PendingItem[] = [
  {
    id: "act-8f4b1e",
    actionType: "comment",
    author: "Satya Nadella",
    headline: "Chairman and CEO at Microsoft",
    postUrl: "https://linkedin.com/feed/update/urn:li:activity:7245890012",
    postExcerpt:
      "Autonomous AI systems in the enterprise require reliable verification architectures before scaling critical decision workflows.",
    draftText:
      "The compounding returns on autonomous verification pipelines highlight why deterministic guardrails matter more than raw model scale. Human-in-the-loop validation bridges the gap between probabilistic generation and mission-critical reliability.",
    confidence: 0.94,
    reasoning:
      "High-signal post directly aligned with enterprise AI reliability focus areas. Technical deep dive response recommended.",
    engagementStyle: "technical_deep_dive",
    createdAt: "15 minutes ago",
  },
  {
    id: "act-4c9a2d",
    actionType: "comment",
    author: "Harrison Chase",
    headline: "Co-Founder and CEO at LangChain",
    postUrl: "https://linkedin.com/feed/update/urn:li:activity:7245834921",
    postExcerpt:
      "Stateful agent workflows in production: why checkpoint persistence and deterministic graph transitions prevent cascading failure loops.",
    draftText:
      "Separating workflow orchestration state from transient LLM checkpoints is the key architectural leap. Combining Cloudflare KV edge stores with LangGraph guarantees zero-conflict deterministic recovery.",
    confidence: 0.91,
    reasoning:
      "Direct alignment with LangGraph orchestration principles and persistent state stores.",
    engagementStyle: "supportive_synthesis",
    createdAt: "35 minutes ago",
  },
  {
    id: "act-2e5f8b",
    actionType: "post",
    author: "Operator (Self)",
    headline: "Original HITL Agent Post",
    postUrl: "",
    postExcerpt: "Original Thought Leadership Draft",
    draftText:
      "Why human-in-the-loop is the prerequisite for enterprise agent deployment: an architectural deep-dive into determinism, state isolation, and zero-leak session vaults.",
    confidence: 0.88,
    reasoning:
      "Feed trends reflect high engagement on agent safety and human authorization architectures.",
    engagementStyle: "technical_deep_dive",
    createdAt: "1 hour ago",
  },
];

export const ApprovalQueueView: React.FC = () => {
  const { setPendingCount } = useApp();
  const [items, setItems] = useState<PendingItem[]>(initialPendingItems);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const handleDecision = (id: string, decision: "approved" | "rejected") => {
    setItems((prev) => {
      const updated = prev.filter((item) => item.id !== id);
      setPendingCount(updated.length);
      return updated;
    });
    setActionNotice(`Action ${id} ${decision}. Dispatching to Cloudflare Workers edge.`);
    setTimeout(() => setActionNotice(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Approval Queue
            </h1>
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 font-mono text-xs text-amber-300">
              {items.length} Pending Actions
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Human authorization boundary: Actions remain pending until explicitly approved or rejected.
          </p>
        </div>
      </div>

      {/* Action Notification */}
      {actionNotice && (
        <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-300">
          <CheckCircle size={14} className="text-emerald-400" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Pending Items List */}
      <div className="space-y-4">
        {items.map((item) => (
          <div
            key={item.id}
            data-testid={`pending-card-${item.id}`}
            className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 transition-colors hover:border-zinc-700/80"
          >
            {/* Top row */}
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-2.5">
                <span
                  className={`rounded px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${
                    item.actionType === "comment"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                  }`}
                >
                  {item.actionType}
                </span>
                <div>
                  <h3 className="text-xs font-semibold text-zinc-100">
                    {item.author}
                  </h3>
                  <p className="text-[11px] text-zinc-500">{item.headline}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-zinc-400">
                  {Math.round(item.confidence * 100)}% Confidence
                </span>
                <span className="font-mono text-[11px] text-zinc-500">
                  {item.createdAt}
                </span>
                {item.postUrl && (
                  <a
                    href={item.postUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-emerald-400 hover:underline"
                  >
                    <span>Target</span>
                    <ArrowSquareOut size={12} />
                  </a>
                )}
              </div>
            </div>

            {/* Target Post Excerpt */}
            {item.postExcerpt && (
              <div className="mt-3 rounded border border-zinc-800/60 bg-zinc-950/50 p-2.5 text-xs text-zinc-400">
                <span className="font-mono text-[10px] text-zinc-500 uppercase">
                  Target Excerpt:
                </span>
                <p className="mt-1 italic">"{item.postExcerpt}"</p>
              </div>
            )}

            {/* Drafted Text */}
            <div className="mt-3">
              <span className="font-mono text-[10px] text-zinc-500 uppercase">
                Generated Draft:
              </span>
              <div className="mt-1 rounded-md border border-zinc-800 bg-zinc-950 p-3 text-xs leading-relaxed text-zinc-200">
                {item.draftText}
              </div>
            </div>

            {/* Decision Actions Bar */}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2 font-mono text-[11px] text-zinc-500">
                <span>Style: {item.engagementStyle}</span>
                <span>•</span>
                <span>ID: {item.id}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  data-testid={`reject-btn-${item.id}`}
                  onClick={() => handleDecision(item.id, "rejected")}
                  className="flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300 active:translate-y-[1px] active:scale-[0.98]"
                >
                  <X size={13} weight="bold" />
                  <span>Reject</span>
                </button>
                <button
                  type="button"
                  data-testid={`approve-btn-${item.id}`}
                  onClick={() => handleDecision(item.id, "approved")}
                  className="flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-3.5 py-1.5 text-xs font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/25 active:translate-y-[1px] active:scale-[0.98]"
                >
                  <Check size={13} weight="bold" />
                  <span>Approve & Dispatch</span>
                </button>
              </div>
            </div>
          </div>
        ))}

        {items.length === 0 && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-12 text-center">
            <Inbox size={32} className="mx-auto text-zinc-600" />
            <h3 className="mt-3 text-sm font-semibold text-zinc-300">
              Approval Queue is Empty
            </h3>
            <p className="mt-1 text-xs text-zinc-500">
              All suggestions have been reviewed. Trigger a Scout run from the Dashboard to scan for new feed candidates.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
