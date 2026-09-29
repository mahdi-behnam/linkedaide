import React from "react";
import { SystemStatusType } from "../types";

export interface StatusPillProps {
  status: SystemStatusType | "pass" | "warn" | "fail";
  label?: string;
  size?: "sm" | "md";
  showDot?: boolean;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  status,
  label,
  size = "md",
  showDot = true,
  className = "",
}) => {
  const isHealthy = status === "operational" || status === "pass";
  const isWarning = status === "paused" || status === "warn";

  const defaultLabel = (() => {
    switch (status) {
      case "operational":
        return "Operational";
      case "paused":
        return "Paused";
      case "tripped":
        return "Breaker Tripped";
      case "pass":
        return "PASS";
      case "warn":
        return "WARN";
      case "fail":
        return "FAIL";
    }
  })();

  const text = label || defaultLabel;

  const colorStyles = isHealthy
    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
    : isWarning
      ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
      : "bg-rose-500/10 text-rose-400 border-rose-500/20";

  const dotStyles = isHealthy
    ? "bg-emerald-400"
    : isWarning
      ? "bg-amber-400"
      : "bg-rose-400";

  const sizeStyles =
    size === "sm"
      ? "px-2 py-0.5 text-xs gap-1.5"
      : "px-2.5 py-1 text-xs font-medium gap-2";

  return (
    <span
      data-testid="status-pill"
      data-status={status}
      className={`inline-flex items-center rounded-full border font-mono tracking-tight transition-colors ${colorStyles} ${sizeStyles} ${className}`}
    >
      {showDot && (
        <span className="relative flex h-2 w-2">
          {isHealthy && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          )}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${dotStyles}`} />
        </span>
      )}
      <span>{text}</span>
    </span>
  );
};
