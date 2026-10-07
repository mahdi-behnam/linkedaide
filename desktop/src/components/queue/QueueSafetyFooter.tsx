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
  nextScoutTime = "Upcoming",
}) => {
  return (
    <footer className="p-3 rounded-lg bg-surface-container border border-outline/50 flex items-center justify-between text-on-surface-variant shadow-2xs">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-md bg-surface-container-highest flex items-center justify-center text-primary border border-outline/40">
          <ShieldCheck size={16} weight="fill" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-semibold text-on-surface">
            Cloudflare Edge Relay
          </span>
          <span className="text-[11px] text-on-surface-variant tabular-nums">
            Safe rate limit: {commentsRemaining} of {commentsMax} daily comments remaining.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[11px] text-on-surface-variant font-sans">
          Next scout: {nextScoutTime}
        </span>
        <button
          type="button"
          className="px-2 py-0.5 rounded-md bg-surface-container-highest hover:bg-surface-container-high text-on-surface text-xs font-medium transition-colors border border-outline/40"
        >
          Audit Rule
        </button>
      </div>
    </footer>
  );
};
