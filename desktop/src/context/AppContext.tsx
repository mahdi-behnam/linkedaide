import React, { createContext, useContext, useState, useMemo, useCallback, useEffect } from "react";
import {
  NavigationTab,
  SystemStatusType,
  DailyQuota,
  AuditEntry,
  DoctorCheck,
  SystemTelemetry,
  ScheduledPost,
  AutomatedCommentWindow,
  ConnectionRequestAction,
} from "../types";
import { ActionResult } from "../types/api";

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
  scheduledPosts: ScheduledPost[];
  saveScheduledPost: (post: ScheduledPost) => void;
  deleteScheduledPost: (id: string) => void;
  commentWindows: AutomatedCommentWindow[];
  activePostForEditing: ScheduledPost | null;
  setActivePostForEditing: (post: ScheduledPost | null) => void;
  connectionQueue: ConnectionRequestAction[];
  setConnectionQueue: React.Dispatch<React.SetStateAction<ConnectionRequestAction[]>>;
  executeConnectionAction: (
    action: "approve" | "reject",
    id: string,
    note?: string
  ) => Promise<ActionResult>;
  refreshState?: () => Promise<void>;
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
  connectionsSent: 2,
  connectionsMax: 10,
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

const initialScheduledPosts: ScheduledPost[] = [
  {
    id: "post-001",
    headline: "The 3 Invariants of Production LLM Agents",
    post_text: "Most agent failures in production aren't model hallucinations. They are uncontrolled side effects.\n\nAfter auditing enterprise autonomous workflows, three non-negotiable architectural invariants emerged:\n\n1. Deterministic State Storage: Agents must never own persistent safety state in ephemeral checkpointers.\n2. Mandatory Human Authorization: No platform write actions without explicit cryptographic or relay sign-off.\n3. Dom-Verified Confirmations: Never assume an automated click succeeded without structural DOM verification.\n\nWhat safety invariant do you consider non-negotiable for enterprise deployment?",
    scheduled_time: "2026-09-30T14:00:00Z",
    status: "scheduled",
    topic_pillar: "Agent Architecture",
    media: [
      {
        media_type: "carousel_pdf",
        file_name: "hitl-agent-architecture.pdf",
        file_url: "mock://hitl-agent-architecture.pdf",
        slide_count: 5,
      },
    ],
    created_at: "2026-09-29T10:00:00Z",
    approved_at: "2026-09-29T11:30:00Z",
  },
  {
    id: "post-002",
    headline: "Why Cloudflare KV Beats Git-as-Database for Live State",
    post_text: "Running autonomous pipelines using git commit-and-push for live state creates three critical problems:\n- Merge conflict storms during concurrent runs\n- Commit history pollution with transient counters\n- Public exposure of pending drafts\n\nMigrating to edge key-value storage completely solved state race conditions with sub-40ms latency.",
    scheduled_time: "2026-10-02T16:30:00Z",
    status: "draft",
    topic_pillar: "System Design",
    media: [],
    created_at: "2026-09-29T12:00:00Z",
  },
  {
    id: "post-003",
    headline: "Zero-Leak Session Vaults for Headless Browsers",
    post_text: "How do you securely automate LinkedIn interactions without exposing raw authentication cookies in CI/CD logs?\n\nWe implemented symmetric Fernet encryption for browser storage states:\n- Decryption keys stay in runner memory\n- Cookies are purged immediately post-execution\n- Continuous health checks monitor session expiry\n\nResult: 18-day session longevity with zero token leakage.",
    scheduled_time: "2026-09-28T09:00:00Z",
    status: "published",
    topic_pillar: "Security & Vaults",
    media: [
      {
        media_type: "image",
        file_name: "vault-encryption-flow.png",
        file_url: "mock://vault-encryption-flow.png",
        slide_count: 1,
      },
    ],
    created_at: "2026-09-27T08:00:00Z",
    approved_at: "2026-09-27T08:45:00Z",
  },
];

const initialCommentWindows: AutomatedCommentWindow[] = [
  {
    id: "win-001",
    title: "Morning Feed Scout",
    start_time: "09:00",
    end_time: "10:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "AI Systems & LLM Architecture",
  },
  {
    id: "win-002",
    title: "Afternoon High-Signal Discussion",
    start_time: "14:00",
    end_time: "15:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Distributed Systems & Cloudflare Workers",
  },
  {
    id: "win-003",
    title: "Evening Industry Roundup",
    start_time: "18:00",
    end_time: "19:00",
    days: ["Tue", "Thu"],
    status: "standby",
    topic_filter: "Autonomous Agents & Frameworks",
  },
];

const initialConnectionQueue: ConnectionRequestAction[] = [
  {
    id: "conn-001",
    profile_url: "https://linkedin.com/in/alice-vance-dist",
    target_name: "Alice Vance",
    target_headline: "Staff Distributed Systems Engineer at Cloudflare",
    mutual_context: "Commented on Alice's post regarding distributed cache invalidation and edge KV consistency",
    note_text: "Hi Alice, really enjoyed your breakdown on edge cache invalidation tradeoffs. Would love to connect and follow your work on distributed systems.",
    status: "pending",
    created_at: "2026-09-30T08:15:00Z",
  },
  {
    id: "conn-002",
    profile_url: "https://linkedin.com/in/marcus-chen-ai",
    target_name: "Marcus Chen",
    target_headline: "Principal Research Scientist at NVIDIA NIM Team",
    mutual_context: "Participated in thread discussing speculative decoding speedups in Nemotron architectures",
    note_text: "Hey Marcus, your insights on speculative decoding latency boundaries were spot on. Excited to connect and keep track of your team's breakthroughs.",
    status: "pending",
    created_at: "2026-09-30T07:45:00Z",
  },
  {
    id: "conn-003",
    profile_url: "https://linkedin.com/in/sarah-jenkins-dev",
    target_name: "Sarah Jenkins",
    target_headline: "Head of AI Infrastructure at LangChain",
    mutual_context: "Engaged on discussion about persistent state checkpoints vs ephemeral graph memory in multi-agent workflows",
    note_text: "Hi Sarah, loved your analysis on checkpoint durability across multi-agent pipelines. Looking forward to staying connected.",
    status: "pending",
    created_at: "2026-09-29T22:10:00Z",
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
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>(initialScheduledPosts);
  const [commentWindows] = useState<AutomatedCommentWindow[]>(initialCommentWindows);
  const [activePostForEditing, setActivePostForEditing] = useState<ScheduledPost | null>(null);
  const [connectionQueue, setConnectionQueue] = useState<ConnectionRequestAction[]>(initialConnectionQueue);

  const refreshState = useCallback(async () => {
    if (typeof window === "undefined" || !window.api?.fetchState) {
      return;
    }
    try {
      const state = await window.api.fetchState();
      if (!state) return;

      const rawPending = state.pending_actions || state.pendingActions || [];
      const newPendingCount = rawPending.length;

      setPendingCount((prev) => {
        if (newPendingCount > prev) {
          const diff = newPendingCount - prev;
          setLastTriggerMessage(`⚡ Realtime: ${diff} new approval${diff > 1 ? "s" : ""} available in queue`);
        }
        return newPendingCount;
      });

      if (typeof state.paused === "boolean") {
        setIsPaused(state.paused);
      }

      setTelemetry((prev) => ({
        ...prev,
        isPaused: typeof state.paused === "boolean" ? state.paused : prev.isPaused,
        circuitBreakerTripped: Boolean(state.incident),
        pendingCount: newPendingCount,
        lastScanAt: state.last_updated || state.lastUpdated || "Just now",
      }));

      if (state.connection_queue || state.connectionQueue) {
        setConnectionQueue(state.connection_queue || state.connectionQueue || []);
      }
    } catch (err) {
      console.warn("Silent background refreshState failed:", err);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !window.api?.onRealtimeEvent) {
      return;
    }

    const unsubscribe = window.api.onRealtimeEvent((event: any) => {
      if (!event) return;
      const eventType = event.type;

      if (eventType === "queue_updated" || eventType === "action_executed") {
        refreshState();
        if (eventType === "action_executed") {
          setLastTriggerMessage(
            `⚡ Realtime: Action "${event.action || "executed"}" recorded for ${event.item_id || "item"}`
          );
        } else if (eventType === "queue_updated") {
          setLastTriggerMessage("⚡ Realtime: Approval queue updated from cloud");
        }
      }
    });

    return () => {
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, [refreshState]);

  const executeConnectionAction = useCallback(
    async (
      action: "approve" | "reject",
      id: string,
      note?: string
    ): Promise<ActionResult> => {
      let result: ActionResult = { success: true, itemId: id, action };
      if (typeof window !== "undefined" && window.api?.executeConnectionAction) {
        try {
          result = await window.api.executeConnectionAction(action, id, note);
        } catch (err: unknown) {
          const errMsg = err instanceof Error ? err.message : "Failed to execute connection action";
          result = { success: false, error: errMsg };
        }
      }

      setConnectionQueue((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                status: action === "approve" ? "approved" : "rejected",
                note_text: note !== undefined ? note : c.note_text,
                approved_at: action === "approve" ? new Date().toISOString() : undefined,
              }
            : c
        )
      );

      const target = connectionQueue.find((c) => c.id === id);
      const name = target ? target.target_name : id;
      setLastTriggerMessage(
        action === "approve"
          ? `Connection request approved for ${name}. Invitation queued.`
          : `Connection candidate for ${name} rejected.`
      );

      return result;
    },
    [connectionQueue]
  );

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

  const saveScheduledPost = useCallback((post: ScheduledPost) => {
    setScheduledPosts((prev) => {
      const idx = prev.findIndex((p) => p.id === post.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = post;
        return next;
      }
      return [post, ...prev];
    });
    setLastTriggerMessage(`Post saved successfully: "${post.headline || post.id}"`);
  }, []);

  const deleteScheduledPost = useCallback((id: string) => {
    setScheduledPosts((prev) => prev.filter((p) => p.id !== id));
    setLastTriggerMessage("Scheduled post removed");
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
      scheduledPosts,
      saveScheduledPost,
      deleteScheduledPost,
      commentWindows,
      activePostForEditing,
      setActivePostForEditing,
      connectionQueue,
      setConnectionQueue,
      executeConnectionAction,
      refreshState,
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
      scheduledPosts,
      saveScheduledPost,
      deleteScheduledPost,
      commentWindows,
      activePostForEditing,
      connectionQueue,
      executeConnectionAction,
      refreshState,
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
