import React from "react";
import { Stethoscope } from "../../components/icons";

interface SystemDiagnosticsCardProps {
  logLevel?: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  onLogLevelChange: (level: "DEBUG" | "INFO" | "WARNING" | "ERROR") => void;
}

export const SystemDiagnosticsCard: React.FC<SystemDiagnosticsCardProps> = ({
  logLevel = "INFO",
  onLogLevelChange,
}) => {
  const levels: Array<{
    id: "DEBUG" | "INFO" | "WARNING" | "ERROR";
    label: string;
    description: string;
  }> = [
    {
      id: "DEBUG",
      label: "DEBUG",
      description: "Detailed trace telemetry including DOM selectors, raw model responses, and payload dumps.",
    },
    {
      id: "INFO",
      label: "INFO (Default)",
      description: "Standard operational milestones: feed discoveries, triage decisions, and execution outcomes.",
    },
    {
      id: "WARNING",
      label: "WARNING",
      description: "Only alerts for recoverable faults, selector drifts, rate throttling, and retry events.",
    },
    {
      id: "ERROR",
      label: "ERROR",
      description: "Critical failures only: challenge detections, fatal API errors, and emergency circuit trips.",
    },
  ];

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex items-center gap-2.5 pb-1 border-b border-surface-container-high">
        <div className="w-8 h-8 rounded-md bg-emerald-500/10 flex items-center justify-center text-emerald-500 shrink-0">
          <Stethoscope size={16} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            System Diagnostics &amp; Telemetry
          </h2>
          <p className="font-label-sm text-[11px] text-on-surface-variant">
            Logging verbosity, terminal output filters, and runtime diagnostics
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2 pt-0.5">
        <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
          Logging Verbosity Level
        </label>

        {/* Apple-style segmented control */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1 p-1 rounded-lg bg-surface-container-low border border-outline-variant/30">
          {levels.map((item) => {
            const isActive = logLevel === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onLogLevelChange(item.id)}
                className={`py-1.5 px-2.5 rounded-md text-[12px] font-medium transition-all text-center cursor-pointer ${
                  isActive
                    ? "bg-surface-container-highest text-on-surface shadow-xs font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container/50"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        <span className="font-label-sm text-[11px] text-on-surface-variant">
          {levels.find((l) => l.id === logLevel)?.description ||
            "Controls telemetry detail in diagnostic terminal outputs and runtime logs."}
        </span>
      </div>
    </div>
  );
};
