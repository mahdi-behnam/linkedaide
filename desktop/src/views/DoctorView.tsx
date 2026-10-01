import React, { useState, useEffect, useMemo } from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import {
  ArrowClockwise,
  CheckCircle,
  WarningCircle,
  Database,
  Globe,
  ShieldCheck,
  Cpu,
  LockKey,
} from "../components/icons";
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

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "state":
        return <Database size={16} className="text-emerald-400" />;
      case "relay":
        return <Globe size={16} className="text-cyan-400" />;
      case "session":
        return <ShieldCheck size={16} className="text-emerald-400" />;
      case "llm":
        return <Cpu size={16} className="text-violet-400" />;
      case "safety":
        return <CheckCircle size={16} className="text-amber-400" />;
      case "env":
      default:
        return <LockKey size={16} className="text-zinc-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              System Diagnostics
            </h1>
            <StatusPill
              status={totalCount === 0 ? "paused" : isAllPassing ? "operational" : "tripped"}
              label={totalCount === 0 ? "Awaiting Execution" : `${passedCount} / ${totalCount} Checks Passing`}
              size="sm"
            />
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Graphical audit of agent runtime dependencies, Cloudflare KV edge store, Playwright auth, and NIM models.
          </p>
        </div>

        {/* Run Doctor Check Button */}
        <button
          type="button"
          data-testid="run-doctor-btn"
          disabled={isCheckingDoctor}
          onClick={runDoctorCheck}
          className={`flex items-center gap-2 rounded-md border px-4 py-2 text-xs font-semibold tracking-wide transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
            isCheckingDoctor
              ? "cursor-not-allowed border-zinc-800 bg-zinc-900/40 text-zinc-600"
              : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:border-emerald-500/50 hover:bg-emerald-500/20"
          }`}
        >
          <ArrowClockwise
            size={14}
            weight="bold"
            className={isCheckingDoctor ? "animate-spin text-emerald-400" : "text-emerald-400"}
          />
          <span>{isCheckingDoctor ? "Running Checks..." : "Run Doctor Checks"}</span>
        </button>
      </div>

      {/* Diagnostics Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {doctorChecks.length === 0 ? (
          <div className="col-span-full flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 p-8 text-center">
            <p className="text-xs text-zinc-400">No diagnostic checks performed yet</p>
            <p className="mt-1 text-[11px] text-zinc-600">
              Click &apos;Run Doctor Checks&apos; above to verify runtime dependencies, session health, and cloud connectivity.
            </p>
          </div>
        ) : (
          doctorChecks.map((check) => (
            <div
              key={check.id}
              data-testid={`doctor-check-${check.id}`}
              className="flex flex-col justify-between rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 transition-colors hover:border-zinc-700/80"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950">
                      {getCategoryIcon(check.category)}
                    </div>
                    <div>
                      <h3 className="text-xs font-semibold text-zinc-200">
                        {check.title}
                      </h3>
                      <span className="font-mono text-[10px] text-zinc-500 uppercase">
                        Category: {check.category}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {check.latencyMs !== undefined && (
                      <span className="font-mono text-[11px] text-zinc-400">
                        {check.latencyMs}ms
                      </span>
                    )}
                    <StatusPill status={check.status} size="sm" />
                  </div>
                </div>

                <p className="mt-3 text-xs leading-relaxed text-zinc-400">
                  {check.detail}
                </p>
              </div>

              {check.recommendation && (
                <div className="mt-3 rounded border border-amber-500/20 bg-amber-500/10 p-2 text-[11px] text-amber-300">
                  <span className="font-semibold">Recommendation: </span>
                  {check.recommendation}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Environment Security & Keys Card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
          <div className="flex items-center gap-2">
            <LockKey size={16} className="text-emerald-400" />
            <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              Environment Secrets Audit
            </h3>
          </div>
          <span className="font-mono text-[11px] text-emerald-400">
            {loadedVarsCount} / {envAuditList.length} Variables Configured
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 md:grid-cols-4">
          {envAuditList.map((item) => (
            <div
              key={item.key}
              className="flex items-center justify-between rounded border border-zinc-800/60 bg-zinc-950/60 px-2.5 py-1.5 font-mono text-[11px]"
            >
              <span className="truncate text-zinc-400">{item.key}</span>
              {item.loaded ? (
                <CheckCircle size={12} weight="bold" className="shrink-0 text-emerald-400" />
              ) : (
                <WarningCircle size={12} className="shrink-0 text-amber-500" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
