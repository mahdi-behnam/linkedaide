import React from "react";
import { ShieldCheck, LockKey } from "../../components/icons";

interface SafetyGuardrailsCardProps {
  maxCommentsPerDay: number;
  maxPostsPerDay: number;
  maxConnectionsPerDay: number;
  maxSuggestionsPerRun: number;
  actionTtlHours: number;
  autoRefreshInterval: number;
  headless: boolean;
  dryRun?: boolean;
  onCommentsChange: (val: number) => void;
  onPostsChange: (val: number) => void;
  onConnectionsChange: (val: number) => void;
  onSuggestionsChange: (val: number) => void;
  onTtlChange: (val: number) => void;
  onIntervalChange: (val: number) => void;
  onHeadlessChange: (val: boolean) => void;
  onDryRunChange?: (val: boolean) => void;
}

export const SafetyGuardrailsCard: React.FC<SafetyGuardrailsCardProps> = ({
  maxCommentsPerDay,
  maxPostsPerDay,
  maxConnectionsPerDay,
  maxSuggestionsPerRun,
  actionTtlHours,
  autoRefreshInterval,
  headless,
  dryRun = false,
  onCommentsChange,
  onPostsChange,
  onConnectionsChange,
  onSuggestionsChange,
  onTtlChange,
  onIntervalChange,
  onHeadlessChange,
  onDryRunChange,
}) => {
  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex items-center gap-2.5 pb-1 border-b border-surface-container-high">
        <div className="w-8 h-8 rounded-md bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
          <ShieldCheck size={16} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Autonomous Safety Guardrails &amp; Quotas
          </h2>
          <p className="font-label-sm text-[11px] text-on-surface-variant">
            Rate limits, freshness windows, and duplicate mitigation
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-0.5">
        {/* Poll Interval */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Poll Interval
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <select
              value={autoRefreshInterval}
              onChange={(e) => onIntervalChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              <option value={60}>1 Minute</option>
              <option value={120}>2 Minutes</option>
              <option value={300}>5 Minutes</option>
              <option value={600}>10 Minutes (Default)</option>
              <option value={900}>15 Minutes</option>
            </select>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Frequency of local telemetry and pending approval sync
          </span>
        </div>

        {/* Max Comments / Day */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Max Comments / Day
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={50}
              value={maxCommentsPerDay}
              onChange={(e) => onCommentsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0 text-[11px]">
              max/24h
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Hard ceiling to prevent account automated flagging
          </span>
        </div>

        {/* Max Posts / Day */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Max Posts / Day
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={10}
              value={maxPostsPerDay}
              onChange={(e) => onPostsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0 text-[11px]">
              max/24h
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Recommended cadence for technical thought leadership
          </span>
        </div>

        {/* Max Connections / Day */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="max-connections-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Max Connections / Day
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <input
              id="max-connections-input"
              aria-label="Max Connections / Day"
              type="number"
              min={1}
              max={30}
              value={maxConnectionsPerDay}
              onChange={(e) => onConnectionsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0 text-[11px]">
              max/24h
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Daily connection outreach ceiling
          </span>
        </div>

        {/* Max Suggestions Per Run */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Max Suggestions / Run
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={30}
              value={maxSuggestionsPerRun}
              onChange={(e) => onSuggestionsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0 text-[11px]">
              items
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Scouting batch candidate cap per execution
          </span>
        </div>

        {/* Approval TTL */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Approval TTL (Hours)
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={72}
              value={actionTtlHours}
              onChange={(e) => onTtlChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0 text-[11px]">
              hours
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Drafts older than configured hours automatically expire
          </span>
        </div>

        {/* Idempotency Window */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            Idempotency Window
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30">
            <input
              type="text"
              readOnly
              value="48 Hours"
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-default"
            />
            <LockKey size={15} className="text-tertiary ml-2 shrink-0" />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Guarantees zero duplicate replies to the same post
          </span>
        </div>
      </div>

      {/* Simulation / Dry Run Mode */}
      <div className="pt-2.5 border-t border-surface-container-high">
        <div className="flex items-center justify-between p-3 rounded-md bg-surface-container-low border border-outline-variant/30">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-on-surface text-[13px] flex items-center gap-2">
              <span>Dry-Run Simulation Mode</span>
              {dryRun && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-500 font-semibold border border-amber-500/20">
                  SIMULATION ACTIVE
                </span>
              )}
            </span>
            <span className="font-body-md text-on-surface-variant text-[12px]">
              Scout feeds, evaluate posts, and generate Telegram proposals without executing real LinkedIn actions (reactions, comments, or posts).
            </span>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={Boolean(dryRun)}
            aria-label="Dry-Run Simulation Mode"
            onClick={() => onDryRunChange?.(!dryRun)}
            className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
              dryRun ? "bg-amber-500" : "bg-surface-container-highest"
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                dryRun ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Headless Browser Option */}
      <div className="pt-2.5 border-t border-surface-container-high">
        <label className="flex items-center gap-2.5 p-2 rounded-md hover:bg-surface-container-low/60 transition-colors cursor-pointer">
          <input
            type="checkbox"
            checked={headless}
            onChange={(e) => onHeadlessChange(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-outline text-primary focus:ring-primary cursor-pointer accent-primary"
          />
          <div className="flex flex-col gap-0.5">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Headless Playwright Browser (Local Mode)
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              Run Chromium in background without opening visible browser window on execution.
            </span>
          </div>
        </label>
      </div>
    </div>
  );
};
