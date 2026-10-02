import React from "react";
import { ArrowSquareOut, Sparkle, CheckCircle } from "@phosphor-icons/react";
import { ConnectionRequestAction } from "../../types";

interface OutreachProfileCardProps {
  candidate: ConnectionRequestAction;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase() || "LI";
}

export const OutreachProfileCard: React.FC<OutreachProfileCardProps> = ({ candidate }) => {
  const initials = getInitials(candidate.target_name);

  return (
    <div className="rounded-2xl border border-outline/60 bg-surface-container-lowest p-5 shadow-xs">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-primary text-sm font-bold shadow-2xs">
            {initials}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-base font-semibold text-on-surface">
                {candidate.target_name}
              </h2>
              <span title="Verified" className="inline-flex items-center shrink-0">
                <CheckCircle
                  size={16}
                  weight="fill"
                  className="text-primary"
                />
              </span>
            </div>
            <p className="text-xs text-on-surface-variant font-normal mt-0.5">
              {candidate.target_headline}
            </p>
          </div>
        </div>

        <a
          href={candidate.profile_url}
          target="_blank"
          rel="noreferrer"
          data-testid="profile-link"
          className="flex items-center gap-1.5 rounded-lg border border-outline bg-surface-container px-3 py-1.5 text-xs font-medium text-on-surface transition hover:bg-surface-container-high shadow-2xs"
        >
          <span>View Profile</span>
          <ArrowSquareOut size={14} />
        </a>
      </div>

      {/* Mutual Interaction Citation Blockquote */}
      {candidate.mutual_context && (
        <div className="mt-4 rounded-xl border border-outline/50 bg-surface-container-low/70 p-3.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-primary">
            <Sparkle size={14} weight="fill" />
            <span>Mutual Interaction Context</span>
          </div>
          <blockquote
            data-testid="mutual-context-quote"
            className="mt-1.5 border-l-2 border-primary/50 pl-3 text-xs leading-relaxed text-on-surface italic"
          >
            {candidate.mutual_context}
          </blockquote>
        </div>
      )}
    </div>
  );
};
