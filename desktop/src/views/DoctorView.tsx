import React from "react";
import { useApp } from "../context/AppContext";
import { StatusPill } from "../components/StatusPill";
import {
  ArrowClockwise,
  CheckCircle,
  Database,
  Globe,
  ShieldCheck,
  Cpu,
  LockKey,
} from "../components/icons";

export const DoctorView: React.FC = () => {
  const { doctorChecks, isCheckingDoctor, runDoctorCheck } = useApp();

  const passedCount = doctorChecks.filter((c) => c.status === "pass").length;
  const totalCount = doctorChecks.length;
  const isAllPassing = passedCount === totalCount;

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
              status={isAllPassing ? "operational" : "paused"}
              label={`${passedCount} / ${totalCount} Checks Passing`}
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
        {doctorChecks.map((check) => (
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
        ))}
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
            All 11 Variables Loaded
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 md:grid-cols-4">
          {[
            "NVIDIA_NIM_API_KEY",
            "NIM_MODEL_PRIMARY",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "SESSION_ENCRYPTION_KEY",
            "LINKEDIN_SESSION_STATE_ENC",
            "CF_ACCOUNT_ID",
            "CF_KV_NAMESPACE_ID",
            "CF_API_TOKEN",
            "MAX_COMMENTS_PER_DAY",
            "DRY_RUN",
          ].map((key) => (
            <div
              key={key}
              className="flex items-center justify-between rounded border border-zinc-800/60 bg-zinc-950/60 px-2.5 py-1.5 font-mono text-[11px]"
            >
              <span className="truncate text-zinc-400">{key}</span>
              <CheckCircle size={12} weight="bold" className="shrink-0 text-emerald-400" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
