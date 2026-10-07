/**
 * Type definitions for Telegram Relay Worker.
 */

export interface Env {
  TELEGRAM_WEBHOOK_SECRET: string;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_AUTHORIZED_CHAT_ID: string;
  GITHUB_DISPATCH_PAT: string;
  GITHUB_REPO_OWNER: string;
  GITHUB_REPO_NAME: string;
  LINKEDIN_AGENT_KV?: KVNamespace;
  SCREENSHOTS_BUCKET?: R2Bucket;
  DESKTOP_API_SECRET?: string;
  NVIDIA_NIM_API_KEY?: string;
  LLM_BASE_URL?: string;
  NIM_MODEL_PRIMARY?: string;
  LLM_MODEL?: string;
}

export interface TelegramCallbackQuery {
  id: string;
  from: {
    id: number;
    is_bot: boolean;
    first_name: string;
    username?: string;
  };
  message?: {
    message_id: number;
    chat: {
      id: number;
    };
  };
  data?: string;
}

export interface TelegramUpdate {
  update_id: number;
  callback_query?: TelegramCallbackQuery;
  message?: {
    message_id: number;
    from?: {
      id: number;
      is_bot?: boolean;
      first_name?: string;
      username?: string;
    };
    chat?: {
      id: number;
    };
    text?: string;
    reply_to_message?: unknown;
  };
}

export interface AutomatedCommentWindow {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  days: string[];
  status: "active" | "standby" | "paused";
  topic_filter: string;
  local_start_time?: string;
  local_end_time?: string;
  timezone?: string;
  last_dispatched_at?: string | null;
}
