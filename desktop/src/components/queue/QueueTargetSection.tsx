import React from "react";
import { ThumbsUp, ChatCircleText } from "@phosphor-icons/react";
import { PendingItem } from "./QueueTriageCard";

interface QueueTargetSectionProps {
  item: PendingItem;
}

export const QueueTargetSection: React.FC<QueueTargetSectionProps> = ({ item }) => {
  return (
    <section className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between text-on-surface-variant">
        <span className="font-label-sm uppercase tracking-wider font-semibold text-outline">
          Target Context
        </span>
        <span className="font-label-sm">
          Published {item.createdAt} via Scheduled Feed Scout
        </span>
      </div>

      <div className="p-5 rounded-2xl bg-surface-container-lowest border border-outline/50 shadow-xs relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-secondary" />
        <blockquote
          data-testid="target-excerpt"
          className="font-body-lg text-on-surface leading-relaxed italic"
        >
          "{item.postExcerpt}"
        </blockquote>

        <div className="mt-4 pt-3 border-t border-outline/40 flex items-center justify-between text-on-surface-variant">
          <div className="flex items-center gap-4 text-xs font-label-md">
            <span className="inline-flex items-center gap-1">
              <ThumbsUp size={14} className="text-primary" />
              <span>Engaged Discussion</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <ChatCircleText size={14} className="text-secondary" />
              <span>Active Thread</span>
            </span>
          </div>

          <div className="text-right text-[11px] text-on-surface-variant font-body-md">
            : {item.author}, {item.headline}
          </div>
        </div>
      </div>
    </section>
  );
};
