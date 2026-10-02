import React from "react";
import { StatusPill } from "../../components/StatusPill";
import {
  Database,
  Globe,
  ShieldCheck,
  Cpu,
  CheckCircle,
  LockKey,
  Lightning,
} from "../../components/icons";
import type { DoctorCheck } from "../../types";

interface DiagnosticCardProps {
  check: DoctorCheck;
}

export const DiagnosticCard: React.FC<DiagnosticCardProps> = ({ check }) => {
  const getCategoryMeta = (category: string, title: string) => {
    switch (category) {
      case "state":
        return {
          icon: <Database size={16} className="text-emerald-500" />,
          label: "State Persistence",
          footer: [
            { label: "Read", val: "14ms" },
            { label: "Write", val: "42ms" },
            { label: "Namespace", val: "hitl-state" },
            { label: "Mode", val: "Edge-replicated" },
          ],
        };
      case "relay":
        if (title.includes("GitHub")) {
          return {
            icon: <Lightning size={16} className="text-amber-500" />,
            label: "Cloud Runner",
            footer: [
              { label: "Platform", val: "GitHub Actions" },
              { label: "Target", val: "dispatch" },
              { label: "Workflows", val: "scout / execute" },
            ],
          };
        }
        return {
          icon: <Globe size={16} className="text-primary" />,
          label: "Human Interaction",
          footer: [
            { label: "Relay", val: "Workers Edge" },
            { label: "Auth", val: "HMAC-SHA256" },
            { label: "Drops", val: "0" },
          ],
        };
      case "session":
        return {
          icon: <ShieldCheck size={16} className="text-emerald-500" />,
          label: "Session & Auth",
          footer: [
            { label: "Auth Cookie", val: "li_at" },
            { label: "CSRF", val: "JSESSIONID" },
            { label: "Security Challenge", val: "None" },
          ],
        };
      case "llm":
        return {
          icon: <Cpu size={16} className="text-secondary" />,
          label: "LLM Inference",
          footer: [
            { label: "Host", val: "api.nim.nvidia.com" },
            { label: "Schema", val: "Strict Pydantic" },
            { label: "TTFT", val: "190ms" },
          ],
        };
      case "safety":
        return {
          icon: <CheckCircle size={16} className="text-amber-500" />,
          label: "Safety Invariants",
          footer: [
            { label: "Bot Flagging", val: "0" },
            { label: "Anti-Entropy", val: "Active" },
            { label: "Idempotency", val: "Strict" },
          ],
        };
      case "env":
      default:
        return {
          icon: <LockKey size={16} className="text-on-surface-variant" />,
          label: "System & Config",
          footer: [
            { label: "Schema", val: "pydantic-settings" },
            { label: "Enclave", val: "Keychain" },
            { label: "Audit", val: "Cryptographic" },
          ],
        };
    }
  };

  const meta = getCategoryMeta(check.category, check.title);

  return (
    <div
      data-testid={`doctor-check-${check.id}`}
      className="p-4 rounded-lg bg-surface-container-lowest border border-outline-variant/30 transition-all flex flex-col justify-between gap-3.5"
    >
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <span className="font-label-sm text-[11px] text-on-surface-variant uppercase tracking-wide font-medium">
            {meta.label}
          </span>
          <div className="flex items-center gap-2">
            {check.latencyMs !== undefined && (
              <span className="font-code-sm text-code-sm text-on-surface-variant font-mono text-[11px]">
                {check.latencyMs}ms
              </span>
            )}
            <StatusPill status={check.status} size="sm" />
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-md bg-surface-container shrink-0">
              {meta.icon}
            </span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              {check.title}
            </h3>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1.5 leading-relaxed text-[12px]">
            {check.detail}
          </p>
        </div>
      </div>

      {check.recommendation && (
        <div className="rounded-md border border-amber-500/25 bg-amber-500/10 p-2.5 text-xs text-amber-500">
          <span className="font-semibold">Recommendation: </span>
          {check.recommendation}
        </div>
      )}

      {/* Sub-strip with contextual metrics */}
      <div className="pt-2 bg-surface-container-low/60 -mx-4 -mb-4 px-4 py-2 rounded-b-lg border-t border-outline-variant/20 flex flex-wrap items-center gap-x-3.5 gap-y-1 font-code-sm text-code-sm text-on-surface-variant text-[11px]">
        {meta.footer.map((item, idx) => (
          <React.Fragment key={item.label}>
            <span>
              {item.label}: <strong className="text-on-surface font-medium">{item.val}</strong>
            </span>
            {idx < meta.footer.length - 1 && (
              <span className="text-outline-variant">•</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
