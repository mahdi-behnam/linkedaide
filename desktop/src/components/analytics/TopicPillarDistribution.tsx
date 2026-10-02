import React from "react";
import { TrendUp } from "../icons";

export interface TopicPillarMetric {
  name: string;
  tag: string;
  commentsCount: number;
  replyRate: string;
  impressions: string;
  resonanceScore: number;
  percentage: number;
}

export interface TopicPillarDistributionProps {
  topicPillars: TopicPillarMetric[];
}

export const TopicPillarDistribution: React.FC<TopicPillarDistributionProps> = ({
  topicPillars,
}) => {
  return (
    <div
      data-testid="topic-pillar-breakdown"
      className="rounded-lg border border-outline/70 bg-surface-container-lowest p-4 shadow-2xs lg:col-span-5 flex flex-col gap-2.5"
    >
      <div className="flex items-center justify-between border-b border-outline/50 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <TrendUp size={15} weight="bold" />
          </div>
          <h2 className="text-xs font-semibold text-on-surface">
            Topic Pillar Distribution
          </h2>
        </div>
        <span className="font-mono text-[10px] text-on-surface-variant">
          {topicPillars.length} Focus Areas
        </span>
      </div>

      <p className="text-[11px] text-on-surface-variant">
        Performance breakdown across target technological focus areas.
      </p>

      {topicPillars.length === 0 ? (
        <div
          data-testid="topic-pillar-empty"
          className="mt-2 flex h-52 flex-col items-center justify-center rounded-md border border-dashed border-outline bg-surface-container-low/40 p-5 text-center"
        >
          <TrendUp size={24} className="text-on-surface-variant/50 mb-1.5" />
          <p className="text-xs font-semibold text-on-surface">
            No topic metrics recorded yet. Metrics will appear once comments are executed.
          </p>
        </div>
      ) : (
        <div className="mt-1 space-y-2">
          {topicPillars.map((pillar) => (
            <div
              key={pillar.name}
              data-testid={`topic-pillar-${pillar.name}`}
              className="rounded-md border border-outline/50 bg-surface-container-low p-2.5 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-semibold text-on-surface">
                    {pillar.name}
                  </h3>
                  <span className="text-[10px] text-on-surface-variant">
                    {pillar.tag}
                  </span>
                </div>
                <div className="text-right">
                  <span className="font-mono text-xs font-bold text-tertiary tabular-nums">
                    {pillar.replyRate}
                  </span>
                  <p className="text-[10px] text-on-surface-variant/70">
                    reply rate
                  </p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="mt-2 h-1 w-full overflow-hidden rounded-xs bg-surface-container-highest">
                <div
                  className="h-full rounded-xs bg-primary transition-all duration-300"
                  style={{ width: `${pillar.percentage}%` }}
                />
              </div>

              <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-on-surface-variant tabular-nums">
                <span>{pillar.commentsCount} comments engaged</span>
                <span>{pillar.impressions} impressions</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
