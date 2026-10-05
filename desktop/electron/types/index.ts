/**
 * Shared TypeScript interfaces for Electron main process and IPC.
 */

export interface PendingAction {
  item_id: string;
  action_type: "approve_comment" | "approve_post" | string;
  created_at: string;
  post_urn?: string;
  post_url?: string;
  author_name?: string;
  author_headline?: string;
  post_excerpt?: string;
  draft_text: string;
  confidence?: number;
  reasoning?: string;
  engagement_style?: string | null;
  telegram_chat_id?: number | null;
  telegram_message_id?: number | null;
}

export interface DailyCounters {
  date: string;
  comments_executed: number;
  posts_executed: number;
  suggestions_sent: number;
}

export interface HistoryEntry {
  item_id: string;
  action_type: string;
  final_status:
    | "rejected"
    | "expired"
    | "executed_success"
    | "executed_failed"
    | "halted"
    | string;
  decided_at?: string | null;
  executed_at?: string | null;
  screenshot_path?: string | null;
  error?: string | null;
}

export interface Incident {
  created_at: string;
  tripped_at: string;
  reason: string;
  context?: Record<string, unknown>;
}

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
  media_key?: string;
  slide_count: number;
}

export interface ScheduledPost {
  id: string;
  headline: string;
  post_text: string;
  scheduled_time?: string | null;
  status: "draft" | "scheduled" | "published" | "failed";
  media: MediaAttachment[];
  topic_pillar: string;
  created_at: string;
  approved_at?: string | null;
}

export interface AgentState {
  pending?: PendingAction[];
  pending_actions: PendingAction[];
  pendingActions?: PendingAction[];
  daily_counters: DailyCounters;
  dailyCounters?: DailyCounters;
  history: HistoryEntry[];
  incident: Incident | null;
  paused: boolean;
  seen_posts_count?: number;
  seenPostsCount?: number;
  connection_queue?: ConnectionRequestAction[];
  connectionQueue?: ConnectionRequestAction[];
  scheduled_posts?: ScheduledPost[];
  scheduledPosts?: ScheduledPost[];
  last_updated?: string;
  lastUpdated?: string;
}

export interface ActionResult {
  success: boolean;
  message?: string;
  itemId?: string;
  action?: string;
  error?: string;
}

export interface DesktopSettings {
  workerUrl: string;
  apiSecret: string;
  encryptionKey?: string;
  nimModel?: string;
  nimApiKey?: string;
  githubRepoOwner?: string;
  githubRepoName?: string;
  githubDispatchPat?: string;
  autoRefreshInterval?: number;
  executionMode?: "cloud" | "local";
  headless?: boolean;
  minimizeToTray?: boolean;
  notificationsEnabled?: boolean;
  maxCommentsPerDay?: number;
  maxPostsPerDay?: number;
  maxSuggestionsPerRun?: number;
  actionTtlHours?: number;
}

export interface ElectronAPI {
  fetchState: (credentials?: { workerUrl?: string; apiSecret?: string }) => Promise<AgentState>;
  testConnection?: (credentials?: { workerUrl?: string; apiSecret?: string }) => Promise<{ success: boolean; latencyMs?: number; error?: string }>;
  executeAction: (
    action: "approve" | "reject",
    itemId: string,
    draftText?: string
  ) => Promise<ActionResult>;
  executeConnectionAction?: (
    action: "approve" | "reject",
    id: string,
    note?: string
  ) => Promise<ActionResult>;
  triggerScout: () => Promise<boolean>;
  togglePause: (paused: boolean) => Promise<boolean>;
  clearIncident: () => Promise<boolean>;
  rewriteDraft: (draftText: string, tone: string) => Promise<string>;
  saveSession: (sessionData: string) => Promise<boolean>;
  getSettings: () => Promise<DesktopSettings>;
  saveSettings: (settings: Partial<DesktopSettings>) => Promise<boolean>;
  encryptSession: (data: string, base64Key: string) => Promise<string>;
  decryptSession: (token: string, base64Key: string) => Promise<string>;
  generateFernetKey: () => Promise<string>;
  captureSession?: () => Promise<{ success: boolean; error?: string }>;
  checkSessionHealth?: () => Promise<{ valid: boolean; daysRemaining?: number; details?: string }>;
  fetchNimModels?: (apiKey?: string) => Promise<{ success: boolean; models: string[]; error?: string }>;
  onRealtimeEvent?: (callback: (event: any) => void) => () => void;
  fetchScheduledPosts?: () => Promise<ScheduledPost[]>;
  saveScheduledPost?: (post: ScheduledPost) => Promise<ScheduledPost>;
  deleteScheduledPost?: (id: string) => Promise<boolean>;
  fetchConnectionQueue?: () => Promise<ConnectionRequestAction[]>;
  uploadMedia?: (
    fileName: string,
    fileBuffer: ArrayBuffer,
    contentType?: string
  ) => Promise<{ success: boolean; key?: string; url?: string; error?: string }>;
}

