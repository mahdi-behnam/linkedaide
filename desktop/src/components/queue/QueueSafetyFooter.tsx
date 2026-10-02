import React from "react";
import { ShieldCheck } from "@phosphor-icons/react";

interface QueueSafetyFooterProps {
  commentsRemaining: number;
  commentsMax: number;
  nextScoutTime?: string;
}

export const QueueSafetyFooter: React.FC<QueueSafetyFooterProps> = ({
  commentsRemaining,
  commentsMax,
  nextScoutTime = "14:00 UTC",
}) => {
  return (
    <footer className="p-4 rounded-xl bg-surface-container border border-outline/50 flex items-center justify-between text-on-surface-variant shadow-2xs">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex items-center justify-center text-primary border border-outline/40">
          <ShieldCheck size={18} weight="fill" />
        </div>
        <div className="flex flex-col">
          <span className="font-body-strong text-on-surface">
            Cloudflare Edge Relay Ready
          </span>
          <span className="font-label-sm text-on-surface-variant">
            Safe rate limit: {commentsRemaining} of {commentsMax} daily comments remaining.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="font-code-sm text-on-surface-variant">
          Next scout: {nextScoutTime}
        </span>
        <button
          type="button"
          className="px-2.5 py-1 rounded-lg bg-surface-container-highest hover:bg-surface-container-high text-on-surface font-label-md transition-colors border border-outline/40"
        >
          Audit Rule
        </button>
      </div>
    </footer>
  );
};
