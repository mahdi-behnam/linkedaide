/**
 * Bi-directional mapper between DesktopSettings (camelCase) and
 * Cloudflare KV config:runtime (snake_case) payloads.
 */

import type { DesktopSettings } from "../types";

/**
 * Transforms Desktop settings into a standard Cloudflare KV config:runtime record.
 */
export function desktopToKvConfig(
  settings: Partial<DesktopSettings>
): Record<string, unknown> {
  const kv: Record<string, unknown> = {};

  if (settings.nimModel !== undefined) {
    kv.nim_model_primary = settings.nimModel;
  }
  if (settings.nimModelFallback !== undefined) {
    kv.nim_model_fallback = settings.nimModelFallback;
  }
  if (settings.llmProvider !== undefined) {
    kv.llm_provider = settings.llmProvider;
  }
  if (settings.userPersona !== undefined) {
    kv.user_persona = settings.userPersona;
  }
  if (settings.userFocusAreas !== undefined) {
    kv.user_focus_areas = settings.userFocusAreas;
  }
  if (settings.targetHashtags !== undefined) {
    kv.target_hashtags = settings.targetHashtags;
  }
  if (settings.scoutTargetUrls !== undefined) {
    kv.scout_target_urls = settings.scoutTargetUrls;
  }
  if (settings.maxCommentsPerDay !== undefined) {
    kv.max_comments_per_day = settings.maxCommentsPerDay;
  }
  if (settings.maxPostsPerDay !== undefined) {
    kv.max_posts_per_day = settings.maxPostsPerDay;
  }
  if (settings.maxConnectionsPerDay !== undefined) {
    kv.max_connections_per_day = settings.maxConnectionsPerDay;
  }
  if (settings.maxSuggestionsPerRun !== undefined) {
    kv.max_suggestions_per_run = settings.maxSuggestionsPerRun;
  }
  if (settings.actionTtlHours !== undefined) {
    kv.pending_action_ttl_hours = settings.actionTtlHours;
  }
  if (settings.maxCommentWords !== undefined) {
    kv.max_comment_words = settings.maxCommentWords;
  }
  if (settings.enablePreCommentReaction !== undefined) {
    kv.enable_pre_comment_reaction = settings.enablePreCommentReaction;
  }
  if (settings.defaultReactionType !== undefined) {
    kv.default_reaction_type = settings.defaultReactionType;
  }
  if (settings.feedScrollScreens !== undefined) {
    kv.scout_scroll_screens = settings.feedScrollScreens;
    kv.feed_scroll_screens = settings.feedScrollScreens;
  }
  if (settings.candidatePoolMultiplier !== undefined) {
    kv.candidate_pool_multiplier = settings.candidatePoolMultiplier;
  }
  if (settings.minTriageConfidence !== undefined) {
    kv.min_triage_confidence = settings.minTriageConfidence;
  }
  if (settings.dryRun !== undefined) {
    kv.dry_run = settings.dryRun;
  }
  if (settings.timezone !== undefined) {
    kv.timezone = settings.timezone;
  }
  // Telegram Human Approval Gateway
  if (settings.telegramBotToken !== undefined) {
    kv.telegram_bot_token = settings.telegramBotToken;
  }
  if (settings.telegramAuthorizedChatId !== undefined) {
    kv.telegram_authorized_chat_id = settings.telegramAuthorizedChatId;
  }
  // Multi-Provider Credentials
  if (settings.nimApiKey !== undefined) {
    kv.nvidia_nim_api_key = settings.nimApiKey;
  }
  if (settings.openaiApiKey !== undefined) {
    kv.openai_api_key = settings.openaiApiKey;
  }
  if (settings.anthropicApiKey !== undefined) {
    kv.anthropic_api_key = settings.anthropicApiKey;
  }
  if (settings.geminiApiKey !== undefined) {
    kv.gemini_api_key = settings.geminiApiKey;
  }
  if (settings.groqApiKey !== undefined) {
    kv.groq_api_key = settings.groqApiKey;
  }
  if (settings.ollamaBaseUrl !== undefined) {
    kv.ollama_base_url = settings.ollamaBaseUrl;
  }
  // Advanced Inference Hyperparameters
  if (settings.nimModelTriage !== undefined) {
    kv.nim_model_triage = settings.nimModelTriage;
  }
  if (settings.nimModelVision !== undefined) {
    kv.nim_model_vision = settings.nimModelVision;
  }
  if (settings.nimTemperature !== undefined) {
    kv.nim_temperature = settings.nimTemperature;
  }
  if (settings.nimTimeoutSeconds !== undefined) {
    kv.nim_timeout_seconds = settings.nimTimeoutSeconds;
  }
  if (settings.nimMaxTokens !== undefined) {
    kv.nim_max_tokens = settings.nimMaxTokens;
  }
  if (settings.nimBaseUrl !== undefined) {
    kv.nim_base_url = settings.nimBaseUrl;
  }
  // Network & Stealth Proxy
  if (settings.residentialProxyUrl !== undefined) {
    kv.residential_proxy_url = settings.residentialProxyUrl;
  }
  // Diagnostics & Telemetry
  if (settings.logLevel !== undefined) {
    kv.log_level = settings.logLevel;
  }

  return kv;
}

/**
 * Transforms a Cloudflare KV config:runtime record into DesktopSettings.
 */
export function kvConfigToDesktop(
  kv: Record<string, unknown>
): Partial<DesktopSettings> {
  const settings: Partial<DesktopSettings> = {};

  const primaryModel =
    kv.nim_model_primary || kv.llm_model_primary;
  if (primaryModel !== undefined && primaryModel !== null) {
    settings.nimModel = String(primaryModel);
  }

  const fallbackModel =
    kv.nim_model_fallback || kv.llm_model_fallback;
  if (fallbackModel !== undefined && fallbackModel !== null) {
    settings.nimModelFallback = String(fallbackModel);
  }

  if (kv.llm_provider !== undefined && kv.llm_provider !== null) {
    settings.llmProvider = String(kv.llm_provider);
  }

  if (kv.user_persona !== undefined && kv.user_persona !== null) {
    settings.userPersona = String(kv.user_persona);
  }

  if (Array.isArray(kv.user_focus_areas)) {
    settings.userFocusAreas = kv.user_focus_areas.map(String);
  }

  if (Array.isArray(kv.target_hashtags)) {
    settings.targetHashtags = kv.target_hashtags.map(String);
  }

  if (Array.isArray(kv.scout_target_urls)) {
    settings.scoutTargetUrls = kv.scout_target_urls.map(String);
  }

  if (typeof kv.max_comments_per_day === "number") {
    settings.maxCommentsPerDay = kv.max_comments_per_day;
  }

  if (typeof kv.max_posts_per_day === "number") {
    settings.maxPostsPerDay = kv.max_posts_per_day;
  }

  if (typeof kv.max_connections_per_day === "number") {
    settings.maxConnectionsPerDay = kv.max_connections_per_day;
  }

  if (typeof kv.max_suggestions_per_run === "number") {
    settings.maxSuggestionsPerRun = kv.max_suggestions_per_run;
  }

  if (typeof kv.pending_action_ttl_hours === "number") {
    settings.actionTtlHours = kv.pending_action_ttl_hours;
  }

  if (typeof kv.max_comment_words === "number") {
    settings.maxCommentWords = kv.max_comment_words;
  }

  if (typeof kv.enable_pre_comment_reaction === "boolean") {
    settings.enablePreCommentReaction = kv.enable_pre_comment_reaction;
  }

  if (typeof kv.default_reaction_type === "string") {
    settings.defaultReactionType = kv.default_reaction_type as any;
  }

  const scrollScreens = kv.scout_scroll_screens ?? kv.feed_scroll_screens;
  if (typeof scrollScreens === "number") {
    settings.feedScrollScreens = scrollScreens;
  }

  if (typeof kv.candidate_pool_multiplier === "number") {
    settings.candidatePoolMultiplier = kv.candidate_pool_multiplier;
  }

  if (typeof kv.min_triage_confidence === "number") {
    settings.minTriageConfidence = kv.min_triage_confidence;
  }

  if (typeof kv.dry_run === "boolean") {
    settings.dryRun = kv.dry_run;
  }

  if (typeof kv.timezone === "string") {
    settings.timezone = kv.timezone;
  }

  // Telegram Human Approval Gateway
  if (kv.telegram_bot_token !== undefined && kv.telegram_bot_token !== null) {
    settings.telegramBotToken = String(kv.telegram_bot_token);
  }
  if (kv.telegram_authorized_chat_id !== undefined && kv.telegram_authorized_chat_id !== null) {
    settings.telegramAuthorizedChatId = String(kv.telegram_authorized_chat_id);
  }

  // Multi-Provider Credentials
  if (kv.nvidia_nim_api_key !== undefined && kv.nvidia_nim_api_key !== null) {
    settings.nimApiKey = String(kv.nvidia_nim_api_key);
  }
  if (kv.openai_api_key !== undefined && kv.openai_api_key !== null) {
    settings.openaiApiKey = String(kv.openai_api_key);
  }
  if (kv.anthropic_api_key !== undefined && kv.anthropic_api_key !== null) {
    settings.anthropicApiKey = String(kv.anthropic_api_key);
  }
  if (kv.gemini_api_key !== undefined && kv.gemini_api_key !== null) {
    settings.geminiApiKey = String(kv.gemini_api_key);
  }
  if (kv.groq_api_key !== undefined && kv.groq_api_key !== null) {
    settings.groqApiKey = String(kv.groq_api_key);
  }
  if (kv.ollama_base_url !== undefined && kv.ollama_base_url !== null) {
    settings.ollamaBaseUrl = String(kv.ollama_base_url);
  }

  // Advanced Inference Hyperparameters
  const triageModel = kv.nim_model_triage || kv.llm_model_triage;
  if (triageModel !== undefined && triageModel !== null) {
    settings.nimModelTriage = String(triageModel);
  }
  const visionModel = kv.nim_model_vision || kv.llm_model_vision;
  if (visionModel !== undefined && visionModel !== null) {
    settings.nimModelVision = String(visionModel);
  }
  if (typeof kv.nim_temperature === "number") {
    settings.nimTemperature = kv.nim_temperature;
  }
  if (typeof kv.nim_timeout_seconds === "number") {
    settings.nimTimeoutSeconds = kv.nim_timeout_seconds;
  }
  if (typeof kv.nim_max_tokens === "number") {
    settings.nimMaxTokens = kv.nim_max_tokens;
  }
  if (kv.nim_base_url !== undefined && kv.nim_base_url !== null) {
    settings.nimBaseUrl = String(kv.nim_base_url);
  }

  // Network & Stealth Proxy
  if (kv.residential_proxy_url !== undefined && kv.residential_proxy_url !== null) {
    settings.residentialProxyUrl = String(kv.residential_proxy_url);
  }

  // Diagnostics & Telemetry
  if (typeof kv.log_level === "string") {
    settings.logLevel = kv.log_level as "DEBUG" | "INFO" | "WARNING" | "ERROR";
  }

  return settings;
}
