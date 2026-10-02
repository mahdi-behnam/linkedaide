import React from "react";
import { Cpu } from "@phosphor-icons/react";
import { PendingItem } from "./QueueTriageCard";

interface QueueRationaleSectionProps {
  item: PendingItem;
}

export const QueueRationaleSection: React.FC<QueueRationaleSectionProps> = ({ item }) => {
  const matchPercent = Math.round(item.confidence * 100);
  const formattedStyle = item.engagementStyle.replace(/_/g, " ");

  return (
    <section className="p-3.5 rounded-lg bg-surface-container-low border border-outline/50 flex flex-col gap-2.5 shadow-2xs">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1.5">
          <Cpu size={14} className="text-primary" />
          <span className="text-xs font-semibold text-on-surface">
            Synthesis &amp; Rationale
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-[11px] text-on-surface-variant font-sans">
            Llama-3.1-70b (NVIDIA NIM)
          </span>
          <span className="text-[11px] text-tertiary font-medium tabular-nums">
            · {matchPercent}% Confidence
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
