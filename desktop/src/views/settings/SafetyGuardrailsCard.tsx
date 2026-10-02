import React from "react";
import { ShieldCheck, LockKey } from "../../components/icons";

interface SafetyGuardrailsCardProps {
  maxCommentsPerDay: number;
  maxPostsPerDay: number;
  maxSuggestionsPerRun: number;
  actionTtlHours: number;
  autoRefreshInterval: number;
  headless: boolean;
  onCommentsChange: (val: number) => void;
  onPostsChange: (val: number) => void;
  onSuggestionsChange: (val: number) => void;
  onTtlChange: (val: number) => void;
  onIntervalChange: (val: number) => void;
  onHeadlessChange: (val: boolean) => void;
}

export const SafetyGuardrailsCard: React.FC<SafetyGuardrailsCardProps> = ({
  maxCommentsPerDay,
  maxPostsPerDay,
  maxSuggestionsPerRun,
  actionTtlHours,
  autoRefreshInterval,
  headless,
  onCommentsChange,
  onPostsChange,
  onSuggestionsChange,
  onTtlChange,
  onIntervalChange,
  onHeadlessChange,
}) => {
  return (
    <div className="flex flex-col gap-4 p-6 rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high">
      <div className="flex items-center gap-3 pb-1 border-b border-surface-container-high">
        <div className="w-9 h-9 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500 shrink-0">
          <ShieldCheck size={18} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">
            Autonomous Safety Guardrails &amp; Quotas
          </h2>
          <p className="font-label-sm text-label-sm text-on-surface-variant">
            Rate limits, freshness windows, and duplicate mitigation
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-1">
        {/* Poll Interval */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Poll Interval
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-amber-500">
            <select
              value={autoRefreshInterval}
              onChange={(e) => onIntervalChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0 cursor-pointer"
            >
              <option value={60}>1 Minute (High Aggression)</option>
              <option value={120}>2 Minutes (Active)</option>
              <option value={300}>5 Minutes (Default Recommended)</option>
              <option value={600}>10 Minutes (Low Footprint)</option>
              <option value={900}>15 Minutes (Passive)</option>
            </select>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Frequency of background timeline scouting
          </span>
        </div>

        {/* Max Comments / Day */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Max Comments / Day
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={50}
              value={maxCommentsPerDay}
              onChange={(e) => onCommentsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0">
              max/24h
            </span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Hard ceiling to prevent account automated flagging
          </span>
        </div>

        {/* Max Posts / Day */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Max Posts / Day
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={10}
              value={maxPostsPerDay}
              onChange={(e) => onPostsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0">
              max/24h
            </span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Recommended cadence for technical thought leadership
          </span>
        </div>

        {/* Max Suggestions Per Run */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Max Suggestions / Run
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={30}
              value={maxSuggestionsPerRun}
              onChange={(e) => onSuggestionsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0">
              items
            </span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Scouting batch candidate cap per execution
          </span>
        </div>

        {/* Approval TTL */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Approval TTL (Hours)
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus-within:border-amber-500">
            <input
              type="number"
              min={1}
              max={72}
              value={actionTtlHours}
              onChange={(e) => onTtlChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0"
            />
            <span className="font-code-sm text-code-sm text-on-surface-variant ml-2 shrink-0">
              hours
            </span>
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Drafts older than configured hours automatically expire
          </span>
        </div>

        {/* Idempotency Window */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface">
            Idempotency Window
          </label>
          <div className="flex items-center px-3.5 py-2 rounded-xl bg-surface-container-low border border-surface-container-high">
            <input
              type="text"
              readOnly
              value="48 Hours"
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface p-0 focus:ring-0 cursor-default"
            />
            <LockKey size={16} className="text-tertiary ml-2 shrink-0" />
          </div>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Guarantees zero duplicate replies to the same post
          </span>
        </div>
      </div>

      {/* Headless Browser Option */}
      <div className="pt-3 border-t border-surface-container-high">
        <label className="flex items-center gap-3 p-3 rounded-xl hover:bg-surface-container-low/60 transition-colors cursor-pointer">
          <input
            type="checkbox"
            checked={headless}
            onChange={(e) => onHeadlessChange(e.target.checked)}
            className="w-4 h-4 rounded border-outline text-primary focus:ring-primary cursor-pointer accent-primary"
          />
          <div className="flex flex-col gap-0.5">
            <span className="font-body-strong text-body-strong text-on-surface">
              Headless Playwright Browser (Local Mode)
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant">
              Run Chromium in background without opening visible browser window on execution.
            </span>
          </div>
        </label>
      </div>
    </div>
  );
};
