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
import { ToastNotification } from "../components/toast/types";
import {
  getDefaultTimezone,
  isValidTimezone,
  formatTime as utilFormatTime,
  formatDate as utilFormatDate,
  formatDateTime as utilFormatDateTime,
  formatTimeAgo as utilFormatTimeAgo,
  calculateNextScoutTime,
} from "../utils/datetime";
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
  notifications: ToastNotification[];
  addNotification: (
    message: string,
    options?: { type?: "info" | "success" | "warn" | "error"; durationMs?: number }
  ) => void;
  removeNotification: (id: string) => void;
  timezone: string;
  setTimezone: (tz: string) => void;
  formatTime: (
    date: Date | string | number | null | undefined,
    options?: Intl.DateTimeFormatOptions
  ) => string;
  formatDate: (
    date: Date | string | number | null | undefined,
    options?: Intl.DateTimeFormatOptions
  ) => string;
  formatDateTime: (
    date: Date | string | number | null | undefined,
    options?: Intl.DateTimeFormatOptions
  ) => string;
  formatTimeAgo: (date: Date | string | number | null | undefined) => string;
  scheduledPosts: ScheduledPost[];
  saveScheduledPost: (post: ScheduledPost) => void;
  deleteScheduledPost: (id: string) => void;
  commentWindows: AutomatedCommentWindow[];
  setCommentWindows: React.Dispatch<React.SetStateAction<AutomatedCommentWindow[]>>;
  saveCommentWindows: (windows: AutomatedCommentWindow[]) => Promise<boolean>;
  nextScoutTime: string;
  activePostForEditing: ScheduledPost | null;
  setActivePostForEditing: (post: ScheduledPost | null) => void;
  connectionQueue: ConnectionRequestAction[];
  setConnectionQueue: React.Dispatch<React.SetStateAction<ConnectionRequestAction[]>>;
  executeConnectionAction: (
    action: "approve" | "reject",
    id: string,
    note?: string
  ) => Promise<ActionResult>;
  hasUnsavedSettings: boolean;
  setHasUnsavedSettings: (dirty: boolean) => void;
  saveSettingsHandler: (() => Promise<boolean>) | null;
  setSaveSettingsHandler: (fn: (() => Promise<boolean>) | null) => void;
  discardSettingsHandler: (() => void) | null;
  setDiscardSettingsHandler: (fn: (() => void) | null) => void;
  clearIncident?: () => Promise<void>;
  refreshState?: () => Promise<void>;
  autoRefreshInterval: number;
  setAutoRefreshInterval: (interval: number) => void;
}

export const defaultCommentWindows: AutomatedCommentWindow[] = [
  {
    id: "scout-win-morning",
    title: "Morning Feed Scout Window",
    start_time: "08:00",
    end_time: "09:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Engineering Leadership & AI Systems",
  },
  {
    id: "scout-win-midday",
    title: "Midday Feed Scout Window",
    start_time: "13:00",
    end_time: "14:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Distributed Systems & Cloud Architecture",
  },
  {
    id: "scout-win-evening",
    title: "Evening Feed Scout Window",
    start_time: "18:00",
    end_time: "19:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Technical Architecture & High Impact Engineering",
  },
];

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
  const [notifications, setNotifications] = useState<ToastNotification[]>([]);
  const [commentWindows, setCommentWindows] = useState<AutomatedCommentWindow[]>(defaultCommentWindows);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(600);
  const [timezone, setTimezoneState] = useState<string>(() => {
    if (typeof window !== "undefined" && window.localStorage) {
      const saved = window.localStorage.getItem("linkedaide_timezone");
      if (saved && isValidTimezone(saved)) return saved;
    }
    return getDefaultTimezone();
  });

  const setTimezone = useCallback((tz: string) => {
    const validTz = isValidTimezone(tz) ? tz : getDefaultTimezone();
    setTimezoneState(validTz);
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem("linkedaide_timezone", validTz);
    }
    if (typeof window !== "undefined" && window.api?.saveSettings) {
      void window.api.saveSettings({ timezone: validTz });
    }
  }, []);

  const formatTime = useCallback(
    (date: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions) =>
      utilFormatTime(date, timezone, options),
    [timezone]
  );

  const formatDate = useCallback(
    (date: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions) =>
      utilFormatDate(date, timezone, options),
    [timezone]
  );

  const formatDateTime = useCallback(
    (date: Date | string | number | null | undefined, options?: Intl.DateTimeFormatOptions) =>
      utilFormatDateTime(date, timezone, options),
    [timezone]
  );

  const formatTimeAgo = useCallback(
    (date: Date | string | number | null | undefined) =>
      utilFormatTimeAgo(date, timezone),
    [timezone]
  );

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const [hasUnsavedSettings, setHasUnsavedSettings] = useState<boolean>(false);
  const [saveSettingsHandler, setSaveSettingsHandlerState] = useState<(() => Promise<boolean>) | null>(null);
  const [discardSettingsHandler, setDiscardSettingsHandlerState] = useState<(() => void) | null>(null);

  const setSaveSettingsHandler = useCallback((fn: (() => Promise<boolean>) | null) => {
    setSaveSettingsHandlerState(() => fn);
  }, []);

  const setDiscardSettingsHandler = useCallback((fn: (() => void) | null) => {
    setDiscardSettingsHandlerState(() => fn);
  }, []);

  const addNotification = useCallback(
    (
      message: string,
      options?: { type?: "info" | "success" | "warn" | "error"; durationMs?: number }
    ) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      const newToast: ToastNotification = {
        id,
        message,
        type: options?.type || "info",
        durationMs: options?.durationMs ?? 5000,
      };
      setNotifications((prev) => [...prev, newToast]);
      setLastTriggerMessage(message);
    },
    []
  );

  const handleSetLastTriggerMessage = useCallback(
    (msg: string | null) => {
      setLastTriggerMessage(msg);
      if (msg) {
        addNotification(msg);
      }
    },
    [addNotification]
  );

  const activeCommentWindows = useMemo(() => {
    return commentWindows.map((w) => ({
      ...w,
      status: isPaused ? ("paused" as const) : w.status,
    }));
  }, [commentWindows, isPaused]);

  const nextScoutTime = useMemo(() => {
    return calculateNextScoutTime(activeCommentWindows, timezone);
  }, [activeCommentWindows, timezone]);

  const saveCommentWindows = useCallback(
    async (windows: AutomatedCommentWindow[]): Promise<boolean> => {
      setCommentWindows(windows);
      try {
        if (typeof window !== "undefined" && window.api?.saveScoutSchedule) {
          const ok = await window.api.saveScoutSchedule(windows);
          if (ok) {
            addNotification("Scout schedule saved to Cloudflare Worker", { type: "success" });
            return true;
          } else {
            addNotification("Failed to save scout schedule to worker", { type: "error" });
            return false;
          }
        }
        return true;
      } catch (err) {
        console.error("Failed to save scout schedule:", err);
        addNotification("Failed to save scout schedule to worker", { type: "error" });
        return false;
      }
    },
    [addNotification]
  );

  // Modular custom hooks
  const {
    scheduledPosts,
    activePostForEditing,
    setActivePostForEditing,
    saveScheduledPost,
    deleteScheduledPost,
  } = useScheduledPosts(handleSetLastTriggerMessage);

  const {
    connectionQueue,
    setConnectionQueue,
    executeConnectionAction,
  } = useConnectionQueue(handleSetLastTriggerMessage);

  const {
    isCheckingDoctor,
    doctorChecks,
    runDoctorCheck,
  } = useDoctorDiagnostics(telemetry, setTelemetry, handleSetLastTriggerMessage);

  const applyState = useCallback((state: any) => {
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

    if (Array.isArray(state.scout_schedule || state.scoutSchedule)) {
      const schedule = (state.scout_schedule || state.scoutSchedule) as AutomatedCommentWindow[];
      if (schedule.length > 0) {
        setCommentWindows(schedule);
      }
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
          state.history.map((h: any, i: number) => {
            const rawType = (h.action_type || "").toLowerCase();
            const actionType: "comment" | "post" | "connection" | "reply" =
              rawType.includes("conn")
                ? "connection"
                : rawType.includes("reply")
                  ? "reply"
                  : rawType.includes("post")
                    ? "post"
                    : "comment";
            return {
              id: `hist-${h.item_id || i}`,
              itemId: h.item_id || `item-${i}`,
              actionType,
              status: (h.final_status as any) || "executed_success",
              decidedAt: h.decided_at || new Date().toISOString(),
              executedAt: h.executed_at || undefined,
              screenshotPath: h.screenshot_path || undefined,
              error: h.error || undefined,
            };
          })
        );
      }
    }
  }, [setConnectionQueue]);

  const refreshState = useCallback(async (preloadedState?: any) => {
    if (preloadedState) {
      applyState(preloadedState);
      return;
    }
    if (typeof window === "undefined" || !window.api?.fetchState) {
      return;
    }
    try {
      const state = await window.api.fetchState();
      if (!state) return;
      applyState(state);
    } catch (err) {
      console.warn("Silent background refreshState failed:", err);
    }
  }, [applyState]);

  useEffect(() => {
    let isMounted = true;
    const initTelemetry = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const s = await window.api.getSettings();
          if (isMounted) {
            if (s?.nimModel) {
              setTelemetry((prev) => ({
                ...prev,
                nimModel: s.nimModel || prev.nimModel,
              }));
            }
            if (s?.timezone && isValidTimezone(s.timezone)) {
              setTimezoneState(s.timezone);
            }
            if (typeof s?.autoRefreshInterval === "number") {
              setAutoRefreshInterval(s.autoRefreshInterval);
            }
          }
        } catch {
          // ignore
        }
      }
      if (typeof window !== "undefined" && window.api?.fetchScoutSchedule) {
        try {
          const schedule = await window.api.fetchScoutSchedule();
          if (isMounted && Array.isArray(schedule) && schedule.length > 0) {
            setCommentWindows(schedule);
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
    // Immediate initial state fetch on app launch
    refreshState();

    let lastFetchTime = Date.now();
    const FOCUS_THROTTLE_MS = 300_000; // Throttle window focus sync to at most once per 5 minutes

    const handleFocus = () => {
      const now = Date.now();
      if (now - lastFetchTime >= FOCUS_THROTTLE_MS) {
        lastFetchTime = now;
        refreshState();
      }
    };
    window.addEventListener("focus", handleFocus);

    // Fallback idle background polling every 10 minutes (600,000ms) to respect Cloudflare KV limits
    const interval = setInterval(() => {
      lastFetchTime = Date.now();
      refreshState();
    }, 600_000);

    return () => {
      window.removeEventListener("focus", handleFocus);
      clearInterval(interval);
    };
  }, [refreshState]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.api?.onRealtimeEvent) {
      return;
    }

    const unsubscribe = window.api.onRealtimeEvent((event: any) => {
      if (!event) return;
      const eventType = event.type;

      if (eventType === "queue_updated" || eventType === "action_executed") {
        if (event.state) {
          applyState(event.state);
        } else {
          refreshState();
        }
        if (eventType === "action_executed") {
          handleSetLastTriggerMessage(
            `⚡ Realtime: Action "${event.action || "executed"}" recorded for ${event.item_id || "item"}`
          );
        } else if (eventType === "queue_updated") {
          handleSetLastTriggerMessage("⚡ Realtime: Approval queue updated from cloud");
        }
      } else if (eventType === "scout_schedule_updated" && Array.isArray(event.schedule)) {
        setCommentWindows(event.schedule);
        handleSetLastTriggerMessage("⚡ Realtime: Scout schedule synchronized");
      }
    });

    return () => {
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, [applyState, refreshState, handleSetLastTriggerMessage]);

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

  useEffect(() => {
    if (typeof window === "undefined" || !window.api?.onMenuAction) {
      return;
    }
    const unsubscribe = window.api.onMenuAction((action: string, data?: unknown) => {
      if (action === "navigate" && typeof data === "string") {
        setCurrentTab(data as NavigationTab);
      } else if (action === "trigger-scout") {
        triggerScout();
      } else if (action === "toggle-pause") {
        togglePause();
      } else if (action === "refresh-state" && refreshState) {
        refreshState();
      } else if (action === "clear-incident" && clearIncident) {
        clearIncident();
      } else if (action === "run-doctor") {
        runDoctorCheck();
      }
    });
    return unsubscribe;
  }, [setCurrentTab, triggerScout, togglePause, refreshState, clearIncident, runDoctorCheck]);

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
      notifications,
      addNotification,
      removeNotification,
      timezone,
      setTimezone,
      formatTime,
      formatDate,
      formatDateTime,
      formatTimeAgo,
      scheduledPosts,
      saveScheduledPost,
      deleteScheduledPost,
      commentWindows: activeCommentWindows,
      setCommentWindows,
      saveCommentWindows,
      nextScoutTime,
      activePostForEditing,
      setActivePostForEditing,
      connectionQueue,
      setConnectionQueue,
      executeConnectionAction,
      hasUnsavedSettings,
      setHasUnsavedSettings,
      saveSettingsHandler,
      setSaveSettingsHandler,
      discardSettingsHandler,
      setDiscardSettingsHandler,
      refreshState,
      autoRefreshInterval,
      setAutoRefreshInterval,
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
      notifications,
      addNotification,
      removeNotification,
      timezone,
      setTimezone,
      formatTime,
      formatDate,
      formatDateTime,
      formatTimeAgo,
      scheduledPosts,
      saveScheduledPost,
      deleteScheduledPost,
      activeCommentWindows,
      setCommentWindows,
      saveCommentWindows,
      nextScoutTime,
      activePostForEditing,
      setActivePostForEditing,
      connectionQueue,
      setConnectionQueue,
      executeConnectionAction,
      hasUnsavedSettings,
      setHasUnsavedSettings,
      saveSettingsHandler,
      setSaveSettingsHandler,
      discardSettingsHandler,
      setDiscardSettingsHandler,
      refreshState,
      autoRefreshInterval,
      setAutoRefreshInterval,
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
