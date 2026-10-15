import React from "react";
import { SlidersHorizontal, WarningCircle, ThumbsUp } from "../../components/icons";

export type ReactionType = "like" | "celebrate" | "support" | "love" | "insightful" | "funny";

interface ScoutEngineCardProps {
  feedScrollScreens: number;
  candidatePoolMultiplier: number;
  minTriageConfidence: number;
  maxCommentWords: number;
  enablePreCommentReaction: boolean;
  defaultReactionType: ReactionType;
  onScrollScreensChange: (screens: number) => void;
  onMultiplierChange: (multiplier: number) => void;
  onConfidenceChange: (confidence: number) => void;
  onMaxWordsChange: (words: number) => void;
  onPreReactionToggle: (enabled: boolean) => void;
  onReactionTypeChange: (type: ReactionType) => void;
}

export const ScoutEngineCard: React.FC<ScoutEngineCardProps> = ({
  feedScrollScreens,
  candidatePoolMultiplier,
  minTriageConfidence,
  maxCommentWords,
  enablePreCommentReaction,
  defaultReactionType,
  onScrollScreensChange,
  onMultiplierChange,
  onConfidenceChange,
  onMaxWordsChange,
  onPreReactionToggle,
  onReactionTypeChange,
}) => {
  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex items-center gap-2.5 pb-1 border-b border-surface-container-high">
        <div className="w-8 h-8 rounded-md bg-purple-500/10 flex items-center justify-center text-purple-500 shrink-0">
          <SlidersHorizontal size={16} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Scout Engine &amp; Scraping Parameters
          </h2>
          <p className="font-label-sm text-[11px] text-on-surface-variant">
            DOM feed scroll depth, candidate discovery multipliers, and comment drafting parameters
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* Feed Scroll Depth */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="feed-scroll-depth-select"
              className="font-body-strong text-body-strong text-on-surface text-[12px]"
            >
              Feed Scroll Depth
            </label>
            {feedScrollScreens >= 4 && (
              <span className="font-label-sm text-[10px] text-amber-500 flex items-center gap-1">
                <WarningCircle size={11} weight="fill" />
                <span>Stealth risk elevated</span>
              </span>
            )}
          </div>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-purple-500">
            <select
              id="feed-scroll-depth-select"
              value={feedScrollScreens}
              onChange={(e) => onScrollScreensChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              <option value={1}>1 Screen (~500–900 px - Ultra Fast)</option>
              <option value={2}>2 Screens (~1,000–1,800 px - Recommended)</option>
              <option value={3}>3 Screens (~1,500–2,700 px - Deeper Scan)</option>
              <option value={4}>4 Screens (~2,000–3,600 px - Extended)</option>
              <option value={5}>5 Screens (~2,500–4,500 px - Maximum Depth)</option>
            </select>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Number of screen heights the scraper smoothly traverses (~500–900px per screen). Higher depths scan older posts but increase runtime and LinkedIn challenge risk (2 screens recommended).
          </span>
        </div>

        {/* Candidate Pool Multiplier */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="candidate-multiplier-select"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Candidate Pool Multiplier
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-purple-500">
            <select
              id="candidate-multiplier-select"
              value={candidatePoolMultiplier}
              onChange={(e) => onMultiplierChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              <option value={2}>2x Suggestions (Lean &amp; Fast)</option>
              <option value={3}>3x Suggestions (Default / Balanced)</option>
              <option value={4}>4x Suggestions (Broad Exploration)</option>
              <option value={5}>5x Suggestions (Exhaustive Candidate Pool)</option>
            </select>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Exploration ratio relative to your suggestion quota. At 3x with 3 suggestions, the scraper harvests up to 9 unseen posts for triage.
          </span>
        </div>

        {/* Minimum Triage Confidence */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="min-triage-confidence-slider"
              className="font-body-strong text-body-strong text-on-surface text-[12px]"
            >
              Min Triage Confidence
            </label>
            <span className="font-code-sm text-[11px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface font-mono">
              {Math.round(minTriageConfidence * 100)}%
            </span>
          </div>
          <div className="flex items-center gap-3 px-3 py-2 rounded-md bg-surface-container-low border border-outline-variant/30">
            <input
              id="min-triage-confidence-slider"
              type="range"
              min={0.5}
              max={0.9}
              step={0.05}
              value={minTriageConfidence}
              onChange={(e) => onConfidenceChange(Number(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Minimum AI confidence score required to qualify a post for comment drafting. Posts below this score are logged as confidence_below_threshold.
          </span>
        </div>

        {/* Max Comment Words */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="max-comment-words-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Max Comment Words
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-purple-500">
            <input
              id="max-comment-words-input"
              type="number"
              min={20}
              max={150}
              step={5}
              value={maxCommentWords}
              onChange={(e) => onMaxWordsChange(Number(e.target.value))}
              className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[13px] p-0 focus:ring-0"
            />
            <span className="font-code-sm text-[11px] text-on-surface-variant ml-2 shrink-0">
              words
            </span>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Target word count ceiling for AI-drafted replies. Keeps comments concise, punchy, and authoritative.
          </span>
        </div>
      </div>

      {/* Pre-Comment Reaction Controls */}
      <div className="pt-2.5 border-t border-surface-container-high flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <label className="flex items-center gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={enablePreCommentReaction}
            onChange={(e) => onPreReactionToggle(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-outline text-primary focus:ring-primary cursor-pointer accent-primary"
          />
          <div className="flex flex-col gap-0.5">
            <span className="font-body-strong text-on-surface text-[13px] flex items-center gap-1.5">
              <ThumbsUp size={13} className="text-primary inline" />
              <span>Organic Pre-Comment Reaction</span>
            </span>
            <span className="font-body-md text-on-surface-variant text-[11px]">
              Attaches an organic reaction before posting an approved comment, mirroring natural human interaction.
            </span>
          </div>
        </label>

        {enablePreCommentReaction && (
          <div className="flex items-center gap-2 shrink-0 pl-6 sm:pl-0">
            <label
              htmlFor="default-reaction-type-select"
              className="font-body-strong text-on-surface text-[12px] shrink-0"
            >
              Type:
            </label>
            <div className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-primary">
              <select
                id="default-reaction-type-select"
                value={defaultReactionType}
                onChange={(e) => onReactionTypeChange(e.target.value as ReactionType)}
                className="bg-transparent border-0 outline-none font-body-md text-on-surface text-[12px] p-0 focus:ring-0 cursor-pointer capitalize"
              >
                <option value="like">Like (Default)</option>
                <option value="insightful">Insightful</option>
                <option value="celebrate">Celebrate</option>
                <option value="support">Support</option>
                <option value="love">Love</option>
                <option value="funny">Funny</option>
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
