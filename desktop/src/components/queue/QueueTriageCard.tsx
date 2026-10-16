import React from "react";
import { CheckCircle } from "@phosphor-icons/react";
import { formatTimeAgo } from "../../utils/datetime";

export interface PendingItem {
  id: string;
  actionType: "comment" | "post" | "reaction" | "reply";
  reactionType?: string;
  author: string;
  headline: string;
  postUrl: string;
  postExcerpt: string;
  draftText: string;
  confidence: number;
  reasoning: string;
  engagementStyle: string;
  createdAt: string;
  topic: string;
}

interface QueueTriageCardProps {
  item: PendingItem;
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

export const QueueTriageCard: React.FC<QueueTriageCardProps> = ({
  item,
  isSelected,
  onSelect,
}) => {
  const initials = getInitials(item.author);
  const matchPercent = Math.round(item.confidence * 100);
  const topicTag = `#${item.topic.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  const getActionLabel = () => {
    if (item.actionType === "reaction") {
      const rx = (item.reactionType || "like").charAt(0).toUpperCase() + (item.reactionType || "like").slice(1);
      return `Reaction · ${rx}`;
    }
    if (item.actionType === "post") return "Original Post";
    if (item.actionType === "reply") return "Reply";
    return "Comment";
  };

  return (
    <article
      id={`queue-item-${item.id}`}
      data-testid={`pending-card-${item.id}`}
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

      {/* Header: Avatar, Name, Verified Badge, Action Tag & Time */}
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="w-5 h-5 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0 text-[10px] font-semibold border border-primary/20">
            {initials}
          </div>
          <div className="flex items-center gap-1 min-w-0">
            <span className="text-xs font-semibold text-on-surface truncate">
              {item.author}
            </span>
            <CheckCircle
              size={12}
              weight="fill"
              className="text-primary shrink-0 inline-block"
              aria-label="Verified author"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] font-medium text-on-surface-variant">
            {getActionLabel()}
          </span>
          <span className="text-[10px] text-on-surface-variant font-sans">
            {formatTimeAgo(item.createdAt)}
          </span>
        </div>
      </div>

      {/* Author Headline */}
      <p className="text-[11px] text-on-surface-variant line-clamp-1 mb-1 font-normal">
        {item.headline}
      </p>

      {/* Quoted Excerpt */}
      {item.postExcerpt && (
        <p className="text-xs text-on-surface-variant font-normal line-clamp-2 mb-1.5 leading-relaxed italic">
          “{item.postExcerpt}”
        </p>
      )}

      {/* Draft Preview Box */}
      <p className="text-xs text-on-surface font-normal line-clamp-2 mb-1.5 bg-surface-container-low/70 p-2 rounded-md leading-relaxed border border-outline/30">
        {item.actionType === "reaction"
          ? `Proposed Reaction: ${(item.reactionType || "like").charAt(0).toUpperCase() + (item.reactionType || "like").slice(1)}`
          : item.draftText}
      </p>

      {/* Card Footer: Match % & Topic Badge */}
      <div className="flex items-center justify-between text-on-surface-variant pt-0.5">
        <div className="inline-flex items-center gap-1.5 text-[11px] text-tertiary font-medium">
          <span className="tabular-nums text-[11px]">
            {matchPercent}% Match
          </span>
          <span className="opacity-40">·</span>
          <span>{item.topic}</span>
        </div>
        <span className="text-[10px] text-on-surface-variant opacity-75 font-sans">
          {topicTag}
        </span>
      </div>
    </article>
  );
};
