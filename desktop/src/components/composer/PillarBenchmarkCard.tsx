import React from "react";
import { ChartLineUp } from "../icons";

interface PillarBenchmarkCardProps {
  topicPillar: string;
}

export const PillarBenchmarkCard: React.FC<PillarBenchmarkCardProps> = ({
  topicPillar,
}) => {
  return (
    <div className="p-5 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-3">
      <div className="flex items-center justify-between pb-1 border-b border-surface-container-high/60">
        <div className="flex items-center gap-2">
          <ChartLineUp size={18} className="text-secondary" />
          <span className="font-headline-sm text-headline-sm text-on-surface">
            Pillar Benchmark
          </span>
        </div>
        <span className="font-label-sm text-label-sm px-2.5 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
          +42% Reach
        </span>
      </div>

      <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
        Carousel posts in{" "}
        <strong className="text-on-surface font-medium">{topicPillar}</strong>{" "}
        outperform single images with 3.8x bookmark and repost velocity in your network.
      </p>

      <div className="pt-2 border-t border-surface-container-high/60 flex flex-col gap-2">
        <div className="flex items-center justify-between text-on-surface-variant">
          <span className="font-label-sm text-label-sm">Audience Alignment</span>
          <span className="font-code-sm text-code-sm text-on-surface font-medium">
            96% High-Signal
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-surface-container overflow-hidden">
          <div className="h-full bg-primary rounded-full w-[96%]" />
        </div>
        <div className="flex items-center justify-between text-on-surface-variant pt-1">
          <span className="font-label-sm text-label-sm">Historical Avg Reach</span>
          <span className="font-code-sm text-code-sm font-semibold text-on-surface">
            18.4k impressions
          </span>
        </div>
      </div>
    </div>
  );
};
