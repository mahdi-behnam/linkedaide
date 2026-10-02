import React from "react";
import { Globe, ShieldCheck, Check } from "../../components/icons";

interface ExecutionModeCardProps {
  executionMode: "cloud" | "local";
  onChange: (mode: "cloud" | "local") => void;
}

export const ExecutionModeCard: React.FC<ExecutionModeCardProps> = ({
  executionMode,
  onChange,
}) => {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Execution Architecture Mode
          </h2>
          <span className="font-label-sm text-[11px] text-on-surface-variant font-normal">
            Primary engine dispatch model
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Option A: Cloud Remote Runner */}
        <label
          className={`relative flex flex-col p-4 rounded-lg border transition-colors cursor-pointer group ${
            executionMode === "cloud"
              ? "bg-surface-container-lowest border-primary shadow-xs"
              : "bg-surface-container-low/70 border-outline-variant/30 hover:bg-surface-container-low"
          }`}
          id="card-mode-cloud"
        >
          <input
            type="radio"
            name="executionMode"
            value="cloud"
            checked={executionMode === "cloud"}
            onChange={() => onChange("cloud")}
            className="sr-only"
            aria-label="Cloud Remote Runner"
          />
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${
                  executionMode === "cloud"
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                {executionMode === "cloud" ? (
                  <Check size={13} weight="bold" />
                ) : (
                  <Globe size={13} />
                )}
              </div>
              <div className="flex flex-col">
                <span className="font-body-strong text-body-strong text-on-surface font-semibold text-[13px]">
                  Cloud Remote Runner
                </span>
                <span className="font-code-sm text-code-sm text-on-surface-variant text-[11px]">
                  Cloudflare KV + GitHub Actions
                </span>
              </div>
            </div>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant pl-7.5 pr-1 leading-relaxed text-[12px]">
            Orchestrates state via Cloudflare Workers KV and triggers GitHub Actions dispatch runners. Zero local machine uptime required.
          </p>
        </label>

        {/* Option B: Local Playwright Runner */}
        <label
          className={`relative flex flex-col p-4 rounded-lg border transition-colors cursor-pointer group ${
            executionMode === "local"
              ? "bg-surface-container-lowest border-primary shadow-xs"
              : "bg-surface-container-low/70 border-outline-variant/30 hover:bg-surface-container-low"
          }`}
          id="card-mode-local"
        >
          <input
            type="radio"
            name="executionMode"
            value="local"
            checked={executionMode === "local"}
            onChange={() => onChange("local")}
            className="sr-only"
            aria-label="Local Playwright Runner"
          />
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${
                  executionMode === "local"
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                {executionMode === "local" ? (
                  <Check size={13} weight="bold" />
                ) : (
                  <ShieldCheck size={13} />
                )}
              </div>
              <div className="flex flex-col">
                <span className="font-body-strong text-body-strong text-on-surface font-semibold text-[13px]">
                  Local Playwright Runner
                </span>
                <span className="font-code-sm text-code-sm text-on-surface-variant text-[11px]">
                  Local Python Engine + Headless Chrome
                </span>
              </div>
            </div>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant pl-7.5 pr-1 leading-relaxed text-[12px]">
            Executes browser actions directly on this machine using local Playwright and Python agent CLI. Ideal for desktop-first control and debugging.
          </p>
        </label>
      </div>
    </div>
  );
};
