import React from "react";
import { Globe, Lightning, CheckCircle, WarningCircle } from "../icons";

export interface EdgeDispatcherStatusProps {
  workerUrl?: string;
  workerStatus?: "connected" | "disconnected" | "checking";
  latencyMs?: number;
  executionMode?: "cloud" | "local";
  hasTelegramWebhook?: boolean;
}

export const EdgeDispatcherStatus: React.FC<EdgeDispatcherStatusProps> = ({
  workerUrl,
  workerStatus = "checking",
  latencyMs,
  executionMode = "cloud",
  hasTelegramWebhook,
}) => {
  const domain = React.useMemo(() => {
    if (!workerUrl) return "Not configured";
    try {
      const u = new URL(workerUrl);
      return u.hostname;
    } catch {
      return workerUrl.replace(/^https?:\/\//, "").split("/")[0] || "Not configured";
    }
  }, [workerUrl]);

  const isConnected = workerStatus === "connected";
  const isChecking = workerStatus === "checking";

  return (
    <section className="bg-surface-bright rounded-lg p-4 border border-outline shadow-2xs flex flex-col gap-3.5">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Globe size={14} weight="bold" />
          </div>
          <h2 className="text-sm font-semibold text-on-surface">Edge Dispatcher Status</h2>
        </div>
        <span className="text-[11px] px-1.5 py-0.2 rounded bg-surface-container-high text-on-surface-variant font-medium border border-outline font-sans">
          Cloudflare Worker
        </span>
      </div>

      {/* Overview Pane */}
      <div className="p-3.5 rounded-md bg-surface-container-low border border-outline flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-on-surface-variant uppercase tracking-wider">
            Worker Endpoint
          </span>
          <span className="text-[11px] font-mono text-on-surface font-medium truncate max-w-[200px]" title={workerUrl}>
            {domain}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-on-surface-variant">Live Edge Health</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? "bg-emerald-500 animate-pulse"
                  : isChecking
                  ? "bg-amber-500"
                  : "bg-error"
              }`}
            />
            <span className="text-xs font-medium text-on-surface">
              {isConnected
                ? latencyMs !== undefined
                  ? `Connected (${latencyMs}ms)`
                  : "Connected"
                : isChecking
                ? "Connecting..."
                : "Offline / Unreachable"}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-on-surface-variant">Execution Mode</span>
          <span className="text-xs font-medium text-on-surface inline-flex items-center gap-1">
            <Lightning size={12} className={executionMode === "cloud" ? "text-amber-500" : "text-primary"} />
            {executionMode === "cloud" ? "Cloud Runner (GitHub Actions)" : "Local Desktop Runner"}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-on-surface-variant">Telegram Relay Gateway</span>
          <div className="flex items-center gap-1 text-xs font-medium">
            {hasTelegramWebhook ? (
              <>
                <CheckCircle size={13} className="text-emerald-500" weight="fill" />
                <span className="text-emerald-500">Active &amp; Verified</span>
              </>
            ) : (
              <>
                <WarningCircle size={13} className="text-amber-500" weight="fill" />
                <span className="text-amber-500">Awaiting Webhook</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Footer Meta */}
      <div className="flex items-center justify-between text-xs text-on-surface-variant border-t border-outline/60 pt-2 font-sans">
        <span>State Replicas</span>
        <span className="font-mono text-[11px] text-on-surface font-medium">Cloudflare Workers KV</span>
      </div>
    </section>
  );
};
