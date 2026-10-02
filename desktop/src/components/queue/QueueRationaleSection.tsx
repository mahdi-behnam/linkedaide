import React from "react";
import { Sparkle, Cpu } from "@phosphor-icons/react";
import { PendingItem } from "./QueueTriageCard";

interface QueueRationaleSectionProps {
  item: PendingItem;
}

export const QueueRationaleSection: React.FC<QueueRationaleSectionProps> = ({ item }) => {
  const matchPercent = Math.round(item.confidence * 100);
  const formattedStyle = item.engagementStyle.replace(/_/g, " ");

  return (
    <section className="p-4 rounded-xl bg-surface-container-low border border-outline/50 flex flex-col gap-3 shadow-2xs">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Sparkle size={18} weight="fill" className="text-primary" />
          <span className="font-body-strong text-on-surface">
            Synthesis & Rationale
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-code-sm text-on-surface-variant px-2 py-0.5 rounded bg-surface-container-highest border border-outline/40 flex items-center gap-1">
            <Cpu size={12} className="text-secondary" />
            <span>Llama-3.1-70b (NVIDIA NIM)</span>
          </span>
          <span className="font-label-sm px-2 py-0.5 rounded-full bg-tertiary/15 text-tertiary border border-tertiary/30 font-semibold">
            {matchPercent}% Confidence
          </span>
        </div>
      </div>

      <p
        data-testid="triage-rationale"
        className="font-body-md text-on-surface-variant leading-relaxed"
      >
        {item.reasoning}
      </p>

      {/* Metadata summary grid */}
      <div className="pt-2 border-t border-outline/40 grid grid-cols-2 gap-4 text-xs">
        <div>
          <span className="font-code-sm uppercase text-[10px] text-on-surface-variant opacity-75">
            Recommendation Style
          </span>
          <p className="font-medium text-on-surface capitalize mt-0.5">
            {formattedStyle}
          </p>
        </div>
        <div>
          <span className="font-code-sm uppercase text-[10px] text-on-surface-variant opacity-75">
            Topic Alignment
          </span>
          <p className="font-medium text-on-surface mt-0.5">
            {item.topic}
          </p>
        </div>
      </div>
    </section>
  );
};
