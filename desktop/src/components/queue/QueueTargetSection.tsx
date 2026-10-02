import React from "react";
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

      <div className="p-4 rounded-lg bg-surface-bright border border-outline shadow-2xs relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary/60" />
        <blockquote
          data-testid="target-excerpt"
          className="text-xs text-on-surface leading-relaxed italic"
        >
          "{item.postExcerpt}"
        </blockquote>

        <div className="mt-3 pt-2.5 border-t border-outline/40 flex items-center justify-between text-on-surface-variant text-[11px]">
          <span>Context snippet from public feed</span>
          <div className="text-right">
            {item.author}, {item.headline}
          </div>
        </div>
      </div>
    </section>
  );
};
