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
    <div className="rounded-lg border border-outline/70 bg-surface-container-lowest p-4 shadow-2xs">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md border border-outline/60 bg-surface-container-high text-on-surface text-xs font-semibold">
            {initials}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h2 className="text-sm font-semibold text-on-surface">
                {candidate.target_name}
              </h2>
              <span title="Verified" className="inline-flex items-center shrink-0">
                <CheckCircle
                  size={15}
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
          className="flex items-center gap-1.5 rounded-md border border-outline bg-surface-container px-2.5 py-1.5 text-xs font-medium text-on-surface transition hover:bg-surface-container-high shadow-2xs"
        >
          <span>View Profile</span>
          <ArrowSquareOut size={13} />
        </a>
      </div>

      {/* Mutual Interaction Citation Blockquote */}
      {candidate.mutual_context && (
        <div className="mt-3.5 rounded-md border border-outline/50 bg-surface-container-low/60 p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-on-surface-variant">
            <Sparkle size={13} />
            <span>Mutual Interaction Context</span>
          </div>
          <blockquote
            data-testid="mutual-context-quote"
            className="mt-1.5 border-l-2 border-primary/40 pl-3 text-xs leading-relaxed text-on-surface/90"
          >
            {candidate.mutual_context}
          </blockquote>
        </div>
      )}
    </div>
  );
};
