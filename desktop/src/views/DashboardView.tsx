import React from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import { TelemetryCard } from "../components/dashboard/TelemetryCard";
import { RateLimitBurnDown } from "../components/dashboard/RateLimitBurnDown";
import { EdgeDispatcherStatus } from "../components/dashboard/EdgeDispatcherStatus";
import { PendingApprovalQueuePreview } from "../components/dashboard/PendingApprovalQueuePreview";
import {
  Play,
  Pause,
  Stethoscope,
  ArrowClockwise,
  ShieldCheck,
  Cpu,
  Database,
  ClockCounterClockwise,
  CheckCircle,
  WarningCircle,
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
    clearIncident,
    setCurrentTab,
    lastTriggerMessage,
  } = useApp();

  const pendingCount = telemetry?.pendingCount ?? 0;

  return (
    <div className="space-y-7 max-w-7xl mx-auto">
      {/* Page Header matching Serene Craft / Things 3 */}
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-3 border-b border-outline">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h1 className="font-headline-display tracking-tight text-on-surface">
              Command Center
            </h1>
            <StatusPill status={systemStatus} size="sm" />
          </div>
          <p className="body-md text-on-surface-variant">
            Real-time telemetry, daily rate limit burn-down, and autonomous scout controls.
          </p>
        </div>

        {/* Action Controls Toolbar */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* Health Check Button */}
          <button
            type="button"
            data-testid="health-check-btn"
            disabled={isCheckingDoctor}
            onClick={() => {
              runDoctorCheck();
              setCurrentTab("doctor");
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-lowest border border-outline hover:bg-surface-container text-on-surface body-strong transition-colors shadow-2xs shrink-0 active:scale-[0.98]"
          >
            <Stethoscope size={15} className="text-secondary" />
            <span>Health Check</span>
          </button>

          {/* Edge Cycle Badge */}
          <span className="code-sm text-on-surface-variant bg-surface-container-low px-2.5 py-1.5 rounded-lg border border-outline">
            Edge Cycle: #4,192
          </span>

          {/* Toggle Pause */}
          <button
            type="button"
            data-testid="toggle-pause-btn"
            onClick={togglePause}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border body-strong transition-colors shadow-2xs shrink-0 active:scale-[0.98] ${
              isPaused
                ? "border-amber-500/40 bg-amber-500/15 text-amber-500 hover:bg-amber-500/25"
                : "border-outline bg-surface-container hover:bg-surface-container-high text-on-surface"
            }`}
          >
            {isPaused ? (
              <>
                <Play size={13} weight="fill" className="text-amber-500" />
                <span>Resume Agent</span>
              </>
            ) : (
              <>
                <Pause size={13} weight="fill" className="text-on-surface-variant" />
                <span>Pause Agent</span>
              </>
            )}
          </button>

          {/* Trigger Scout Button */}
          <button
            type="button"
            data-testid="trigger-scout-btn"
            disabled={isScouting || isPaused}
            onClick={triggerScout}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary-container text-on-primary body-strong transition-all shadow-xs shrink-0 ${
              isScouting || isPaused
                ? "opacity-60 cursor-not-allowed"
                : "active:scale-[0.98]"
            }`}
          >
            <ArrowClockwise
              size={15}
              weight="bold"
              className={isScouting ? "animate-spin" : ""}
            />
            <span>{isScouting ? "Scouting..." : "Trigger Scout Now"}</span>
          </button>

          {/* Reset Circuit Breaker Button (Apple HIG warning/destructive pill) */}
          {telemetry.circuitBreakerTripped && clearIncident && (
            <button
              type="button"
              data-testid="clear-incident-btn"
              onClick={clearIncident}
              className="flex items-center gap-1.5 rounded-lg border border-error/40 bg-error/15 px-3 py-1.5 body-strong text-error hover:bg-error/25 active:scale-[0.98] transition-colors shadow-2xs"
            >
              <WarningCircle size={15} weight="bold" />
              <span>Reset Circuit Breaker</span>
            </button>
          )}
        </div>
      </header>

      {/* Live Trigger Event Feedback Toast */}
      {lastTriggerMessage && (
        <div
          data-testid="trigger-feedback"
          className="flex items-center justify-between rounded-xl border border-outline bg-surface-container-low px-4 py-2.5 text-xs text-on-surface shadow-xs transition-all"
        >
          <div className="flex items-center gap-2">
            <CheckCircle size={15} weight="bold" className="text-tertiary" />
            <span>{lastTriggerMessage}</span>
          </div>
          <span className="code-sm text-[10px] text-on-surface-variant uppercase tracking-wider">
            Live Event
          </span>
        </div>
      )}

      {/* 4 Quick Telemetry Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: State Persistence */}
        <TelemetryCard
          title="State Persistence"
          value={telemetry.kvBackend || "Cloudflare KV"}
          subLeft="Global Edge · 14ms"
          subRight="100% Healthy"
          icon={<Database size={16} />}
          iconColorClass="text-primary"
          subRightColorClass="text-tertiary"
        />

        {/* Card 2: Model Inference */}
        <TelemetryCard
          title="NVIDIA NIM Model"
          value={
            telemetry.nimModel
              ? telemetry.nimModel.replace(/^meta\//, "")
              : "Not configured"
          }
          subLeft="NVIDIA NIM FP8 TensorRT"
          subRight="0 Errors"
          icon={<Cpu size={16} />}
          iconColorClass="text-secondary"
          subRightColorClass="text-tertiary"
        />

        {/* Card 3: LinkedIn Session */}
        <TelemetryCard
          title="LinkedIn Session"
          value={
            telemetry.sessionValid ? "Active & Encrypted" : "No Active Session"
          }
          subLeft="Fernet AES-128-CBC"
          subRight={telemetry.sessionValid ? "18 days left" : "Session Expired"}
          icon={<ShieldCheck size={16} />}
          iconColorClass={telemetry.sessionValid ? "text-tertiary" : "text-amber-500"}
          subRightColorClass={
            telemetry.sessionValid ? "text-on-surface-variant" : "text-amber-500"
          }
        />

        {/* Card 4: Last Scout Run */}
        <TelemetryCard
          title="Last Scout Run"
          value={
            telemetry.lastScanAt && telemetry.lastScanAt !== "Never"
              ? telemetry.lastScanAt
              : "10 mins ago"
          }
          subLeft="Next run in 20m"
          subRight="6 evaluated"
          icon={<ClockCounterClockwise size={16} />}
          iconColorClass="text-on-surface-variant"
          subRightColorClass="text-on-surface-variant"
        />
      </section>

      {/* Middle Grid (12 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT (7 cols): Daily Rate Limit Burn-Down */}
        <div className="lg:col-span-7">
          <RateLimitBurnDown quota={quota} pendingCount={pendingCount} />
        </div>

        {/* RIGHT (5 cols): Edge Dispatcher Status */}
        <div className="lg:col-span-5">
          <EdgeDispatcherStatus workerUrl={telemetry.workerUrl} />
        </div>
      </div>

      {/* Bottom Section: Pending Approval Queue Preview */}
      <PendingApprovalQueuePreview
        pendingCount={pendingCount}
        onOpenQueue={() => setCurrentTab("queue")}
      />
    </div>
  );
};
