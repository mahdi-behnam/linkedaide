import React from "react";
import {
  CheckCircle,
  ArrowSquareOut,
  X,
  ArrowClockwise,
  PaperPlaneRight,
  WarningCircle,
} from "@phosphor-icons/react";
import { PendingItem } from "./QueueTriageCard";

interface QueueWorkspaceHeaderProps {
  item: PendingItem;
  onApprove: () => void;
  onReject: () => void;
  onRegenerate: () => void;
  isProcessing: boolean;
  isRewriting: boolean;
  actionNotice: string | null;
  actionError: string | null;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase() || "LI";
}

export const QueueWorkspaceHeader: React.FC<QueueWorkspaceHeaderProps> = ({
  item,
  onApprove,
  onReject,
  onRegenerate,
  isProcessing,
  isRewriting,
  actionNotice,
  actionError,
}) => {
  const initials = getInitials(item.author);

  return (
    <header className="sticky top-0 z-30 bg-surface/95 backdrop-blur-md border-b border-outline px-8 py-3.5 flex flex-col gap-3">
      {/* Top author row & profile link */}
      <div className="flex items-center justify-between gap-3.5 w-full">
        <div className="flex items-center gap-3.5 min-w-0 flex-1">
          <div className="w-10 h-10 rounded-full bg-secondary/15 text-secondary font-headline-sm font-semibold flex items-center justify-center shrink-0 shadow-xs border border-secondary/20 select-none text-[14px]">
            {initials}
          </div>
          <div className="flex flex-col justify-center min-w-0 flex-1 gap-0.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="font-headline-sm text-[16px] text-on-surface font-semibold tracking-tight">
                Post by {item.author}
              </h2>
              <span title="Verified" className="inline-flex items-center shrink-0">
                <CheckCircle
                  size={16}
                  weight="fill"
                  className="text-primary"
                />
              </span>
              <span className="opacity-40 text-on-surface-variant text-[12px]">·</span>
              <span className="text-on-surface-variant font-body-md text-[13px] font-normal truncate max-w-md">
                {item.headline}
              </span>
            </div>
            <div className="flex items-center gap-2 text-on-surface-variant font-label-sm text-[12px]">
              {item.postUrl ? (
                <a
                  href={item.postUrl}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="target-post-link"
                  className="inline-flex items-center gap-1 text-primary hover:underline font-medium transition-colors"
                >
                  <span>View on LinkedIn</span>
                  <ArrowSquareOut size={13} />
                </a>
              ) : (
                <span className="text-on-surface-variant">Original Post</span>
              )}
              <span className="opacity-40 text-on-surface-variant text-[10px]">·</span>
              <span className="text-on-surface-variant opacity-75 font-code-sm">
                via Feed Scout · Published {item.createdAt}
              </span>
            </div>
          </div>
        </div>

        {/* Top Action Buttons (Things 3 / Apple Header) */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            data-testid="reject-btn"
            disabled={isProcessing || isRewriting}
            onClick={onReject}
            className="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-error-container hover:text-on-error-container text-on-surface-variant transition-colors font-body-strong whitespace-nowrap disabled:opacity-50"
          >
            <X size={15} weight="bold" className="group-hover:text-error" />
            <span>Reject</span>
            <kbd className="font-code-sm opacity-60 ml-0.5">R</kbd>
          </button>

          <button
            type="button"
            data-testid="top-regenerate-btn"
            disabled={isProcessing || isRewriting}
            onClick={onRegenerate}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-body-strong transition-colors whitespace-nowrap disabled:opacity-50"
          >
            <ArrowClockwise
              size={15}
              className={isRewriting ? "animate-spin text-primary" : "text-on-surface-variant"}
            />
            <span>Regenerate</span>
          </button>

          <button
            type="button"
            data-testid="approve-btn"
            disabled={isProcessing || isRewriting}
            onClick={onApprove}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-primary hover:bg-primary-container text-on-primary font-body-strong shadow-sm hover:shadow transition-all whitespace-nowrap disabled:opacity-50"
          >
            <PaperPlaneRight size={15} weight="bold" />
            <span>Approve & Dispatch</span>
            <kbd className="font-code-sm px-1.5 py-0.2 rounded bg-surface-container-lowest/20 text-on-primary">
              A
            </kbd>
          </button>
        </div>
      </div>

      {/* Floating Notices & Errors */}
      {actionNotice && (
        <div
          data-testid="action-notice"
          className="flex items-center gap-2 rounded-md border border-tertiary/30 bg-tertiary/10 px-3.5 py-1.5 text-xs text-tertiary"
        >
          <CheckCircle size={14} weight="bold" />
          <span>{actionNotice}</span>
        </div>
      )}

      {actionError && (
        <div
          data-testid="action-error"
          className="flex items-center gap-2 rounded-md border border-error/30 bg-error/10 px-3.5 py-1.5 text-xs text-error"
        >
          <WarningCircle size={14} weight="bold" />
          <span>{actionError}</span>
        </div>
      )}
    </header>
  );
};
