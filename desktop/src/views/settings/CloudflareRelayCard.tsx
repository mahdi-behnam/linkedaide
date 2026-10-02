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
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center text-primary shrink-0">
            <Globe size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              Cloudflare Worker Edge Relay
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
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
            className="px-3 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 transition-colors font-medium text-[12px] flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer disabled:opacity-50"
          >
            <ArrowClockwise
              size={13}
              weight="bold"
              className={isTesting ? "animate-spin text-primary" : "text-on-surface-variant"}
            />
            <span>{isTesting ? "Testing..." : "Test Connection"}</span>
          </button>
        </div>
      </div>

      {testResult && (
        <div
          className={`flex items-center justify-between rounded-md border p-2.5 text-xs font-mono ${
            testResult.success
              ? "border-tertiary/30 bg-tertiary-container/15 text-tertiary"
              : "border-error/30 bg-error-container/20 text-error"
          }`}
        >
          <div className="flex items-center gap-2">
            {testResult.success ? (
              <CheckCircle size={15} weight="fill" />
            ) : (
              <WarningCircle size={15} weight="fill" />
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* Worker URL */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Worker API Endpoint URL
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-primary transition-all">
            <input
              type="text"
              data-testid="worker-url-input"
              value={workerUrl}
              onChange={(e) => onWorkerUrlChange(e.target.value)}
              placeholder="https://relay.your-subdomain.workers.dev"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
            <Globe size={15} className="text-on-surface-variant shrink-0 ml-2" />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Public gateway for receiving incoming approvals and dispatch pulses
          </span>
        </div>

        {/* API Secret */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Desktop API Secret (Bearer Token)
          </label>
          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-primary transition-all">
            <input
              type={showSecret ? "text" : "password"}
              data-testid="api-secret-input"
              value={apiSecret}
              onChange={(e) => onApiSecretChange(e.target.value)}
              placeholder="Enter DESKTOP_API_SECRET"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
            <button
              type="button"
              onClick={onToggleShowSecret}
              className="text-on-surface-variant hover:text-on-surface shrink-0 ml-2 cursor-pointer"
            >
              <Eye size={15} />
            </button>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Validated against Worker HMAC authentication header
          </span>
        </div>

        {/* KV Namespace */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Cloudflare KV Namespace
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30">
            <input
              type="text"
              readOnly
              value="hitl-state"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 cursor-default text-[12px]"
            />
            <span className="font-code-sm text-[11px] text-on-surface-variant ml-2 bg-surface-container px-1.5 py-0.5 rounded-[4px] font-mono border border-outline-variant/20">
              ENV.STATE_KV
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Direct key-value store identifier for active triage queues
          </span>
        </div>

        {/* Sync Frequency */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Edge Sync Frequency
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-primary">
            <select
              value={autoRefreshInterval}
              onChange={(e) => onIntervalChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              <option value={60}>Realtime Long-Polling (1 Minute)</option>
              <option value={120}>Active Polling (2 Minutes)</option>
              <option value={300}>Batched Interval (5 Minutes - Default)</option>
              <option value={600}>Passive Interval (10 Minutes)</option>
              <option value={900}>Conservative (15 Minutes)</option>
            </select>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Balances local CPU resource usage with multi-client response speed
          </span>
        </div>
      </div>
    </div>
  );
};
