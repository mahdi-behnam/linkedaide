import React from "react";
import { DailyQuota } from "../../types";
import { Lightning } from "../icons";

export interface RateLimitBurnDownProps {
  quota: DailyQuota;
  pendingCount?: number;
}

export const RateLimitBurnDown: React.FC<RateLimitBurnDownProps> = ({
  quota,
  pendingCount = 0,
}) => {
  const commentsPct = quota.commentsMax > 0
    ? Math.min(100, Math.round((quota.commentsExecuted / quota.commentsMax) * 100))
    : 0;
  const postsPct = quota.postsMax > 0
    ? Math.min(100, Math.round((quota.postsExecuted / quota.postsMax) * 100))
    : 0;
  const suggestionsPct = quota.suggestionsMax > 0
    ? Math.min(100, Math.round((quota.suggestionsSent / quota.suggestionsMax) * 100))
    : 0;

  const commentsRemaining = Math.max(0, quota.commentsMax - quota.commentsExecuted);
  const postsRemaining = Math.max(0, quota.postsMax - quota.postsExecuted);
  const suggestionsRemaining = Math.max(0, quota.suggestionsMax - quota.suggestionsSent);

  return (
    <section className="bg-surface-bright rounded-lg p-4 border border-outline shadow-2xs flex flex-col gap-3.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Lightning size={14} weight="bold" />
          </div>
          <h2 className="text-sm font-semibold text-on-surface">Daily Rate Limit Burn-Down</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant border border-outline font-sans">
            Resets 00:00 UTC
          </span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-[4px] bg-tertiary/10 text-tertiary font-medium border border-tertiary/20">
            Within Limits
          </span>
        </div>
      </div>

      <p className="body-md text-on-surface-variant -mt-1 text-xs">
        Autonomous safety circuit breakers automatically throttle dispatch actions to protect account health.
      </p>

      {/* 3 Progress Rows */}
      <div className="flex flex-col gap-2.5 pt-0.5">
        {/* Progress Row 1: Comments Executed */}
        <div
          data-testid="quota-card"
          className="p-3 rounded-md bg-surface-container-low border border-outline/50 flex flex-col gap-2 transition-colors hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface text-xs">Comments Executed</span>
              <span className="text-[11px] text-on-surface-variant font-sans">· Target &lt; 15/day</span>
            </div>
            <div className="flex items-baseline gap-1 text-xs tabular-nums">
              <span className="text-on-surface font-semibold">{quota.commentsExecuted}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.commentsMax}</span>
              <span className="text-[11px] text-on-surface-variant ml-1 font-normal">
                ({commentsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-xs overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={commentsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-xs transition-all duration-300 ease-out"
              style={{ width: `${commentsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant text-[11px]">
            <span>Safe pace: ~1.2 per hour</span>
            <span className="text-tertiary font-medium tabular-nums">{commentsRemaining} remaining today</span>
          </div>
        </div>

        {/* Progress Row 2: Posts Published */}
        <div
          data-testid="quota-card"
          className="p-3 rounded-md bg-surface-container-low border border-outline/50 flex flex-col gap-2 transition-colors hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface text-xs">Posts Published</span>
              <span className="text-[11px] text-on-surface-variant font-sans">· Target &lt; 3/day</span>
            </div>
            <div className="flex items-baseline gap-1 text-xs tabular-nums">
              <span className="text-on-surface font-semibold">{quota.postsExecuted}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.postsMax}</span>
              <span className="text-[11px] text-on-surface-variant ml-1 font-normal">
                ({postsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-xs overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={postsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-xs transition-all duration-300 ease-out"
              style={{ width: `${postsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant text-[11px]">
            <span>Slot 2 scheduled at 14:00 UTC</span>
            <span className="text-tertiary font-medium tabular-nums">{postsRemaining} remaining today</span>
          </div>
        </div>

        {/* Progress Row 3: Suggestions Reviewed */}
        <div
          data-testid="quota-card"
          className="p-3 rounded-md bg-surface-container-low border border-outline/50 flex flex-col gap-2 transition-colors hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface text-xs">Suggestions Reviewed</span>
              <span className="text-[11px] text-on-surface-variant font-sans">· Daily queue quota</span>
            </div>
            <div className="flex items-baseline gap-1 text-xs tabular-nums">
              <span className="text-on-surface font-semibold">{quota.suggestionsSent}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.suggestionsMax}</span>
              <span className="text-[11px] text-on-surface-variant ml-1 font-normal">
                ({suggestionsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-xs overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={suggestionsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-xs transition-all duration-300 ease-out"
              style={{ width: `${suggestionsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant text-[11px]">
            <span>{pendingCount} pending in triage queue</span>
            <span className="text-on-surface-variant tabular-nums">{suggestionsRemaining} quota remaining</span>
          </div>
        </div>
      </div>
    </section>
  );
};
