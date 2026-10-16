import React, { useState, useEffect, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { TelemetryCard } from "../components/dashboard/TelemetryCard";
import { RateLimitBurnDown } from "../components/dashboard/RateLimitBurnDown";
import { EdgeDispatcherStatus } from "../components/dashboard/EdgeDispatcherStatus";
import {
  PendingApprovalQueuePreview,
  PreviewPendingItem,
} from "../components/dashboard/PendingApprovalQueuePreview";
import {
  ArrowClockwise,
  ShieldCheck,
  Cpu,
  ClockCounterClockwise,
  CheckCircle,
  WarningCircle,
} from "../components/icons";

export const DashboardView: React.FC = () => {
  const {
    isPaused,
    telemetry,
    quota,
    isScouting,
    triggerScout,
    clearIncident,
    setCurrentTab,
    lastTriggerMessage,
    formatTimeAgo,
    doctorChecks,
    pendingItems,
  } = useApp();

  const [settings, setSettings] = useState<any>(null);

  useEffect(() => {
    let mounted = true;
    if (typeof window !== "undefined" && window.api?.getSettings) {
      window.api.getSettings().then((s) => {
        if (mounted && s) setSettings(s);
      });
    }
    return () => {
      mounted = false;
    };
  }, []);

  const pendingCount = telemetry?.pendingCount ?? 0;

  const previewItems: PreviewPendingItem[] = useMemo(() => {
    return (pendingItems || []).map((p: any) => {
      const isPost = (p.action_type || "").toLowerCase().includes("post");
      const author = p.author_name || (isPost ? "You (Draft)" : "LinkedIn Member");
      const initials =
        author
          .split(" ")
          .map((n: string) => n[0])
          .join("")
          .slice(0, 2)
          .toUpperCase() || "LI";
      return {
        id: p.item_id || p.id,
        author,
        initials,
        avatarBg: isPost ? "bg-primary/15" : "bg-secondary/15",
        avatarText: isPost ? "text-primary" : "text-secondary",
        headline:
          p.author_headline ||
          (isPost ? "Original Post Suggestion" : "LinkedIn Member"),
        verified: false,
        type: isPost ? "Original Post" : "Comment",
        confidence: p.confidence
          ? `${Math.round(p.confidence * 100)}% Confidence`
          : "85% Confidence",
        timeAgo: p.created_at ? formatTimeAgo(p.created_at) : "Pending",
        quote: p.post_excerpt ? `“${p.post_excerpt.slice(0, 100)}...”` : undefined,
        draft: p.draft_text || (p.reaction_type ? `Reaction: ${p.reaction_type}` : ""),
        primaryAction: isPost ? "Edit Draft" : "Approve",
        secondaryAction: isPost ? "Dismiss" : "Reject",
      };
    });
  }, [pendingItems, formatTimeAgo]);

  return (
    <div className="space-y-7 max-w-7xl mx-auto">
      {/* Page Header matching Serene Craft / Things 3 */}
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-3 border-b border-outline">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <h1 className="font-headline-display tracking-tight text-on-surface">
              Command Center
            </h1>
          </div>
          <p className="body-md text-on-surface-variant">
            Real-time telemetry, daily rate limit burn-down, and autonomous scout controls.
          </p>
        </div>

        {/* Action Controls Toolbar */}
        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* Trigger Scout Button */}
          <button
            type="button"
            data-testid="trigger-scout-btn"
            disabled={isScouting || isPaused}
            onClick={triggerScout}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md bg-primary hover:bg-primary-container text-on-primary text-xs font-medium transition-colors shadow-2xs shrink-0 ${
              isScouting || isPaused
                ? "opacity-60 cursor-not-allowed"
                : "active:scale-[0.99]"
            }`}
          >
            <ArrowClockwise
              size={13}
              weight="bold"
              className={isScouting ? "animate-spin" : ""}
            />
            <span>{isScouting ? "Scouting..." : "Trigger Scout Now"}</span>
          </button>

          {/* Reset Circuit Breaker Button (Apple HIG warning/destructive button) */}
          {telemetry.circuitBreakerTripped && clearIncident && (
            <button
              type="button"
              data-testid="clear-incident-btn"
              onClick={clearIncident}
              className="flex items-center gap-1.5 rounded-md border border-error/40 bg-error/10 px-2.5 py-1 text-xs font-medium text-error hover:bg-error/20 active:scale-[0.99] transition-colors shadow-2xs"
            >
              <WarningCircle size={14} weight="bold" />
              <span>Reset Circuit Breaker</span>
            </button>
          )}
        </div>
      </header>

      {/* Live Trigger Event Feedback Toast */}
      {lastTriggerMessage && (
        <div
          data-testid="trigger-feedback"
          className="flex items-center justify-between rounded-lg border border-outline bg-surface-container-low px-3 py-2 text-xs text-on-surface shadow-2xs transition-all"
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

      {/* 3 Quick Telemetry Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Card 1: Model Inference */}
        <TelemetryCard
          title="NVIDIA NIM Model"
          value={
            telemetry.nimModel
              ? telemetry.nimModel.replace(/^meta\//, "")
              : "Not configured"
          }
          subLeft="api.nim.nvidia.com"
          subRight={telemetry.nimModel ? "Active" : "Unset"}
          icon={<Cpu size={16} />}
          iconColorClass="text-secondary"
          subRightColorClass={telemetry.nimModel ? "text-tertiary" : "text-on-surface-variant"}
        />

        {/* Card 2: LinkedIn Session */}
        <TelemetryCard
          title="LinkedIn Session"
          value={
            telemetry.sessionValid ? "Active & Encrypted" : "No Active Session"
          }
          subLeft="Fernet AES-128-CBC"
          subRight={telemetry.sessionValid ? "Valid" : "Session Expired"}
          icon={<ShieldCheck size={16} />}
          iconColorClass={telemetry.sessionValid ? "text-tertiary" : "text-amber-500"}
          subRightColorClass={
            telemetry.sessionValid ? "text-on-surface-variant" : "text-amber-500"
          }
        />

        {/* Card 3: Last Scout Run */}
        <TelemetryCard
          title="Last Scout Run"
          value={
            telemetry.lastScanAt && telemetry.lastScanAt !== "Never"
              ? telemetry.lastScanAt
              : "No recent runs"
          }
          subLeft="Automated Schedule"
          subRight={telemetry.circuitBreakerTripped ? "Circuit Paused" : "Active"}
          icon={<ClockCounterClockwise size={16} />}
          iconColorClass="text-on-surface-variant"
          subRightColorClass={
            telemetry.circuitBreakerTripped ? "text-error" : "text-on-surface-variant"
          }
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
          <EdgeDispatcherStatus
            workerUrl={telemetry.workerUrl}
            workerStatus={telemetry.workerStatus}
            latencyMs={doctorChecks?.find((c) => c.id === "relay-health" || c.id === "kv-access")?.latencyMs}
            executionMode={settings?.executionMode ?? "cloud"}
            hasTelegramWebhook={Boolean(telemetry.workerUrl && telemetry.workerStatus === "connected")}
          />
        </div>
      </div>

      {/* Bottom Section: Pending Approval Queue Preview */}
      <PendingApprovalQueuePreview
        pendingCount={pendingCount}
        items={previewItems}
        onOpenQueue={() => setCurrentTab("queue")}
      />
    </div>
  );
};
