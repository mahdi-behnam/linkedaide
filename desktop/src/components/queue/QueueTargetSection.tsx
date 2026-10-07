import React from "react";
import { PendingItem } from "./QueueTriageCard";

interface QueueTargetSectionProps {
  item: PendingItem;
}

export const QueueTargetSection: React.FC<QueueTargetSectionProps> = ({ item }) => {
  const isPost = item.actionType === "post";
  const isReaction = item.actionType === "reaction";

  return (
    <section className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between text-on-surface-variant">
        <span className="font-label-sm uppercase tracking-wider font-semibold text-outline">
          {isPost ? "Post Concept & Focus" : isReaction ? "Target Post & Reaction" : "Target Context"}
        </span>
        <span className="font-label-sm">
          {isPost ? "Drafted via Post Ideation" : `Discovered ${item.createdAt}`}
        </span>
      </div>

      <div className="p-4 rounded-lg bg-surface-bright border border-outline shadow-2xs relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary/60" />
        {item.postExcerpt ? (
          <blockquote
            data-testid="target-excerpt"
            className="text-xs text-on-surface leading-relaxed italic"
          >
            "{item.postExcerpt}"
          </blockquote>
        ) : (
          <p className="text-xs text-on-surface leading-relaxed">
            {isPost
              ? "Original thought leadership post drafted for your profile."
              : "Target post reference."}
          </p>
        )}

        <div className="mt-3 pt-2.5 border-t border-outline/40 flex items-center justify-between text-on-surface-variant text-[11px]">
          <span>
            {isPost
              ? "Focus Area & Author Persona"
              : isReaction
              ? `Recommended Reaction: ${(item.reactionType || "like").toUpperCase()}`
              : "Context snippet from public feed"}
          </span>
          <div className="text-right">
            {item.author}, {item.headline}
          </div>
        </div>
      </div>
    </section>
  );
};
