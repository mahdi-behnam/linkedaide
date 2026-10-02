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
    <section className="bg-surface-container-lowest rounded-xl p-5 border border-outline shadow-2xs flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Lightning size={17} weight="bold" />
          </div>
          <h2 className="headline-sm text-on-surface">Daily Rate Limit Burn-Down</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="code-sm px-2 py-0.5 rounded bg-surface-container-low text-on-surface-variant border border-outline">
            Resets 00:00 UTC
          </span>
          <span className="label-sm px-2 py-0.5 rounded-full bg-tertiary/10 text-tertiary font-semibold border border-tertiary/20">
            Within Limits
          </span>
        </div>
      </div>

      <p className="body-md text-on-surface-variant -mt-1">
        Autonomous safety circuit breakers automatically throttle dispatch actions to protect account health.
      </p>

      {/* 3 Progress Rows */}
      <div className="flex flex-col gap-3.5 pt-1">
        {/* Progress Row 1: Comments Executed */}
        <div
          data-testid="quota-card"
          className="p-3.5 rounded-xl bg-surface-container-low border border-outline/70 flex flex-col gap-2 transition-all hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface">Comments Executed</span>
              <span className="code-sm text-on-surface-variant">· Target &lt; 15/day</span>
            </div>
            <div className="flex items-baseline gap-1 body-strong">
              <span className="text-on-surface font-bold">{quota.commentsExecuted}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.commentsMax}</span>
              <span className="code-sm text-on-surface-variant ml-1.5 font-normal">
                ({commentsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={commentsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${commentsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant code-sm">
            <span>Safe pace: ~1.2 per hour</span>
            <span className="text-tertiary font-medium">{commentsRemaining} remaining today</span>
          </div>
        </div>

        {/* Progress Row 2: Posts Published */}
        <div
          data-testid="quota-card"
          className="p-3.5 rounded-xl bg-surface-container-low border border-outline/70 flex flex-col gap-2 transition-all hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface">Posts Published</span>
              <span className="code-sm text-on-surface-variant">· Target &lt; 3/day</span>
            </div>
            <div className="flex items-baseline gap-1 body-strong">
              <span className="text-on-surface font-bold">{quota.postsExecuted}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.postsMax}</span>
              <span className="code-sm text-on-surface-variant ml-1.5 font-normal">
                ({postsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={postsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${postsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant code-sm">
            <span>Slot 2 scheduled at 14:00 UTC</span>
            <span className="text-tertiary font-medium">{postsRemaining} remaining today</span>
          </div>
        </div>

        {/* Progress Row 3: Suggestions Reviewed */}
        <div
          data-testid="quota-card"
          className="p-3.5 rounded-xl bg-surface-container-low border border-outline/70 flex flex-col gap-2 transition-all hover:border-outline-variant"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="body-strong text-on-surface">Suggestions Reviewed</span>
              <span className="code-sm text-on-surface-variant">· Daily queue quota</span>
            </div>
            <div className="flex items-baseline gap-1 body-strong">
              <span className="text-on-surface font-bold">{quota.suggestionsSent}</span>
              <span className="text-on-surface-variant font-normal">/ {quota.suggestionsMax}</span>
              <span className="code-sm text-on-surface-variant ml-1.5 font-normal">
                ({suggestionsPct}%)
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
            <div
              role="progressbar"
              aria-valuenow={suggestionsPct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="bg-primary h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${suggestionsPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-on-surface-variant code-sm">
            <span>{pendingCount} pending in triage queue</span>
            <span className="text-on-surface-variant">{suggestionsRemaining} quota remaining</span>
          </div>
        </div>
      </div>
    </section>
  );
};
