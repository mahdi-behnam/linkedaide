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

  const statusBadgeColor = isExhausted
    ? "text-error bg-error/10 border-error/20"
    : isWarning
      ? "text-amber-500 bg-amber-500/10 border-amber-500/20"
      : "text-tertiary bg-tertiary/10 border-tertiary/20";

  return (
    <div
      data-testid="quota-card"
      className={`group relative flex flex-col justify-between rounded-xl border border-outline bg-surface-container-lowest p-4 shadow-xs transition-all duration-150 hover:bg-surface-container-low hover:border-outline-variant active:scale-[0.99] ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {icon && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-outline bg-surface-container-low text-on-surface-variant transition-colors group-hover:text-primary group-hover:border-primary/30">
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
        <div className="flex items-center gap-1.5">
          <span
            className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${statusBadgeColor}`}
          >
            {statusLabel}
          </span>
          <span className="label-sm font-medium text-on-surface-variant">
            {remaining} left
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <div className="flex items-baseline justify-between font-mono">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-semibold tracking-tight text-on-surface">
              {executed}
            </span>
            <span className="label-md text-on-surface-variant">/ {max}</span>
          </div>
          <span className="label-md font-medium text-on-surface-variant">
            {percentage}%
          </span>
        </div>

        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
          <div
            role="progressbar"
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
            className={`h-full rounded-full transition-all duration-300 ${barColor}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
};
