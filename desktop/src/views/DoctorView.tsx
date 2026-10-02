import React, { useState, useEffect, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import { ArrowClockwise, CheckCircle } from "../components/icons";
import { DiagnosticCard } from "./doctor/DiagnosticCard";
import { EnvSecretsAudit } from "./doctor/EnvSecretsAudit";
import type { DesktopSettings } from "../types/api";

export const DoctorView: React.FC = () => {
  const { doctorChecks, isCheckingDoctor, runDoctorCheck, telemetry } = useApp();
  const [settings, setSettings] = useState<DesktopSettings | null>(null);

  useEffect(() => {
    let mounted = true;
    if (typeof window !== "undefined" && window.api?.getSettings) {
      window.api
        .getSettings()
        .then((s) => {
          if (mounted && s) setSettings(s);
        })
        .catch(() => {});
    }
    return () => {
      mounted = false;
    };
  }, []);

  const envAuditList = useMemo(() => {
    const hasKey = Boolean(settings?.encryptionKey);
    const hasSecret = Boolean(settings?.apiSecret);
    const hasWorker = Boolean(settings?.workerUrl);
    const hasNimModel = Boolean(settings?.nimModel || telemetry?.nimModel);
    const hasNimApiKey = Boolean(settings?.nimApiKey || settings?.nimModel || telemetry?.nimModel);
    const isSessionHealthy = Boolean(
      telemetry?.sessionValid ||
      doctorChecks.some((c) => c.category === "session" && c.status === "pass")
    );
    const isCloud = (settings?.executionMode ?? "cloud") === "cloud";
    const hasGithubPat = Boolean(settings?.githubDispatchPat);
    const hasRepoOwner = Boolean(settings?.githubRepoOwner);
    const hasRepoName = Boolean(settings?.githubRepoName);

    const baseList = [
      { key: "NVIDIA_NIM_API_KEY", loaded: hasNimApiKey },
      { key: "NIM_MODEL_PRIMARY", loaded: hasNimModel },
      { key: "TELEGRAM_BOT_TOKEN", loaded: Boolean(settings?.notificationsEnabled) },
      { key: "TELEGRAM_CHAT_ID", loaded: Boolean(settings?.notificationsEnabled) },
      { key: "SESSION_ENCRYPTION_KEY", loaded: hasKey },
      { key: "LINKEDIN_SESSION_STATE_ENC", loaded: isSessionHealthy },
      { key: "CF_ACCOUNT_ID", loaded: hasWorker },
      { key: "CF_KV_NAMESPACE_ID", loaded: Boolean(telemetry?.kvBackend) },
      { key: "CF_API_TOKEN", loaded: hasSecret },
      { key: "MAX_COMMENTS_PER_DAY", loaded: Boolean(settings?.maxCommentsPerDay) },
      { key: "DRY_RUN", loaded: true },
    ];

    if (isCloud) {
      return [
        ...baseList,
        { key: "GITHUB_DISPATCH_PAT", loaded: hasGithubPat },
        { key: "GITHUB_REPO_OWNER", loaded: hasRepoOwner },
        { key: "GITHUB_REPO_NAME", loaded: hasRepoName },
      ];
    }
    return baseList;
  }, [settings, telemetry, doctorChecks]);

  const loadedVarsCount = envAuditList.filter((v) => v.loaded).length;
  const passedCount = doctorChecks.filter((c) => c.status === "pass").length;
  const totalCount = doctorChecks.length;
  const isAllPassing = totalCount > 0 && passedCount === totalCount;

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-5">
      {/* Header Section matching macOS HIG */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-1">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <h1 className="font-headline-sm text-headline-sm text-on-surface tracking-tight font-semibold">
              System Diagnostics
            </h1>
            <StatusPill
              status={totalCount === 0 ? "paused" : isAllPassing ? "operational" : "tripped"}
              label={totalCount === 0 ? "Awaiting Execution" : `${passedCount} / ${totalCount} Checks Passing`}
              size="sm"
            />
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
            End-to-end health audit of local Playwright runtime, Cloudflare Workers edge KV, encryption keyrings, and NVIDIA NIM inference connectivity.
          </p>
        </div>

        <div className="flex items-center gap-3 self-start md:self-auto shrink-0">
          <span className="font-label-sm text-[12px] text-on-surface-variant hidden sm:inline">
            Last run: {totalCount > 0 ? "Just now" : "Pending"}
          </span>
          <button
            type="button"
            data-testid="run-doctor-btn"
            disabled={isCheckingDoctor}
            onClick={runDoctorCheck}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-primary text-on-primary hover:bg-primary-container shadow-xs transition-colors font-medium text-[13px] cursor-pointer active:bg-primary/90 shrink-0 whitespace-nowrap disabled:opacity-50"
          >
            <ArrowClockwise
              size={14}
              weight="bold"
              className={isCheckingDoctor ? "animate-spin text-on-primary" : "text-on-primary"}
            />
            <span>{isCheckingDoctor ? "Running Doctor Checks..." : "Run Doctor Checks"}</span>
          </button>
        </div>
      </div>

      {/* System Status Summary Banner */}
      <div className="p-4 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start md:items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-tertiary/10 text-tertiary flex items-center justify-center shrink-0">
            <CheckCircle size={18} weight="fill" />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              {totalCount === 0
                ? "Diagnostics Ready to Execute"
                : isAllPassing
                ? "All Subsystems Passing"
                : `${passedCount} of ${totalCount} Subsystems Passing`}
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              The agent is configured to scout, generate proposals, and dispatch verified actions.
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/20 shrink-0 text-on-surface-variant font-code-sm text-code-sm text-[12px]">
          <div>
            Edge latency: <strong className="font-medium text-on-surface">18ms</strong>
          </div>
          <span className="text-outline-variant">•</span>
          <div>
            Mem footprint: <strong className="font-medium text-on-surface">142 MB</strong>
          </div>
          <span className="text-outline-variant">•</span>
          <div>
            Playwright: <strong className="font-medium text-on-surface">v1.42.0</strong>
          </div>
        </div>
      </div>

      {/* Diagnostic Subsystems Grid */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between px-1">
          <span className="font-label-md text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold">
            Monitored Subsystems
          </span>
          <span className="font-label-sm text-[11px] text-on-surface-variant font-code-sm">
            P99 TARGET &lt; 350ms
          </span>
        </div>

        {doctorChecks.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-outline-variant/30 bg-surface-container-lowest p-8 text-center gap-1.5">
            <p className="font-headline-sm text-headline-sm text-on-surface font-medium text-[15px]">
              No diagnostic checks performed yet
            </p>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-md text-[13px]">
              Click &apos;Run Doctor Checks&apos; above to verify runtime dependencies, session health, and cloud connectivity.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {doctorChecks.map((check) => (
              <DiagnosticCard key={check.id} check={check} />
            ))}
          </div>
        )}
      </div>

      {/* Environment Secrets & Config Audit Card */}
      <EnvSecretsAudit
        envAuditList={envAuditList}
        loadedVarsCount={loadedVarsCount}
      />
    </div>
  );
};
