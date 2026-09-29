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
    ? "bg-rose-500"
    : isWarning
      ? "bg-amber-500"
      : "bg-emerald-500";

  const statusLabel = isExhausted
    ? "Exhausted"
    : isWarning
      ? "High Usage"
      : "Nominal";

  const statusColor = isExhausted
    ? "text-rose-400 bg-rose-500/10 border-rose-500/20"
    : isWarning
      ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
      : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";

  return (
    <div
      data-testid="quota-card"
      className={`group relative flex flex-col justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-all duration-150 hover:border-zinc-700/80 hover:bg-zinc-900/80 active:scale-[0.99] ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {icon && (
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 text-zinc-300 transition-colors group-hover:border-zinc-700 group-hover:text-zinc-100">
              {icon}
            </div>
          )}
          <div>
            <h4 className="text-xs font-medium tracking-tight text-zinc-300 group-hover:text-zinc-100">
              {title}
            </h4>
            <p className="text-[11px] text-zinc-500">
              {subtitle || `${remaining} ${unit} remaining today`}
            </p>
          </div>
        </div>
        <span
          className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${statusColor}`}
        >
          {statusLabel}
        </span>
      </div>

      <div className="mt-4 space-y-2">
        <div className="flex items-baseline justify-between font-mono">
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold tracking-tight text-zinc-100">
              {executed}
            </span>
            <span className="text-xs text-zinc-500">/ {max}</span>
          </div>
          <span className="text-xs font-medium text-zinc-400">
            {percentage}%
          </span>
        </div>

        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-zinc-800/80">
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
