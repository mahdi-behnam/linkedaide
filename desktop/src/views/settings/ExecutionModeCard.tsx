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
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">
            Execution Architecture Mode
          </h2>
          <span className="font-label-sm text-label-sm text-on-surface-variant font-normal">
            Primary engine dispatch model
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Option A: Cloud Remote Runner */}
        <label
          className={`relative flex flex-col p-5 rounded-2xl border transition-all cursor-pointer group shadow-xs ${
            executionMode === "cloud"
              ? "bg-surface-container-lowest border-primary shadow-sm"
              : "bg-surface-container-low/70 border-surface-container-high hover:bg-surface-container-low"
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
          <div className="flex items-start justify-between gap-3 mb-2.5">
            <div className="flex items-center gap-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-transform group-hover:scale-105 ${
                  executionMode === "cloud"
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                {executionMode === "cloud" ? (
                  <Check size={14} weight="bold" />
                ) : (
                  <Globe size={14} />
                )}
              </div>
              <div className="flex flex-col">
                <span className="font-body-strong text-body-strong text-on-surface font-semibold">
                  Cloud Remote Runner
                </span>
                <span className="font-code-sm text-code-sm text-on-surface-variant">
                  Cloudflare KV + GitHub Actions
                </span>
              </div>
            </div>
            {executionMode === "cloud" && (
              <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary font-label-sm text-label-sm font-semibold tracking-wide">
                Active Mode
              </span>
            )}
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant pl-9 pr-1 leading-relaxed">
            Orchestrates state via Cloudflare Workers KV and triggers GitHub Actions dispatch runners. Zero local machine uptime required.
          </p>
        </label>

        {/* Option B: Local Playwright Runner */}
        <label
          className={`relative flex flex-col p-5 rounded-2xl border transition-all cursor-pointer group shadow-xs ${
            executionMode === "local"
              ? "bg-surface-container-lowest border-primary shadow-sm"
              : "bg-surface-container-low/70 border-surface-container-high hover:bg-surface-container-low"
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
          <div className="flex items-start justify-between gap-3 mb-2.5">
            <div className="flex items-center gap-3">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-transform group-hover:scale-105 ${
                  executionMode === "local"
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                {executionMode === "local" ? (
                  <Check size={14} weight="bold" />
                ) : (
                  <ShieldCheck size={14} />
                )}
              </div>
              <div className="flex flex-col">
                <span className="font-body-strong text-body-strong text-on-surface font-semibold">
                  Local Playwright Runner
                </span>
                <span className="font-code-sm text-code-sm text-on-surface-variant">
                  Local Python Engine + Headless Chrome
                </span>
              </div>
            </div>
            {executionMode === "local" && (
              <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary font-label-sm text-label-sm font-semibold tracking-wide">
                Active Mode
              </span>
            )}
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant pl-9 pr-1 leading-relaxed">
            Executes browser actions directly on this machine using local Playwright and Python agent CLI. Ideal for desktop-first control and debugging.
          </p>
        </label>
      </div>
    </div>
  );
};
