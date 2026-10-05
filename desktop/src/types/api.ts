/**
 * API types and global window definition for Desktop Renderer process.
 */

import type { ConnectionRequestAction, ScheduledPost } from "./index";
export type { ScheduledPost, MediaAttachment, ScheduledPostStatus, AutomatedCommentWindow, ConnectionRequestAction } from "./index";

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
  connections_sent: number;
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

export interface AgentState {
  pending?: PendingAction[];
  pending_actions: PendingAction[];
  pendingActions?: PendingAction[];
  connection_queue?: ConnectionRequestAction[];
  connectionQueue?: ConnectionRequestAction[];
  daily_counters: DailyCounters;
  dailyCounters?: DailyCounters;
  history: HistoryEntry[];
  incident: Incident | null;
  paused: boolean;
  seen_posts_count?: number;
  seenPostsCount?: number;
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
  autoRefreshInterval?: number;
  executionMode?: "cloud" | "local";
  headless?: boolean;
  minimizeToTray?: boolean;
  notificationsEnabled?: boolean;
  maxCommentsPerDay?: number;
  maxPostsPerDay?: number;
  maxSuggestionsPerRun?: number;
  actionTtlHours?: number;
  nimModel?: string;
  nimApiKey?: string;
  githubRepoOwner?: string;
  githubRepoName?: string;
  githubDispatchPat?: string;
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
}

declare global {
  interface Window {
    api: ElectronAPI;
  }
}
