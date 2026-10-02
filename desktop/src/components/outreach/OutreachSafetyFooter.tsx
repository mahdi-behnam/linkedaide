import React from "react";
import { ShieldCheck } from "@phosphor-icons/react";

interface OutreachSafetyFooterProps {
  connectionsSent: number;
  connectionsMax: number;
}

export const OutreachSafetyFooter: React.FC<OutreachSafetyFooterProps> = ({
  connectionsSent,
  connectionsMax,
}) => {
  const remaining = Math.max(0, connectionsMax - connectionsSent);

  return (
    <footer className="p-3 rounded-lg bg-surface-container/60 border border-outline/60 flex items-center justify-between text-on-surface-variant shadow-2xs">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-md bg-surface-container-highest flex items-center justify-center text-primary border border-outline/40">
          <ShieldCheck size={16} />
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-semibold text-on-surface">
            LinkedIn Safety Boundary
          </span>
          <span className="text-[11px] text-on-surface-variant">
            Safe rate limit: {remaining} of {connectionsMax} connection invitations remaining today.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-on-surface-variant tabular-nums">
          Quota: {connectionsSent}/{connectionsMax}
        </span>
        <span className="px-2 py-0.5 rounded-[4px] bg-tertiary/15 text-tertiary text-[11px] font-medium border border-tertiary/20">
          Edge Protected
        </span>
      </div>
    </footer>
  );
};
