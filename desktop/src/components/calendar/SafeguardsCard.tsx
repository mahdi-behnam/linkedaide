import React from "react";
import { useApp } from "../../context/AppContext";
import { ShieldCheck } from "../icons";

export const SafeguardsCard: React.FC = () => {
  const { quota } = useApp();

  const postsMax = quota?.postsMax ?? 3;
  const postsExecuted = quota?.postsExecuted ?? 0;
  const commentsMax = quota?.commentsMax ?? 15;
  const commentsExecuted = quota?.commentsExecuted ?? 0;

  const totalCap = postsMax + commentsMax;
  const totalUsed = postsExecuted + commentsExecuted;
  const ratio = totalCap > 0 ? Math.min(1, Math.max(0, totalUsed / totalCap)) : 0;
  const circumference = 88;
  const strokeDashoffset = Math.round(circumference * (1 - ratio));

  const statusLabel =
    ratio >= 1
      ? "Capped"
      : ratio > 0.8
      ? "Near Cap"
      : ratio > 0
      ? "Active"
      : "Nominal";

  const statusColor =
    ratio >= 1
      ? "text-error"
      : ratio > 0.8
      ? "text-amber-500"
      : "text-tertiary";

  return (
    <div className="flex flex-col justify-between gap-3.5 bg-surface-container-lowest p-4 rounded-lg border border-outline/70 shadow-2xs">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between pb-1 border-b border-outline/50">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-primary" />
            <h3 className="text-xs font-semibold text-on-surface">
              Schedule Safeguards &amp; Invariants
            </h3>
          </div>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed">
          Deterministic rate limits guarantee maximum{" "}
          <span className="text-on-surface font-medium">{postsMax} posts</span> and{" "}
          <span className="text-on-surface font-medium">{commentsMax} comments</span> per 24 hours. Automated scouting triggers drafts directly to the{" "}
          <span className="text-primary font-medium">Approval Queue</span> for strict human verification.
        </p>

        {/* Daily Quota Velocity Card */}
        <div className="p-2.5 rounded-md bg-surface-container-low flex items-center justify-between gap-3 border border-outline/50">
          <div className="flex items-center gap-2.5">
            <svg className="w-8 h-8 text-primary shrink-0" viewBox="0 0 36 36">
              <circle
                cx="18"
                cy="18"
                fill="none"
                r="14"
                stroke="currentColor"
                className="opacity-20"
                strokeWidth="3"
              />
              <circle
                cx="18"
                cy="18"
                fill="none"
                r="14"
                stroke="currentColor"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                strokeWidth="3"
                transform="rotate(-90 18 18)"
              />
            </svg>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-on-surface">
                Daily Quota Velocity
              </span>
              <span className="font-mono text-[10px] text-on-surface-variant tabular-nums">
                {postsExecuted} of {postsMax} Posts · {commentsExecuted} of {commentsMax} Comments
              </span>
            </div>
          </div>
          <span className={`text-[11px] font-medium ${statusColor}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Legend Items */}
      <div className="pt-2 border-t border-outline/50 flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-outline font-semibold">
          Calendar Event Types
        </span>
        <div className="grid grid-cols-2 gap-1.5 text-on-surface-variant text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-[1px] bg-primary shrink-0" />
            <span>Scheduled Post</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-[1px] bg-tertiary shrink-0" />
            <span>Published Post</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-[1px] bg-outline shrink-0" />
            <span>Draft Post</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-[1px] bg-secondary shrink-0" />
            <span>Scout Window</span>
          </div>
        </div>
      </div>
    </div>
  );
};
