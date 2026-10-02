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
      className="rounded-xl border border-outline bg-surface-container-lowest p-5 shadow-2xs lg:col-span-5 flex flex-col gap-3"
    >
      <div className="flex items-center justify-between border-b border-outline pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <TrendUp size={16} weight="bold" />
          </div>
          <h2 className="headline-sm text-on-surface">
            Topic Pillar Distribution
          </h2>
        </div>
        <span className="code-sm text-on-surface-variant">
          {topicPillars.length} Focus Areas
        </span>
      </div>

      <p className="body-md text-on-surface-variant">
        Performance breakdown across target technological focus areas.
      </p>

      {topicPillars.length === 0 ? (
        <div
          data-testid="topic-pillar-empty"
          className="mt-2 flex h-60 flex-col items-center justify-center rounded-xl border border-dashed border-outline bg-surface-container-low/40 p-6 text-center"
        >
          <TrendUp size={28} className="text-on-surface-variant/50 mb-2" />
          <p className="body-strong text-on-surface">
            No topic metrics recorded yet. Metrics will appear once comments are executed.
          </p>
        </div>
      ) : (
        <div className="mt-2 space-y-3">
          {topicPillars.map((pillar) => (
            <div
              key={pillar.name}
              data-testid={`topic-pillar-${pillar.name}`}
              className="rounded-xl border border-outline bg-surface-container-low p-3.5 transition-all hover:border-outline-variant"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="body-strong text-on-surface">
                    {pillar.name}
                  </h3>
                  <span className="code-sm text-on-surface-variant">
                    {pillar.tag}
                  </span>
                </div>
                <div className="text-right">
                  <span className="code-sm font-bold text-tertiary">
                    {pillar.replyRate}
                  </span>
                  <p className="code-sm text-on-surface-variant/70">
                    reply rate
                  </p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
                  style={{ width: `${pillar.percentage}%` }}
                />
              </div>

              <div className="mt-2 flex items-center justify-between code-sm text-on-surface-variant">
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
