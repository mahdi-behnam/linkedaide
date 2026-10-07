import React from "react";
import {
  Inbox,
  CaretRight,
  CheckCircle,
  Check,
  PencilSimple,
} from "../icons";
import { formatKeyCombo } from "../../utils/platform";

export interface PreviewPendingItem {
  id: string;
  author: string;
  initials: string;
  avatarBg: string;
  avatarText: string;
  headline: string;
  verified?: boolean;
  type: "Comment" | "Original Post";
  typeBg?: string;
  confidence: string;
  timeAgo: string;
  quote?: string;
  draft: string;
  primaryAction: string;
  secondaryAction: string;
}

const DEFAULT_PREVIEW_ITEMS: PreviewPendingItem[] = [
  {
    id: "sn-1",
    author: "Satya Nadella",
    initials: "SN",
    avatarBg: "bg-secondary/15",
    avatarText: "text-secondary",
    headline: "Chairman & CEO at Microsoft",
    verified: true,
    type: "Comment",
    confidence: "94% Confidence",
    timeAgo: "15m ago",
    quote: "“Autonomous AI systems in the enterprise require reliable verification architectures...”",
    draft: "The compounding returns on autonomous verification pipelines highlight why deterministic guardrails matter more than raw model scale...",
    primaryAction: "Approve",
    secondaryAction: "Reject",
  },
  {
    id: "hc-2",
    author: "Harrison Chase",
    initials: "HC",
    avatarBg: "bg-surface-container-high",
    avatarText: "text-on-surface-variant",
    headline: "Co-founder & CEO at LangChain",
    verified: false,
    type: "Comment",
    confidence: "91% Confidence",
    timeAgo: "35m ago",
    quote: "“Separating workflow orchestration state from transient LLM checkpoints is the key architectural leap...”",
    draft: "Stateful graphs prevent hallucinated cascading failures across tool-use agents by keeping state transitions reproducible...",
    primaryAction: "Approve",
    secondaryAction: "Reject",
  },
  {
    id: "op-3",
    author: "Operator (Self)",
    initials: "OP",
    avatarBg: "bg-primary/15",
    avatarText: "text-primary",
    headline: "Original Thought Leadership Post",
    verified: false,
    type: "Original Post",
    confidence: "88% Match",
    timeAgo: "1h ago",
    draft: "Why human-in-the-loop is the prerequisite for enterprise agent deployment: an architectural deep-dive into safe asynchronous queues...",
    primaryAction: "Edit Draft",
    secondaryAction: "Dismiss",
  },
];

export interface PendingApprovalQueuePreviewProps {
  pendingCount: number;
  onOpenQueue: () => void;
  onActionClick?: (action: string, itemId: string) => void;
  items?: PreviewPendingItem[];
}

export const PendingApprovalQueuePreview: React.FC<PendingApprovalQueuePreviewProps> = ({
  pendingCount,
  onOpenQueue,
  onActionClick,
  items = DEFAULT_PREVIEW_ITEMS,
}) => {
  const displayItems = pendingCount > 0 ? items.slice(0, Math.max(1, Math.min(3, pendingCount))) : [];

  return (
    <section className="bg-surface-bright rounded-lg p-4 border border-outline shadow-2xs flex flex-col gap-3.5">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline">
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-on-surface">Pending Approval Queue</h3>
            <span className="font-mono text-[11px] text-on-surface-variant font-medium tabular-nums">
              ({pendingCount} Pending)
            </span>
          </div>
          <p className="body-md text-on-surface-variant mt-0.5 text-xs">
            Draft responses awaiting human verification. Decisions can also be taken via Telegram bot.
          </p>
        </div>

        {/* Review Queue Button */}
        <button
          type="button"
          onClick={onOpenQueue}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-container-low hover:bg-surface-container text-primary text-xs font-medium transition-colors self-start sm:self-auto border border-outline shadow-2xs active:scale-[0.99] shrink-0"
        >
          <span>Review Queue</span>
          <span className="text-[10px] px-1 py-0.2 rounded bg-surface-container-highest text-on-surface-variant font-sans">
            {formatKeyCombo("1")}
          </span>
          <CaretRight size={13} weight="bold" />
        </button>
      </div>

      {/* Content: Either Items List or Clean Empty State */}
      {displayItems.length > 0 ? (
        <div className="flex flex-col gap-2.5">
          {displayItems.map((item) => (
            <article
              key={item.id}
              className="p-3.5 rounded-md bg-surface-container-low border border-outline hover:border-outline-variant transition-colors flex flex-col gap-2.5"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className={`w-6 h-6 rounded-md ${item.avatarBg} ${item.avatarText} font-semibold flex items-center justify-center text-[11px] shrink-0 border border-outline/40`}
                  >
                    {item.initials}
                  </div>
                  <span className="text-xs text-on-surface font-semibold truncate">
                    {item.author}
                  </span>
                  {item.verified && (
                    <span title="Verified" className="inline-flex shrink-0">
                      <CheckCircle
                        size={14}
                        weight="fill"
                        className="text-primary"
                      />
                    </span>
                  )}
                  <span className="text-on-surface-variant text-[12px] font-normal truncate hidden sm:inline">
                    · {item.headline}
                  </span>
                  <span className="text-[11px] text-on-surface-variant font-medium shrink-0">
                    · {item.type}
                  </span>
                </div>
                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className="text-[11px] text-tertiary font-medium">
                    {item.confidence}
                  </span>
                  <span className="text-[11px] text-on-surface-variant font-sans">{item.timeAgo}</span>
                </div>
              </div>

              {/* Context Quote & Proposed Draft */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
                <div className="md:col-span-8 flex flex-col gap-1">
                  {item.quote && (
                    <p className="text-xs text-on-surface-variant italic border-l-2 border-primary/40 pl-2 line-clamp-1">
                      {item.quote}
                    </p>
                  )}
                  <p className="text-xs text-on-surface line-clamp-2 leading-relaxed">{item.draft}</p>
                </div>

                {/* Inline Decision Actions */}
                <div className="md:col-span-4 flex items-center justify-end gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      if (onActionClick) onActionClick(item.secondaryAction, item.id);
                      else onOpenQueue();
                    }}
                    className="px-2.5 py-1 rounded-md bg-surface-container-lowest hover:bg-error/10 hover:text-error text-on-surface-variant text-xs font-medium transition-colors border border-outline shrink-0 active:scale-[0.99]"
                  >
                    {item.secondaryAction}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (onActionClick) onActionClick(item.primaryAction, item.id);
                      else onOpenQueue();
                    }}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors shadow-2xs flex items-center gap-1.5 shrink-0 active:scale-[0.99] ${
                      item.primaryAction === "Approve"
                        ? "bg-primary hover:bg-primary-container text-on-primary"
                        : "bg-surface-container-highest hover:bg-surface-container text-on-surface border border-outline"
                    }`}
                  >
                    {item.primaryAction === "Approve" ? (
                      <Check size={13} weight="bold" />
                    ) : (
                      <PencilSimple size={13} weight="bold" />
                    )}
                    <span>{item.primaryAction}</span>
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-outline bg-surface-container-low/40 py-8 text-center">
          <Inbox size={26} className="text-on-surface-variant/60 mb-2" />
          <p className="body-strong text-on-surface">No pending approvals in queue</p>
          <p className="label-sm text-on-surface-variant mt-1 max-w-sm">
            All scout suggestions reviewed. New candidates will appear here as feeds are scanned.
          </p>
        </div>
      )}
    </section>
  );
};
