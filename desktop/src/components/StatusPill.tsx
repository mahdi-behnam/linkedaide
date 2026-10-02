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
    ? "text-tertiary"
    : isWarning
      ? "text-amber-500"
      : "text-error";

  const sizeStyles =
    size === "sm"
      ? "text-[11px]"
      : "text-xs";

  return (
    <span
      data-testid="status-pill"
      data-status={status}
      className={`inline-flex items-center font-sans font-medium tracking-normal ${colorStyles} ${sizeStyles} ${className}`}
    >
      <span>{text}</span>
    </span>
  );
};
