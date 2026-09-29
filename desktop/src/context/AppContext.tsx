import React, { createContext, useContext, useState, useMemo, useCallback } from "react";
import {
  NavigationTab,
  SystemStatusType,
  DailyQuota,
  AuditEntry,
  DoctorCheck,
  SystemTelemetry,
} from "../types";

export interface AppContextType {
  currentTab: NavigationTab;
  setCurrentTab: (tab: NavigationTab) => void;
  systemStatus: SystemStatusType;
  isPaused: boolean;
  togglePause: () => void;
  pendingCount: number;
  setPendingCount: (count: number) => void;
  telemetry: SystemTelemetry;
  quota: DailyQuota;
  isScouting: boolean;
  triggerScout: () => Promise<void>;
  isCheckingDoctor: boolean;
  runDoctorCheck: () => Promise<void>;
  auditEntries: AuditEntry[];
  doctorChecks: DoctorCheck[];
  lastTriggerMessage: string | null;
}

const initialTelemetry: SystemTelemetry = {
  workerUrl: "https://relay.hitl-agent.workers.dev",
  workerStatus: "connected",
  kvBackend: "Cloudflare KV",
  sessionValid: true,
  nimModel: "meta/llama-3.1-70b-instruct",
  lastScanAt: "10 minutes ago",
  isPaused: false,
  circuitBreakerTripped: false,
  pendingCount: 3,
};

const initialQuota: DailyQuota = {
  commentsExecuted: 4,
  commentsMax: 15,
  postsExecuted: 1,
  postsMax: 3,
  suggestionsSent: 7,
  suggestionsMax: 20,
};

const initialAuditEntries: AuditEntry[] = [
  {
    id: "hist-001",
    itemId: "act-8f4b1e",
    actionType: "comment",
    status: "executed_success",
    decidedAt: "2026-09-29T16:45:00Z",
    executedAt: "2026-09-29T16:45:18Z",
    targetAuthor: "Satya Nadella",
    targetHeadline: "Chairman and CEO at Microsoft",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:7245890012",
    draftExcerpt:
      "The compounding returns on autonomous verification pipelines highlight why deterministic guardrails matter more than raw model scale.",
  },
  {
    id: "hist-002",
    itemId: "act-3a9d2c",
    actionType: "comment",
    status: "rejected",
    decidedAt: "2026-09-29T15:20:00Z",
    targetAuthor: "Sam Altman",
    targetHeadline: "CEO at OpenAI",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:7245812948",
    draftExcerpt:
      "Reasoning models shift the bottleneck from training compute to runtime deliberation.",
  },
  {
    id: "hist-003",
    itemId: "act-7c1e5a",
    actionType: "post",
    status: "executed_success",
    decidedAt: "2026-09-29T14:00:00Z",
    executedAt: "2026-09-29T14:01:05Z",
    draftExcerpt:
      "Why human-in-the-loop is the prerequisite for enterprise agent deployment: an architectural deep-dive into determinism, state isolation, and zero-leak session vaults.",
  },
  {
    id: "hist-004",
    itemId: "act-9e8d4f",
    actionType: "comment",
    status: "expired",
    decidedAt: "2026-09-29T12:00:00Z",
    targetAuthor: "Andrej Karpathy",
    targetHeadline: "Eureka Labs",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:7245701192",
    draftExcerpt:
      "Synthetic pretraining environments require strict physical invariants to prevent model reward hacking.",
  },
  {
    id: "hist-005",
    itemId: "act-1b2c3d",
    actionType: "comment",
    status: "executed_failed",
    decidedAt: "2026-09-29T10:15:00Z",
    executedAt: "2026-09-29T10:15:42Z",
    targetAuthor: "Yann LeCun",
    targetHeadline: "Chief AI Scientist at Meta",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:7245609384",
    draftExcerpt:
      "Autoregressive generation without world models struggles with persistent planning horizon limits.",
    error: "Target post comment field temporarily disabled by author",
  },
  {
    id: "hist-006",
    itemId: "act-4d5e6f",
    actionType: "comment",
    status: "executed_success",
    decidedAt: "2026-09-29T09:30:00Z",
    executedAt: "2026-09-29T09:30:22Z",
    targetAuthor: "Demis Hassabis",
    targetHeadline: "CEO at Google DeepMind",
    targetUrl: "https://linkedin.com/feed/update/urn:li:activity:7245511239",
    draftExcerpt:
      "AlphaFold 3 biological modeling demonstrates the power of diffusion over complex structural distributions.",
  },
];

const initialDoctorChecks: DoctorCheck[] = [
  {
    id: "chk-kv",
    category: "state",
    title: "Cloudflare KV State Store",
    status: "pass",
    latencyMs: 38,
    detail: "Namespace bound and active. Fast edge read/write verified without merge conflicts.",
  },
  {
    id: "chk-relay",
    category: "relay",
    title: "Telegram Relay Worker",
    status: "pass",
    latencyMs: 64,
    detail: "Webhook operational on Cloudflare Workers edge. HMAC signature validation active.",
  },
  {
    id: "chk-session",
    category: "session",
    title: "LinkedIn Playwright Session",
    status: "pass",
    latencyMs: 120,
    detail: "Session state decryptable. li_at cookie active (valid for 18 days). No checkpoint encountered.",
  },
  {
    id: "chk-llm",
    category: "llm",
    title: "NVIDIA NIM Connectivity",
    status: "pass",
    latencyMs: 245,
    detail: "Primary model meta/llama-3.1-70b-instruct responsive. Structured schema validation passing.",
  },
  {
    id: "chk-safety",
    category: "safety",
    title: "Safety & Circuit Breaker",
    status: "pass",
    detail: "Circuit breaker intact. 0 bot detections. Daily quota burn-down within configured thresholds.",
  },
  {
    id: "chk-env",
    category: "env",
    title: "Environment Configuration",
    status: "pass",
    detail: "All required secrets and runtime variables detected and validated via pydantic-settings.",
  },
];

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>("dashboard");
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [pendingCount, setPendingCount] = useState<number>(3);
  const [telemetry, setTelemetry] = useState<SystemTelemetry>(initialTelemetry);
  const [quota] = useState<DailyQuota>(initialQuota);
  const [isScouting, setIsScouting] = useState<boolean>(false);
  const [isCheckingDoctor, setIsCheckingDoctor] = useState<boolean>(false);
  const [auditEntries] = useState<AuditEntry[]>(initialAuditEntries);
  const [doctorChecks, setDoctorChecks] = useState<DoctorCheck[]>(initialDoctorChecks);
  const [lastTriggerMessage, setLastTriggerMessage] = useState<string | null>(null);

  const systemStatus: SystemStatusType = useMemo(() => {
    if (telemetry.circuitBreakerTripped) return "tripped";
    if (isPaused) return "paused";
    return "operational";
  }, [telemetry.circuitBreakerTripped, isPaused]);

  const togglePause = useCallback(() => {
    setIsPaused((prev) => {
      const next = !prev;
      setTelemetry((t) => ({ ...t, isPaused: next }));
      setLastTriggerMessage(next ? "System paused by operator" : "System resumed to operational");
      return next;
    });
  }, []);

  const triggerScout = useCallback(async () => {
    setIsScouting(true);
    setLastTriggerMessage("Scout workflow triggered. Scanning feed...");
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      setTelemetry((t) => ({ ...t, lastScanAt: "Just now" }));
      setLastTriggerMessage("Scout cycle completed: 1 candidate drafted.");
    } finally {
      setIsScouting(false);
    }
  }, []);

  const runDoctorCheck = useCallback(async () => {
    setIsCheckingDoctor(true);
    setLastTriggerMessage("Running full system diagnostics...");
    try {
      await new Promise((resolve) => setTimeout(resolve, 600));
      setDoctorChecks((prev) =>
        prev.map((c) => ({
          ...c,
          latencyMs: c.latencyMs ? Math.round(c.latencyMs * (0.9 + Math.random() * 0.2)) : undefined,
        }))
      );
      setLastTriggerMessage("Diagnostics complete: All 6 checks passing.");
    } finally {
      setIsCheckingDoctor(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      currentTab,
      setCurrentTab,
      systemStatus,
      isPaused,
      togglePause,
      pendingCount,
      setPendingCount,
      telemetry,
      quota,
      isScouting,
      triggerScout,
      isCheckingDoctor,
      runDoctorCheck,
      auditEntries,
      doctorChecks,
      lastTriggerMessage,
    }),
    [
      currentTab,
      systemStatus,
      isPaused,
      togglePause,
      pendingCount,
      telemetry,
      quota,
      isScouting,
      triggerScout,
      isCheckingDoctor,
      runDoctorCheck,
      auditEntries,
      doctorChecks,
      lastTriggerMessage,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};
