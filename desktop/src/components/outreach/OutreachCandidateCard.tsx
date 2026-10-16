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


  return (
    <article
      id={`candidate-card-${candidate.id}`}
      data-testid={`candidate-card-${candidate.id}`}
      onClick={onSelect}
      className={`group relative p-2.5 rounded-md cursor-pointer transition-colors text-left ${
        isSelected
          ? "bg-surface-bright shadow-2xs border border-primary/30"
          : "bg-surface-bright/70 hover:bg-surface-bright border border-outline/50 hover:border-outline shadow-2xs"
      }`}
    >
      {/* Selected Indicator Bar */}
      {isSelected && (
        <div className="absolute left-0 top-2 bottom-2 w-0.5 bg-primary rounded-r-xs" />
      )}

      {/* Header: Avatar, Name, Status Pill */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0 text-[10px] font-semibold border border-primary/20">
            {initials}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1">
              <h3 className="text-xs font-semibold text-on-surface truncate">
                {candidate.target_name}
              </h3>
              <CheckCircle
                size={12}
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
          className={`text-[11px] font-medium capitalize shrink-0 ${
            candidate.status === "sent"
              ? "text-tertiary"
              : candidate.status === "rejected" || candidate.status === "failed"
              ? "text-error"
              : "text-amber-500"
          }`}
        >
          {candidate.status}
        </span>
      </div>

      {/* Mutual Context Citation */}
      {candidate.mutual_context && (
        <div className="mt-2 flex items-center gap-1.5 rounded-md border border-primary/20 bg-primary/5 px-2 py-1 text-[11px] text-primary">
          <ChatText size={12} weight="bold" className="shrink-0" />
          <span className="line-clamp-1">{candidate.mutual_context}</span>
        </div>
      )}
    </article>
  );
};
