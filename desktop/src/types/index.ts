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
  | "outreach"
  | "composer"
  | "calendar"
  | "analytics"
  | "vault"
  | "history"
  | "doctor"
  | "settings";

export type ScheduledPostStatus = "draft" | "scheduled" | "published" | "failed";

export interface ConnectionRequestAction {
  id: string;
  profile_url: string;
  target_name: string;
  target_headline?: string;
  mutual_context?: string;
  note_text?: string;
  status: "pending" | "approved" | "rejected" | "sent" | "failed";
  created_at: string;
  approved_at?: string | null;
}

export interface MediaAttachment {
  media_type: "image" | "carousel_pdf";
  file_name: string;
  file_url: string;
  slide_count: number;
}

export interface ScheduledPost {
  id: string;
  headline: string;
  post_text: string;
  scheduled_time?: string | null;
  status: ScheduledPostStatus;
  media: MediaAttachment[];
  topic_pillar: string;
  created_at: string;
  approved_at?: string | null;
}

export interface AutomatedCommentWindow {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  days: string[];
  status: "active" | "standby" | "paused";
  topic_filter: string;
}

export interface DailyQuota {
  commentsExecuted: number;
  commentsMax: number;
  postsExecuted: number;
  postsMax: number;
  suggestionsSent: number;
  suggestionsMax: number;
  connectionsSent?: number;
  connectionsMax?: number;
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
