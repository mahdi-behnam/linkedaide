import React from "react";
import {
  CheckCircle,
  ArrowSquareOut,
  WarningCircle,
} from "@phosphor-icons/react";
import { PendingItem } from "./QueueTriageCard";

interface QueueWorkspaceHeaderProps {
  item: PendingItem;
  onApprove?: () => void;
  onReject?: () => void;
  onRegenerate?: () => void;
  isProcessing?: boolean;
  isRewriting?: boolean;
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
  actionNotice,
  actionError,
}) => {
  const initials = getInitials(item.author);

  return (
    <header className="sticky top-0 z-30 bg-surface/95 backdrop-blur-md border-b border-outline px-6 py-3 flex flex-col gap-2.5">
      {/* Top author row & profile link */}
      <div className="flex items-center justify-between gap-3 w-full">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-md bg-primary/10 text-primary font-semibold flex items-center justify-center shrink-0 border border-primary/20 select-none text-xs">
            {initials}
          </div>
          <div className="flex flex-col justify-center min-w-0 flex-1 gap-0.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="text-sm text-on-surface font-semibold tracking-tight">
                Post by {item.author}
              </h2>
              <span title="Verified" className="inline-flex items-center shrink-0">
                <CheckCircle
                  size={14}
                  weight="fill"
                  className="text-primary"
                />
              </span>
              <span className="opacity-40 text-on-surface-variant text-[12px]">·</span>
              <span className="text-on-surface-variant text-xs font-normal truncate max-w-md">
                {item.headline}
              </span>
            </div>
            <div className="flex items-center gap-2 text-on-surface-variant text-[11px]">
              {item.postUrl ? (
                <a
                  href={item.postUrl}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="target-post-link"
                  className="inline-flex items-center gap-1 text-primary hover:underline font-medium transition-colors"
                >
                  <span>View on LinkedIn</span>
                  <ArrowSquareOut size={12} />
                </a>
              ) : (
                <span className="text-on-surface-variant">Original Post</span>
              )}
              <span className="opacity-40 text-on-surface-variant text-[10px]">·</span>
              <span className="text-on-surface-variant opacity-75 font-sans">
                via Feed Scout · Published {item.createdAt}
              </span>
            </div>
          </div>
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
