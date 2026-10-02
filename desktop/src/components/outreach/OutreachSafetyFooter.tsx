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
    <footer className="p-4 rounded-xl bg-surface-container border border-outline/50 flex items-center justify-between text-on-surface-variant shadow-2xs">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex items-center justify-center text-primary border border-outline/40">
          <ShieldCheck size={18} weight="fill" />
        </div>
        <div className="flex flex-col">
          <span className="font-body-strong text-on-surface">
            LinkedIn Safety Boundary
          </span>
          <span className="font-label-sm text-on-surface-variant">
            Safe rate limit: {remaining} of {connectionsMax} connection invitations remaining today.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="font-code-sm text-on-surface-variant">
          Quota: {connectionsSent}/{connectionsMax}
        </span>
        <span className="px-2 py-0.5 rounded-full bg-tertiary/15 text-tertiary text-label-sm font-semibold border border-tertiary/20">
          Edge Protected
        </span>
      </div>
    </footer>
  );
};
