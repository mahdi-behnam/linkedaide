import React from "react";
import { UserPlus, ShieldCheck } from "@phosphor-icons/react";
import { ConnectionRequestAction } from "../../types";
import { OutreachCandidateCard } from "./OutreachCandidateCard";

interface OutreachLeftPaneProps {
  items: ConnectionRequestAction[];
  selectedId: string;
  onSelectId: (id: string) => void;
  connectionsSent: number;
  connectionsMax: number;
}

export const OutreachLeftPane: React.FC<OutreachLeftPaneProps> = ({
  items,
  selectedId,
  onSelectId,
  connectionsSent,
  connectionsMax,
}) => {
  const pendingCount = items.filter((c) => c.status === "pending").length;
  const quotaPercent = Math.min(100, Math.round((connectionsSent / connectionsMax) * 100));

  return (
    <section className="w-[360px] lg:w-[390px] shrink-0 flex flex-col bg-surface-container-low border-r border-outline select-none h-full">
      {/* Header Bar */}
      <div className="p-4 pb-3 flex flex-col gap-3 border-b border-outline/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="font-headline-md text-on-surface tracking-tight">
              Outreach Queue
            </h1>
            <span
              data-testid="pending-count-pill"
              className="inline-flex items-center px-1.5 py-0.2 rounded-[4px] bg-surface-container-high text-on-surface text-[10px] font-medium tabular-nums"
            >
              {pendingCount} Pending
            </span>
          </div>

          {/* Daily Connection Cap Quota Badge */}
          <div
            data-testid="connection-quota-badge"
            className="flex items-center gap-2 rounded-md border border-outline bg-surface-container-lowest px-2.5 py-1 shadow-2xs"
          >
            <div className="flex h-5 w-5 items-center justify-center rounded-sm bg-tertiary/10 text-tertiary">
              <ShieldCheck size={13} weight="bold" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center justify-between gap-2 text-[10px]">
                <span className="font-medium text-on-surface-variant">Daily Cap</span>
                <span className="font-sans font-medium text-tertiary tabular-nums">
                  {connectionsSent} / {connectionsMax}
                </span>
              </div>
              <div className="mt-0.5 h-1 w-16 overflow-hidden rounded-xs bg-surface-container-high">
                <div
                  className="h-full rounded-xs bg-tertiary transition-all duration-300"
                  style={{ width: `${quotaPercent}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="text-xs text-on-surface-variant">
          Human-in-the-loop connection request review and 300-character personalized note studio
        </div>
      </div>

      {/* Candidate List Header */}
      <div className="px-4 py-2 border-b border-outline/40 flex items-center justify-between">
        <span className="text-xs font-medium tracking-wider text-on-surface-variant uppercase">
          Connection Candidates ({items.length})
        </span>
      </div>

      {/* Scrollable List */}
      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {items.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center rounded-xl border border-dashed border-outline text-center p-6 bg-surface-container/30">
            <UserPlus size={28} className="text-on-surface-variant opacity-60" />
            <p className="mt-2 text-sm font-medium text-on-surface">
              No connection candidates queued
            </p>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Feed scout runs will surface high-signal contacts
            </p>
          </div>
        ) : (
          items.map((candidate) => (
            <OutreachCandidateCard
              key={candidate.id}
              candidate={candidate}
              isSelected={candidate.id === selectedId}
              onSelect={() => onSelectId(candidate.id)}
            />
          ))
        )}
      </div>
    </section>
  );
};
