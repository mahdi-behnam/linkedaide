import React from "react";
import {
  Globe,
  ArrowClockwise,
  Eye,
  CheckCircle,
  WarningCircle,
} from "../../components/icons";

interface CloudflareRelayCardProps {
  workerUrl: string;
  apiSecret: string;
  autoRefreshInterval: number;
  showSecret: boolean;
  onToggleShowSecret: () => void;
  onWorkerUrlChange: (url: string) => void;
  onApiSecretChange: (secret: string) => void;
  onIntervalChange: (interval: number) => void;
  isTesting: boolean;
  testResult: {
    success: boolean;
    latencyMs?: number;
    error?: string;
  } | null;
  onTestConnection: () => void;
}

export const CloudflareRelayCard: React.FC<CloudflareRelayCardProps> = ({
  workerUrl,
  apiSecret,
  autoRefreshInterval,
  showSecret,
  onToggleShowSecret,
  onWorkerUrlChange,
  onApiSecretChange,
  onIntervalChange,
  isTesting,
  testResult,
  onTestConnection,
}) => {
  return (
    <div className="flex flex-col gap-4 p-6 rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
            <Globe size={18} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface">
              Cloudflare Worker Edge Relay
            </h2>
            <p className="font-label-sm text-label-sm text-on-surface-variant">
              Bi-directional message relay &amp; persistent KV orchestration
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 self-end sm:self-auto">
          <button
            type="button"
            data-testid="test-connection-btn"
            disabled={isTesting}
            onClick={onTestConnection}
            className="px-3.5 py-1.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors font-body-strong text-body-strong flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer disabled:opacity-50"
          >
            <ArrowClockwise
              size={14}
              weight="bold"
              className={isTesting ? "animate-spin text-primary" : "text-on-surface-variant"}
            />
            <span>{isTesting ? "Testing..." : "Test Connection"}</span>
          </button>
        </div>
      </div>

      {testResult && (
        <div
          className={`flex items-center justify-between rounded-xl border p-3 text-xs font-mono ${
            testResult.success
              ? "border-tertiary/30 bg-tertiary-container/15 text-tertiary"
              : "border-error/30 bg-error-container/20 text-error"
          }`}
        >
          <div className="flex items-center gap-2">
            {testResult.success ? (
              <CheckCircle size={16} weight="fill" />
            ) : (
              <WarningCircle size={16} weight="fill" />
            )}
            <span>
              {testResult.success
                ? "Connected successfully to Cloudflare Worker API. Remember to click 'Save & Apply Settings' below to persist."
                : `Connection error: ${testResult.error}`}
            </span>
          </div>
          {testResult.latencyMs !== undefined && (
            <span className="font-semibold shrink-0 ml-2 font-mono">
              {testResult.latencyMs} ms
            </span>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-1">
        {/* Worker URL */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Worker API Endpoint URL
          </label>
          <div className="flex items-center px-3.5 py-2.5 rounded-xl bg-surface-container-low focus-within:bg-surface-container-lowest border border-surface-container-high focus-within:border-primary transition-all">
            <input
              type="text"
              data-testid="worker-url-input"
              value={workerUrl}
              onChange={(e) => onWorkerUrlChange(e.target.value)}
              placeholder="https://relay.your-subdomain.workers.dev"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant"
            />
            <Globe size={16} className="text-on-surface-variant shrink-0 ml-2" />
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Public gateway for receiving incoming approvals and dispatch pulses
          </span>
        </div>

        {/* API Secret */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Desktop API Secret (Bearer Token)
          </label>
          <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-surface-container-low focus-within:bg-surface-container-lowest border border-surface-container-high focus-within:border-primary transition-all">
            <input
              type={showSecret ? "text" : "password"}
              data-testid="api-secret-input"
              value={apiSecret}
              onChange={(e) => onApiSecretChange(e.target.value)}
              placeholder="Enter DESKTOP_API_SECRET"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant"
            />
            <button
              type="button"
              onClick={onToggleShowSecret}
              className="text-on-surface-variant hover:text-on-surface shrink-0 ml-2 cursor-pointer"
            >
              <Eye size={16} />
            </button>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Validated against Worker HMAC authentication header
          </span>
        </div>

        {/* KV Namespace */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Cloudflare KV Namespace
          </label>
          <div className="flex items-center px-3.5 py-2.5 rounded-xl bg-surface-container-low border border-surface-container-high">
            <input
              type="text"
              readOnly
              value="hitl-state"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 cursor-default"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 bg-surface-container px-2 py-0.5 rounded-md font-mono">
              ENV.STATE_KV
            </span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Direct key-value store identifier for active triage queues
          </span>
        </div>

        {/* Sync Frequency */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Edge Sync Frequency
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-primary">
            <select
              value={autoRefreshInterval}
              onChange={(e) => onIntervalChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0 cursor-pointer"
            >
              <option value={60}>Realtime Long-Polling (1 Minute)</option>
              <option value={120}>Active Polling (2 Minutes)</option>
              <option value={300}>Batched Interval (5 Minutes - Default)</option>
              <option value={600}>Passive Interval (10 Minutes)</option>
              <option value={900}>Conservative (15 Minutes)</option>
            </select>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Balances local CPU resource usage with multi-client response speed
          </span>
        </div>
      </div>
    </div>
  );
};
