import React from "react";
import { TrendUp } from "../icons";

export interface KpiMetricCardProps {
  testId: string;
  title: string;
  value: string;
  trendText?: string;
  hasData: boolean;
  subtitle: string;
  icon: React.ReactNode;
  iconColorClass?: string;
}

export const KpiMetricCard: React.FC<KpiMetricCardProps> = ({
  testId,
  title,
  value,
  trendText,
  hasData,
  subtitle,
  icon,
  iconColorClass = "text-primary",
}) => {
  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-outline/70 bg-surface-container-lowest p-3.5 shadow-2xs flex flex-col justify-between"
    >
      <div className="flex items-center justify-between pb-2">
        <span className="text-[11px] font-medium text-on-surface-variant">
          {title}
        </span>
        <div
          className={`flex h-6 w-6 items-center justify-center rounded-md border border-outline/50 bg-surface-container-low ${iconColorClass}`}
        >
          {icon}
        </div>
      </div>
      <div>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold tracking-tight text-on-surface tabular-nums">
            {value}
          </span>
          {hasData && trendText ? (
            <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-tertiary">
              <TrendUp size={11} weight="bold" />
              {trendText}
            </span>
          ) : (
            <span className="text-[11px] text-on-surface-variant/60 font-mono">--</span>
          )}
        </div>
        <p className="mt-1 text-[11px] text-on-surface-variant truncate">
          {subtitle}
        </p>
      </div>
    </div>
  );
};
