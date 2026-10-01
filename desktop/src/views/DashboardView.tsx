import React from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import { QuotaCard } from "../components/QuotaCard";
import {
  Play,
  Pause,
  Stethoscope,
  ArrowClockwise,
  ShieldCheck,
  Cpu,
  Database,
  Inbox,
  ClockCounterClockwise,
  CheckCircle,
} from "../components/icons";

export const DashboardView: React.FC = () => {
  const {
    systemStatus,
    isPaused,
    togglePause,
    telemetry,
    quota,
    isScouting,
    triggerScout,
    isCheckingDoctor,
    runDoctorCheck,
    setCurrentTab,
    lastTriggerMessage,
  } = useApp();

  const pendingCount = telemetry?.pendingCount ?? 0;

  return (
    <div className="space-y-6">
      {/* Header & Command Center Title */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Command Center
            </h1>
            <StatusPill status={systemStatus} size="sm" />
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Real-time telemetry, daily rate limit burn-down, and autonomous scout controls.
          </p>
        </div>

        {/* Quick Actions Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Trigger Scout Now */}
          <button
            type="button"
            data-testid="trigger-scout-btn"
            disabled={isScouting || isPaused}
            onClick={triggerScout}
            className={`flex items-center gap-2 rounded-md border px-3.5 py-1.5 text-xs font-semibold tracking-wide transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
              isScouting || isPaused
                ? "cursor-not-allowed border-zinc-800 bg-zinc-900/40 text-zinc-600"
                : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:border-emerald-500/50 hover:bg-emerald-500/20"
            }`}
          >
            <ArrowClockwise
              size={14}
              weight="bold"
              className={isScouting ? "animate-spin text-emerald-400" : "text-emerald-400"}
            />
            <span>{isScouting ? "Scouting..." : "Trigger Scout Now"}</span>
          </button>

          {/* Health Check */}
          <button
            type="button"
            data-testid="health-check-btn"
            disabled={isCheckingDoctor}
            onClick={() => {
              runDoctorCheck();
              setCurrentTab("doctor");
            }}
            className="flex items-center gap-2 rounded-md border border-zinc-700/80 bg-zinc-800/80 px-3.5 py-1.5 text-xs font-medium text-zinc-200 transition-all duration-150 hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100 active:translate-y-[1px] active:scale-[0.98]"
          >
            <Stethoscope size={14} className="text-violet-400" />
            <span>Health Check</span>
          </button>

          {/* Toggle Pause */}
          <button
            type="button"
            data-testid="toggle-pause-btn"
            onClick={togglePause}
            className={`flex items-center gap-2 rounded-md border px-3.5 py-1.5 text-xs font-semibold tracking-wide uppercase transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
              isPaused
                ? "border-amber-500/30 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25"
                : "border-zinc-700/80 bg-zinc-800/80 text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100"
            }`}
          >
            {isPaused ? (
              <>
                <Play size={13} weight="fill" className="text-amber-400" />
                <span>Resume Agent</span>
              </>
            ) : (
              <>
                <Pause size={13} weight="fill" className="text-zinc-400" />
                <span>Pause Agent</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Activity Alert / Feedback Toast */}
      {lastTriggerMessage && (
        <div
          data-testid="trigger-feedback"
          className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-900/80 px-4 py-2 text-xs text-zinc-300"
        >
          <div className="flex items-center gap-2">
            <CheckCircle size={14} className="text-emerald-400" />
            <span>{lastTriggerMessage}</span>
          </div>
          <span className="font-mono text-[10px] text-zinc-500">Live Event</span>
        </div>
      )}

      {/* Telemetry Cockpit Strip */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Persistence Backend */}
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 text-emerald-400">
            <Database size={18} />
          </div>
          <div className="overflow-hidden">
            <p className="text-[11px] font-medium text-zinc-400">State Persistence</p>
            <p className="truncate text-xs font-semibold text-zinc-200">
              {telemetry.kvBackend}
            </p>
          </div>
        </div>

        {/* NIM Model */}
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 text-violet-400">
            <Cpu size={18} />
          </div>
          <div className="overflow-hidden">
            <p className="text-[11px] font-medium text-zinc-400">NVIDIA NIM Model</p>
            <p className="truncate font-mono text-xs font-semibold text-zinc-200">
              {telemetry.nimModel ? telemetry.nimModel.replace(/^meta\//, "") : "Not configured"}
            </p>
          </div>
        </div>

        {/* LinkedIn Session */}
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 ${telemetry.sessionValid ? "text-emerald-400" : "text-amber-400"}`}>
            <ShieldCheck size={18} />
          </div>
          <div className="overflow-hidden">
            <p className="text-[11px] font-medium text-zinc-400">LinkedIn Session</p>
            <p className={`truncate text-xs font-semibold ${telemetry.sessionValid ? "text-emerald-400" : "text-amber-400"}`}>
              {telemetry.sessionValid ? "Active & Encrypted" : "No Active Session"}
            </p>
          </div>
        </div>

        {/* Last Scan Time */}
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950 text-amber-400">
            <ClockCounterClockwise size={18} />
          </div>
          <div className="overflow-hidden">
            <p className="text-[11px] font-medium text-zinc-400">Last Scout Run</p>
            <p className="truncate text-xs font-semibold text-zinc-200">
              {telemetry.lastScanAt || "Never"}
            </p>
          </div>
        </div>
      </div>

      {/* Daily Quota Burn-Down Cards */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Daily Rate Limit Burn-Down
          </h2>
          <span className="font-mono text-[11px] text-zinc-500">
            Resets 00:00 UTC
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <QuotaCard
            title="Comments Executed"
            executed={quota.commentsExecuted}
            max={quota.commentsMax}
            unit="comments"
            subtitle={`${quota.commentsMax - quota.commentsExecuted} remaining today`}
          />
          <QuotaCard
            title="Posts Published"
            executed={quota.postsExecuted}
            max={quota.postsMax}
            unit="posts"
            subtitle={`${quota.postsMax - quota.postsExecuted} remaining today`}
          />
          <QuotaCard
            title="Suggestions Reviewed"
            executed={quota.suggestionsSent}
            max={quota.suggestionsMax}
            unit="suggestions"
            subtitle={`${quota.suggestionsMax - quota.suggestionsSent} quota remaining`}
          />
        </div>
      </div>

      {/* Pending Approvals Quick Preview Card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-amber-500/30 bg-amber-500/10 text-amber-400">
              <Inbox size={18} weight="bold" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-zinc-200">
                Pending Approval Queue
              </h3>
              <p className="text-xs text-zinc-400">
                Draft actions awaiting human decision via Telegram or Desktop Cockpit.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setCurrentTab("queue")}
            className="flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-200 transition-colors hover:border-zinc-600 hover:text-zinc-100 active:scale-[0.98]"
          >
            <span>Review Queue</span>
            <span className="rounded bg-amber-500/20 px-1.5 py-0.2 font-mono text-[10px] text-amber-300">
              {pendingCount}
            </span>
          </button>
        </div>

        {pendingCount > 0 ? (
          <div className="mt-4 rounded-md border border-zinc-800/80 bg-zinc-950/70 p-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-400 uppercase">
                  pending
                </span>
                <span className="font-medium text-zinc-300">
                  {pendingCount} {pendingCount === 1 ? "action" : "actions"} awaiting review
                </span>
              </div>
              <span className="font-mono text-[11px] text-zinc-400">Queue active</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-zinc-400">
              Autonomous scout has queued candidate drafts awaiting human verification before edge execution.
            </p>
          </div>
        ) : (
          <div className="mt-4 flex flex-col items-center justify-center rounded-md border border-dashed border-zinc-800/80 py-6 text-center">
            <Inbox size={22} className="text-zinc-600 mb-1.5" />
            <p className="text-xs font-medium text-zinc-400">No pending approvals in queue</p>
            <p className="mt-0.5 text-[11px] text-zinc-500">
              All scout suggestions reviewed. New candidates will appear here as feeds are scanned.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
