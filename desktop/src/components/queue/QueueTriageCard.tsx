import React from "react";
import { CheckCircle } from "@phosphor-icons/react";

export interface PendingItem {
  id: string;
  actionType: "comment" | "post";
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

  return (
    <article
      data-testid={`pending-card-${item.id}`}
      onClick={onSelect}
      className={`group relative p-3 rounded-xl cursor-pointer transition-all text-left ${
        isSelected
          ? "bg-surface-container-lowest shadow-sm ring-1 ring-primary/20"
          : "bg-surface-container-lowest/60 hover:bg-surface-container-lowest border border-outline/40 hover:border-outline shadow-2xs"
      }`}
    >
      {/* Selected Indicator Bar */}
      {isSelected && (
        <div className="absolute left-0 top-3 bottom-3 w-1 bg-primary rounded-r-full" />
      )}

      {/* Header: Avatar, Name, Verified Badge, Action Tag & Time */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0 font-label-sm font-semibold">
            {initials}
          </div>
          <div className="flex items-center gap-1 min-w-0">
            <span className="font-body-strong text-on-surface truncate">
              {item.author}
            </span>
            <CheckCircle
              size={13}
              weight="fill"
              className="text-primary shrink-0 inline-block"
              aria-label="Verified author"
            />
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`px-1.5 py-0.5 rounded-full font-label-sm ${
              item.actionType === "comment"
                ? "bg-secondary/15 text-secondary border border-secondary/20"
                : "bg-surface-container-highest text-on-surface border border-outline"
            }`}
          >
            {item.actionType === "comment" ? "Comment" : "Original Post"}
          </span>
          <span className="font-label-sm text-on-surface-variant">
            {item.createdAt}
          </span>
        </div>
      </div>

      {/* Author Headline */}
      <p className="text-[11px] text-on-surface-variant line-clamp-1 mb-1.5 font-normal">
        {item.headline}
      </p>

      {/* Quoted Excerpt */}
      {item.postExcerpt && (
        <p className="font-body-md text-on-surface-variant font-normal line-clamp-2 mb-1.5 leading-relaxed italic">
          “{item.postExcerpt}”
        </p>
      )}

      {/* Draft Preview Box */}
      <p className="font-body-md text-on-surface font-normal line-clamp-2 mb-2 bg-surface-container-low/70 p-2 rounded-lg leading-relaxed border border-outline/30">
        {item.draftText}
      </p>

      {/* Card Footer: Match % & Topic Badge */}
      <div className="flex items-center justify-between text-on-surface-variant pt-0.5">
        <div className="inline-flex items-center gap-1 font-label-sm text-tertiary font-medium">
          <span className="rounded-full px-1.5 py-0.5 bg-tertiary/10 border border-tertiary/20">
            {matchPercent}% Match
          </span>
          <span className="opacity-40">·</span>
          <span>{item.topic}</span>
        </div>
        <span className="font-code-sm text-on-surface-variant opacity-75">
          {topicTag}
        </span>
      </div>
    </article>
  );
};
