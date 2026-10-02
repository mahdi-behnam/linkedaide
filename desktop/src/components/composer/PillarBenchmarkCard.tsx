import React from "react";
import { ChartLineUp } from "../icons";

interface PillarBenchmarkCardProps {
  topicPillar: string;
}

export const PillarBenchmarkCard: React.FC<PillarBenchmarkCardProps> = ({
  topicPillar,
}) => {
  return (
    <div className="p-4 rounded-lg bg-surface-container-lowest border border-outline/70 shadow-2xs flex flex-col gap-2.5">
      <div className="flex items-center justify-between pb-1 border-b border-outline/50">
        <div className="flex items-center gap-2">
          <ChartLineUp size={16} className="text-secondary" />
          <span className="text-xs font-semibold text-on-surface">
            Pillar Benchmark
          </span>
        </div>
        <span className="text-[11px] text-tertiary font-medium">
          +42% Reach
        </span>
      </div>

      <p className="text-xs text-on-surface-variant leading-relaxed">
        Carousel posts in{" "}
        <strong className="text-on-surface font-medium">{topicPillar}</strong>{" "}
        outperform single images with 3.8x bookmark and repost velocity in your network.
      </p>

      <div className="pt-2 border-t border-outline/50 flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-on-surface-variant text-[11px]">
          <span>Audience Alignment</span>
          <span className="font-mono text-[11px] text-on-surface font-medium tabular-nums">
            96% Match
          </span>
        </div>
        <div className="w-full h-1 rounded-xs bg-surface-container overflow-hidden">
          <div className="h-full bg-primary rounded-xs w-[96%]" />
        </div>
        <div className="flex items-center justify-between text-on-surface-variant pt-0.5 text-[11px]">
          <span>Historical Avg Reach</span>
          <span className="font-mono text-[11px] font-medium text-on-surface tabular-nums">
            18.4k impressions
          </span>
        </div>
      </div>
    </div>
  );
};
