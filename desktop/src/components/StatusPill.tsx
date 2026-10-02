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
    ? "bg-tertiary/10 text-tertiary border-tertiary/20"
    : isWarning
      ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
      : "bg-error/10 text-error border-error/20";

  const dotStyles = isHealthy
    ? "bg-tertiary"
    : isWarning
      ? "bg-amber-500"
      : "bg-error";

  const sizeStyles =
    size === "sm"
      ? "px-2 py-0.5 text-[11px] gap-1.5"
      : "px-2.5 py-1 text-xs font-medium gap-1.5";

  return (
    <span
      data-testid="status-pill"
      data-status={status}
      className={`inline-flex items-center rounded-md border font-sans tracking-normal transition-colors ${colorStyles} ${sizeStyles} ${className}`}
    >
      {showDot && (
        <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${dotStyles}`} />
      )}
      <span>{text}</span>
    </span>
  );
};
