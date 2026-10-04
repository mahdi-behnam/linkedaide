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
import { useScheduledPosts } from "../hooks/useScheduledPosts";
import { useConnectionQueue } from "../hooks/useConnectionQueue";
import { useDoctorDiagnostics } from "../hooks/useDoctorDiagnostics";

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
  clearIncident?: () => Promise<void>;
  refreshState?: () => Promise<void>;
}

const initialTelemetry: SystemTelemetry = {
  workerUrl: "https://relay.hitl-agent.workers.dev",
  workerStatus: "connected",
  kvBackend: "Cloudflare KV",
  sessionValid: false,
  nimModel: "",
  lastScanAt: "Never",
  isPaused: false,
  circuitBreakerTripped: false,
  pendingCount: 0,
};

const initialQuota: DailyQuota = {
  commentsExecuted: 0,
  commentsMax: 15,
  postsExecuted: 0,
  postsMax: 3,
  suggestionsSent: 0,
  suggestionsMax: 20,
  connectionsSent: 0,
  connectionsMax: 10,
};

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>("dashboard");
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [telemetry, setTelemetry] = useState<SystemTelemetry>(initialTelemetry);
  const [quota, setQuota] = useState<DailyQuota>(initialQuota);
  const [isScouting, setIsScouting] = useState<boolean>(false);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [lastTriggerMessage, setLastTriggerMessage] = useState<string | null>(null);
  const [commentWindows] = useState<AutomatedCommentWindow[]>([]);

  // Modular custom hooks
  const {
    scheduledPosts,
    activePostForEditing,
    setActivePostForEditing,
    saveScheduledPost,
    deleteScheduledPost,
  } = useScheduledPosts(setLastTriggerMessage);

  const {
    connectionQueue,
    setConnectionQueue,
    executeConnectionAction,
  } = useConnectionQueue(setLastTriggerMessage);

  const {
    isCheckingDoctor,
    doctorChecks,
    runDoctorCheck,
  } = useDoctorDiagnostics(telemetry, setTelemetry, setLastTriggerMessage);

  const refreshState = useCallback(async () => {
    if (typeof window === "undefined" || !window.api?.fetchState) {
      return;
    }
    try {
      const state = await window.api.fetchState();
      if (!state) return;

      const rawPending =
        state.pending_actions ||
        state.pendingActions ||
        state.pending ||
        [];
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

      if (state.daily_counters || state.dailyCounters) {
        const counters = (state.daily_counters || state.dailyCounters) as any;
        setQuota((prev) => ({
          ...prev,
          commentsExecuted: counters.comments_executed ?? counters.commentsExecuted ?? prev.commentsExecuted,
          postsExecuted: counters.posts_executed ?? counters.postsExecuted ?? prev.postsExecuted,
          suggestionsSent: counters.suggestions_sent ?? counters.suggestionsSent ?? prev.suggestionsSent,
          connectionsSent: counters.connections_sent ?? counters.connectionsSent ?? prev.connectionsSent,
        }));
      }

      if (Array.isArray(state.history)) {
        if (state.history.length === 0) {
          setAuditEntries([]);
        } else {
          setAuditEntries(
            state.history.map((h, i) => ({
              id: `hist-${h.item_id || i}`,
              itemId: h.item_id || `item-${i}`,
              actionType: (h.action_type?.includes("post") ? "post" : "comment") as "post" | "comment",
              status: (h.final_status as any) || "executed_success",
              decidedAt: h.decided_at || new Date().toISOString(),
              executedAt: h.executed_at || undefined,
              screenshotPath: h.screenshot_path || undefined,
              error: h.error || undefined,
            }))
          );
        }
      }
    } catch (err) {
      console.warn("Silent background refreshState failed:", err);
    }
  }, [setConnectionQueue]);

  useEffect(() => {
    let isMounted = true;
    const initTelemetry = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const s = await window.api.getSettings();
          if (isMounted && s?.nimModel) {
            setTelemetry((prev) => ({
              ...prev,
              nimModel: s.nimModel || prev.nimModel,
            }));
          }
        } catch {
          // ignore
        }
      }
      if (typeof window !== "undefined" && window.api?.checkSessionHealth) {
        try {
          const h = await window.api.checkSessionHealth();
          if (isMounted && typeof h?.valid === "boolean") {
            setTelemetry((prev) => ({
              ...prev,
              sessionValid: h.valid,
            }));
          }
        } catch {
          // ignore
        }
      }
    };
    initTelemetry();
    return () => {
      isMounted = false;
    };
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

  const systemStatus: SystemStatusType = useMemo(() => {
    if (telemetry.circuitBreakerTripped) return "tripped";
    if (isPaused) return "paused";
    return "operational";
  }, [telemetry.circuitBreakerTripped, isPaused]);

  const togglePause = useCallback(async () => {
    const next = !isPaused;
    setIsPaused(next);
    setTelemetry((t) => ({ ...t, isPaused: next }));
    setLastTriggerMessage(next ? "System paused by operator" : "System resumed to operational");
    if (typeof window !== "undefined" && window.api?.togglePause) {
      try {
        await window.api.togglePause(next);
      } catch (err) {
        console.warn("Failed to sync pause state with backend:", err);
      }
    }
  }, [isPaused]);

  const triggerScout = useCallback(async () => {
    setIsScouting(true);
    setLastTriggerMessage("Scout workflow triggered. Initiating feed scan...");
    try {
      if (typeof window !== "undefined" && window.api?.triggerScout) {
        const ok = await window.api.triggerScout();
        if (ok) {
          setTelemetry((t) => ({ ...t, lastScanAt: "Just now" }));
          setLastTriggerMessage("Scout workflow dispatched successfully. Scanning feed for candidates...");
          await refreshState();
        } else {
          setLastTriggerMessage("Scout execution finished with errors or dispatch failed.");
        }
      } else {
        await new Promise((resolve) => setTimeout(resolve, 800));
        setTelemetry((t) => ({ ...t, lastScanAt: "Just now" }));
        setLastTriggerMessage("Scout simulation completed (preview mode).");
      }
    } catch (err: unknown) {
      let errMsg = err instanceof Error ? err.message : String(err);
      errMsg = errMsg.replace(/^Error invoking remote method '[^']+':\s*(Error:\s*)?/, "");
      if (errMsg.includes("Resource not accessible by personal access token")) {
        errMsg = "GitHub PAT permission denied (403): Token lacks workflow dispatch rights. For Classic PATs (ghp_...), check both 'workflow' and 'repo' scopes. For Fine-grained PATs (github_pat_...), set Repository Permissions -> 'Actions' to 'Read and write'.";
      }
      setLastTriggerMessage(`Scout dispatch failed: ${errMsg}`);
    } finally {
      setIsScouting(false);
    }
  }, [refreshState]);

  const clearIncident = useCallback(async () => {
    if (typeof window !== "undefined" && window.api?.clearIncident) {
      try {
        const ok = await window.api.clearIncident();
        if (ok) {
          setTelemetry((t) => ({ ...t, circuitBreakerTripped: false }));
          setLastTriggerMessage("Circuit breaker cleared and reset to operational.");
          await refreshState();
        } else {
          setLastTriggerMessage("Failed to clear circuit breaker incident.");
        }
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : String(err);
        setLastTriggerMessage(`Clear incident failed: ${errMsg}`);
      }
    }
  }, [refreshState]);

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
      clearIncident,
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
      clearIncident,
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
