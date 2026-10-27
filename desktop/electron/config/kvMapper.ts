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

  return settings;
}
