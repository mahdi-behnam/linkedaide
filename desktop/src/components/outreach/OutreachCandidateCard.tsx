import React from "react";
import { ChatText, CheckCircle } from "@phosphor-icons/react";
import { ConnectionRequestAction } from "../../types";

interface OutreachCandidateCardProps {
  candidate: ConnectionRequestAction;
  isSelected: boolean;
  onSelect: () => void;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase() || "LI";
}

export const OutreachCandidateCard: React.FC<OutreachCandidateCardProps> = ({
  candidate,
  isSelected,
  onSelect,
}) => {
  const initials = getInitials(candidate.target_name);

  const statusStyles: Record<string, string> = {
    pending: "border-amber-500/30 bg-amber-500/10 text-amber-500",
    approved: "border-tertiary/30 bg-tertiary/10 text-tertiary",
    rejected: "border-outline bg-surface-container text-on-surface-variant",
    sent: "border-primary/30 bg-primary/10 text-primary",
    failed: "border-error/30 bg-error/10 text-error",
  };

  return (
    <article
      data-testid={`candidate-card-${candidate.id}`}
      onClick={onSelect}
      className={`group relative p-3.5 rounded-xl cursor-pointer transition-all text-left ${
        isSelected
          ? "bg-surface-container-lowest shadow-sm ring-1 ring-primary/20"
          : "bg-surface-container-lowest/60 hover:bg-surface-container-lowest border border-outline/40 hover:border-outline shadow-2xs"
      }`}
    >
      {/* Selected Indicator Bar */}
      {isSelected && (
        <div className="absolute left-0 top-3 bottom-3 w-1 bg-primary rounded-r-full" />
      )}

      {/* Header: Avatar, Name, Status Pill */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0 font-label-sm font-semibold border border-primary/20">
            {initials}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1">
              <h3 className="font-body-strong text-on-surface truncate">
                {candidate.target_name}
              </h3>
              <CheckCircle
                size={13}
                weight="fill"
                className="text-primary shrink-0"
              />
            </div>
            <p className="text-[11px] text-on-surface-variant line-clamp-1 font-normal">
              {candidate.target_headline}
            </p>
          </div>
        </div>

        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase shrink-0 ${
            statusStyles[candidate.status] || statusStyles.pending
          }`}
        >
          {candidate.status}
        </span>
      </div>

      {/* Mutual Context Citation */}
      {candidate.mutual_context && (
        <div className="mt-2.5 flex items-center gap-1.5 rounded-lg border border-primary/20 bg-primary/5 px-2.5 py-1.5 text-[11px] text-primary">
          <ChatText size={13} weight="bold" className="shrink-0" />
          <span className="line-clamp-1">{candidate.mutual_context}</span>
        </div>
      )}
    </article>
  );
};
