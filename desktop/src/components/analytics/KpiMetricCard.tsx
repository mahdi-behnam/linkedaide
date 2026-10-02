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
      className="rounded-xl border border-outline bg-surface-container-lowest p-4 shadow-2xs transition-all hover:border-outline-variant flex flex-col justify-between"
    >
      <div className="flex items-center justify-between pb-2">
        <span className="code-sm font-medium text-on-surface-variant">
          {title}
        </span>
        <div
          className={`flex h-7 w-7 items-center justify-center rounded-lg border border-outline bg-surface-container-low ${iconColorClass}`}
        >
          {icon}
        </div>
      </div>
      <div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-on-surface">
            {value}
          </span>
          {hasData && trendText ? (
            <span className="inline-flex items-center gap-0.5 code-sm font-semibold text-tertiary">
              <TrendUp size={12} weight="bold" />
              {trendText}
            </span>
          ) : (
            <span className="code-sm text-on-surface-variant/60">--</span>
          )}
        </div>
        <p className="mt-1 text-[11px] text-on-surface-variant truncate">
          {subtitle}
        </p>
      </div>
    </div>
  );
};
