export type SystemStatusType = "operational" | "paused" | "tripped";

export type HistoryStatus =
  | "executed_success"
  | "executed_failed"
  | "rejected"
  | "expired"
  | "halted";

export type NavigationTab =
  | "dashboard"
  | "queue"
  | "vault"
  | "history"
  | "doctor"
  | "settings";

export interface DailyQuota {
  commentsExecuted: number;
  commentsMax: number;
  postsExecuted: number;
  postsMax: number;
  suggestionsSent: number;
  suggestionsMax: number;
}

export interface AuditEntry {
  id: string;
  itemId: string;
  actionType: "comment" | "post";
  status: HistoryStatus;
  decidedAt: string;
  executedAt?: string;
  targetAuthor?: string;
  targetHeadline?: string;
  targetUrl?: string;
  draftExcerpt?: string;
  error?: string;
  screenshotPath?: string;
}

export interface DoctorCheck {
  id: string;
  category: "state" | "relay" | "session" | "llm" | "safety" | "env";
  title: string;
  status: "pass" | "warn" | "fail";
  latencyMs?: number;
  detail: string;
  recommendation?: string;
}

export interface SystemTelemetry {
  workerUrl: string;
  workerStatus: "connected" | "disconnected" | "checking";
  kvBackend: string;
  sessionValid: boolean;
  nimModel: string;
  lastScanAt: string;
  isPaused: boolean;
  circuitBreakerTripped: boolean;
  pendingCount: number;
}
