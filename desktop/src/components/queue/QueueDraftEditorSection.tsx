import React, { RefObject } from "react";
import {
  Check,
  X,
  ArrowClockwise,
  Tag,
  ArrowCounterClockwise,
  MagicWand,
  Sparkle,
} from "@phosphor-icons/react";
import { VoiceDictationButton } from "../VoiceDictationButton";

interface ToneOption {
  label: string;
  tone: string;
}

const TONE_OPTIONS: ToneOption[] = [
  { label: "Technical Deep Dive", tone: "technical" },
  { label: "Inquisitive Question", tone: "inquisitive" },
  { label: "Contrarian Stance", tone: "contrarian" },
  { label: "Short & Punchy", tone: "shorter" },
];

interface QueueDraftEditorSectionProps {
  draftText: string;
  onDraftChange: (text: string) => void;
  onRewrite: (tone: string) => void;
  activeRewriteTone: string | null;
  onApprove: () => void;
  onReject: () => void;
  onRegenerate: () => void;
  isProcessing: boolean;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  initialDraftText?: string;
}

export const QueueDraftEditorSection: React.FC<QueueDraftEditorSectionProps> = ({
  draftText,
  onDraftChange,
  onRewrite,
  activeRewriteTone,
  onApprove,
  onReject,
  onRegenerate,
  isProcessing,
  textareaRef,
  initialDraftText,
}) => {
  const charCount = draftText.length;
  const wordCount = draftText.trim()
    ? draftText.trim().split(/\s+/).length
    : 0;
  const isSweetSpot =
    charCount >= 150 && charCount <= 350 && wordCount >= 25 && wordCount <= 60;

  const handleResetDraft = () => {
    if (initialDraftText) {
      onDraftChange(initialDraftText);
    }
  };

  const handleAddHashtag = () => {
    onDraftChange(draftText ? `${draftText} #AI #Automation` : "#AI #Automation");
  };

  return (
    <section className="flex flex-col gap-3">
      {/* Header with Char/Word Counter & Sweet Spot Badge */}
      <div className="flex items-center justify-between">
        <label
          htmlFor="responseEditor"
          className="font-headline-sm text-on-surface"
        >
          Proposed Response Draft
        </label>
        <div className="flex items-center gap-2">
          <span
            data-testid="char-word-counter"
            className="font-label-md text-on-surface-variant font-mono"
          >
            {charCount} chars · {wordCount} words
          </span>

          {isSweetSpot ? (
            <span
              data-testid="sweet-spot-badge"
              className="inline-flex items-center gap-1 rounded-full border border-tertiary/30 bg-tertiary/10 px-2 py-0.5 text-label-sm font-semibold text-tertiary"
            >
              <Check size={11} weight="bold" />
              Sweet Spot
            </span>
          ) : (
            <span
              data-testid="length-indicator"
              className="rounded-full border border-outline bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant"
            >
              {charCount < 150 ? "Target: 150-350 chars" : "Long (> 350)"}
            </span>
          )}
        </div>
      </div>

      {/* Calm, Focused Text Editing Area */}
      <div className="p-4 rounded-2xl bg-surface-container-lowest border border-outline/60 shadow-xs flex flex-col gap-3 focus-within:border-primary/60 focus-within:shadow-md transition-all">
        <textarea
          ref={textareaRef}
          id="responseEditor"
          data-testid="draft-editor-textarea"
          aria-label="Comment Draft Editor"
          value={draftText}
          onChange={(e) => onDraftChange(e.target.value)}
          rows={5}
          placeholder="Refine response text before dispatch..."
          className="w-full bg-transparent border-0 outline-none font-body-lg text-on-surface resize-none leading-relaxed placeholder:text-on-surface-variant"
        />

        {/* Tone Selector & Formatting Controls */}
        <div className="pt-2 border-t border-outline/40 flex flex-wrap items-center justify-between gap-2">
          {/* Segmented Tone Selector (Things 3 / Apple segmented design) */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-container-low flex-wrap border border-outline/40">
            {TONE_OPTIONS.map((opt) => {
              const isSelected = activeRewriteTone === opt.tone;
              return (
                <button
                  key={opt.tone}
                  type="button"
                  data-testid={`tone-pill-${opt.tone}`}
                  disabled={!!activeRewriteTone || isProcessing}
                  onClick={() => onRewrite(opt.tone)}
                  className={`px-2.5 py-1 rounded-lg font-label-md transition-all whitespace-nowrap shrink-0 flex items-center gap-1.5 active:scale-[0.98] disabled:opacity-50 ${
                    isSelected
                      ? "bg-surface-container-lowest text-on-surface shadow-xs font-semibold ring-1 ring-primary/20"
                      : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                  }`}
                >
                  {isSelected ? (
                    <ArrowClockwise size={12} className="animate-spin text-primary" />
                  ) : (
                    <Sparkle size={12} className="text-on-surface-variant" />
                  )}
                  <span>{opt.label}</span>
                </button>
              );
            })}
          </div>

          {/* Quick Formatting Actions & Voice Dictation */}
          <div className="flex items-center gap-1 text-on-surface-variant">
            <button
              type="button"
              onClick={handleAddHashtag}
              title="Add Hashtags"
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <Tag size={16} />
            </button>
            <button
              type="button"
              onClick={() => onRewrite("technical")}
              title="Check Tone & Grammar"
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <MagicWand size={16} />
            </button>
            <button
              type="button"
              onClick={handleResetDraft}
              title="Discard Edits"
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <ArrowCounterClockwise size={16} />
            </button>

            <div className="mx-1 h-4 w-px bg-outline/60" />

            {/* Embedded Voice Dictation Button */}
            <VoiceDictationButton
              onTranscript={(text) => {
                onDraftChange(draftText ? `${draftText} ${text}` : text);
              }}
            />
          </div>
        </div>

        {/* Bottom Workspace Action Buttons */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-outline/40 pt-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="regenerate-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onRegenerate}
              className="flex items-center gap-1.5 rounded-lg border border-outline bg-surface-container px-3 py-1.5 text-xs font-medium text-on-surface transition-all hover:bg-surface-container-high active:scale-[0.98] disabled:opacity-50"
            >
              <ArrowClockwise
                size={13}
                className={
                  activeRewriteTone === "regenerate"
                    ? "animate-spin text-primary"
                    : ""
                }
              />
              <span>Regenerate</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="reject-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onReject}
              className="flex items-center gap-1.5 rounded-lg border border-error/30 bg-error/10 px-3.5 py-1.5 text-xs font-medium text-error transition-all hover:bg-error/20 active:scale-[0.98] disabled:opacity-50"
            >
              <X size={13} weight="bold" />
              <span>Reject</span>
              <kbd className="ml-1 rounded border border-error/30 bg-error/10 px-1.5 py-0.5 font-mono text-[10px] text-error">
                R
              </kbd>
            </button>

            <button
              type="button"
              data-testid="approve-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onApprove}
              className="flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary px-4 py-1.5 text-xs font-semibold text-on-primary transition-all hover:bg-primary-container active:scale-[0.98] disabled:opacity-50 shadow-xs"
            >
              <Check size={13} weight="bold" />
              <span>Approve & Queue</span>
              <kbd className="ml-1 rounded border border-white/20 bg-white/15 px-1.5 py-0.5 font-mono text-[10px] text-on-primary">
                A
              </kbd>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
