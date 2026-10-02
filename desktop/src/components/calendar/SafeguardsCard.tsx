import React from "react";
import { ShieldCheck } from "../icons";

export const SafeguardsCard: React.FC = () => {
  return (
    <div className="flex flex-col justify-between gap-4 bg-surface-container-lowest p-5 rounded-2xl border border-surface-container-high shadow-xs">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between pb-1 border-b border-surface-container-high/60">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-primary" />
            <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">
              Schedule Safeguards &amp; Invariants
            </h3>
          </div>
          <span className="font-label-sm text-label-sm px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-medium">
            Edge Guard
          </span>
        </div>

        <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
          Deterministic rate limits guarantee maximum{" "}
          <span className="font-body-strong text-on-surface">3 posts</span> and{" "}
          <span className="font-body-strong text-on-surface">15 comments</span> per 24 hours. Automated scouting triggers drafts directly to the{" "}
          <span className="text-primary font-medium">Approval Queue</span> for strict human verification.
        </p>

        {/* Daily Quota Velocity Card */}
        <div className="p-3 rounded-xl bg-surface-container-low flex items-center justify-between gap-3 border border-surface-container-high/50">
          <div className="flex items-center gap-3">
            <svg className="w-10 h-10 text-primary shrink-0" viewBox="0 0 36 36">
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
                strokeDasharray="88"
                strokeDashoffset="56"
                strokeLinecap="round"
                strokeWidth="3"
                transform="rotate(-90 18 18)"
              />
            </svg>
            <div className="flex flex-col">
              <span className="font-body-strong text-body-strong text-on-surface">
                Daily Quota Velocity
              </span>
              <span className="font-code-sm text-code-sm text-on-surface-variant">
                1 of 3 Posts · 8 of 15 Comments
              </span>
            </div>
          </div>
          <span className="font-label-sm text-label-sm text-tertiary bg-tertiary-fixed/60 px-2.5 py-0.5 rounded-full font-medium">
            Optimal
          </span>
        </div>
      </div>

      {/* Legend Items */}
      <div className="pt-2 border-t border-surface-container-high/60 flex flex-col gap-2">
        <span className="font-label-sm text-label-sm uppercase tracking-wider text-outline font-medium">
          Calendar Event Types
        </span>
        <div className="grid grid-cols-2 gap-2 text-on-surface-variant font-label-md text-label-md">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-primary shrink-0" />
            <span>Scheduled Post</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-tertiary shrink-0" />
            <span>Published Post</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-outline shrink-0" />
            <span>Draft Post</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-secondary shrink-0" />
            <span>Scout Window</span>
          </div>
        </div>
      </div>
    </div>
  );
};
