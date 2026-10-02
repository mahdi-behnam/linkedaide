import React from "react";

export interface QuotaCardProps {
  title: string;
  executed: number;
  max: number;
  unit?: string;
  icon?: React.ReactNode;
  subtitle?: string;
  className?: string;
}

export const QuotaCard: React.FC<QuotaCardProps> = ({
  title,
  executed,
  max,
  unit = "actions",
  icon,
  subtitle,
  className = "",
}) => {
  const percentage = max > 0 ? Math.min(Math.round((executed / max) * 100), 100) : 0;
  const remaining = Math.max(max - executed, 0);

  const isExhausted = executed >= max;
  const isWarning = percentage >= 75 && !isExhausted;

  const barColor = isExhausted
    ? "bg-error"
    : isWarning
      ? "bg-amber-500"
      : "bg-primary";

  const statusLabel = isExhausted
    ? "Exhausted"
    : isWarning
      ? "High Usage"
      : "Nominal";


  return (
    <div
      data-testid="quota-card"
      className={`group relative flex flex-col justify-between rounded-lg border border-outline bg-surface-container-lowest p-3.5 shadow-2xs transition-colors hover:bg-surface-container-low/60 ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {icon && (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-outline bg-surface-container-low text-on-surface-variant transition-colors group-hover:text-primary">
              {icon}
            </div>
          )}
          <div>
            <h4 className="body-strong tracking-tight text-on-surface transition-colors">
              {title}
            </h4>
            <p className="label-sm text-on-surface-variant">
              {subtitle || `${remaining} ${unit} remaining today`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`font-sans text-[11px] font-medium ${
              isExhausted ? "text-error" : isWarning ? "text-amber-500" : "text-tertiary"
            }`}
          >
            {statusLabel}
          </span>
          <span className="label-sm font-medium text-on-surface-variant tabular-nums">
            {remaining} left
          </span>
        </div>
      </div>

      <div className="mt-3.5 space-y-1.5">
        <div className="flex items-baseline justify-between font-sans tabular-nums">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-semibold tracking-tight text-on-surface">
              {executed}
            </span>
            <span className="label-md text-on-surface-variant">/ {max}</span>
          </div>
          <span className="label-md font-medium text-on-surface-variant">
            {percentage}%
          </span>
        </div>

        <div className="relative h-1.5 w-full overflow-hidden rounded-xs bg-surface-container-highest">
          <div
            role="progressbar"
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
            className={`h-full rounded-xs transition-all duration-300 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
};
