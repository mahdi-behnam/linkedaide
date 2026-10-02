import React, { RefObject } from "react";
import {
  Check,
  X,
  ArrowClockwise,
  Tag,
  ArrowCounterClockwise,
  MagicWand,
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
          className="text-xs font-semibold text-on-surface"
        >
          Proposed Response Draft
        </label>
        <div className="flex items-center gap-2">
          <span
            data-testid="char-word-counter"
            className="text-[11px] text-on-surface-variant font-sans tabular-nums"
          >
            {charCount} chars · {wordCount} words
          </span>

          {isSweetSpot ? (
            <span
              data-testid="sweet-spot-badge"
              className="inline-flex items-center gap-1 text-[11px] font-medium text-tertiary"
            >
              <Check size={11} weight="bold" />
              Sweet Spot
            </span>
          ) : (
            <span
              data-testid="length-indicator"
              className="text-[11px] text-on-surface-variant font-sans"
            >
              {charCount < 150 ? "Target: 150-350 chars" : "Long (> 350)"}
            </span>
          )}
        </div>
      </div>

      {/* Focused Text Editing Area */}
      <div className="p-3.5 rounded-lg bg-surface-bright border border-outline shadow-2xs flex flex-col gap-2.5 focus-within:border-primary/60 transition-colors">
        <textarea
          ref={textareaRef}
          id="responseEditor"
          data-testid="draft-editor-textarea"
          aria-label="Comment Draft Editor"
          value={draftText}
          onChange={(e) => onDraftChange(e.target.value)}
          rows={5}
          placeholder="Refine response text before dispatch..."
          className="w-full bg-transparent border-0 outline-none text-xs text-on-surface resize-none leading-relaxed placeholder:text-on-surface-variant"
        />

        {/* Tone Selector & Formatting Controls */}
        <div className="pt-2 border-t border-outline/50 flex flex-wrap items-center justify-between gap-2">
          {/* Segmented Tone Selector (macOS native segmented control) */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-md bg-surface-container-low border border-outline/50">
            {TONE_OPTIONS.map((opt) => {
              const isSelected = activeRewriteTone === opt.tone;
              return (
                <button
                  key={opt.tone}
                  type="button"
                  data-testid={`tone-pill-${opt.tone}`}
                  disabled={!!activeRewriteTone || isProcessing}
                  onClick={() => onRewrite(opt.tone)}
                  className={`px-2 py-0.5 rounded-sm text-[11px] transition-colors whitespace-nowrap shrink-0 flex items-center gap-1 disabled:opacity-50 ${
                    isSelected
                      ? "bg-surface-bright text-on-surface shadow-2xs font-medium"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  {isSelected && (
                    <ArrowClockwise size={11} className="animate-spin text-primary" />
                  )}
                  <span>{opt.label}</span>
                </button>
              );
            })}
          </div>

          {/* Quick Formatting Actions & Voice Dictation */}
          <div className="flex items-center gap-0.5 text-on-surface-variant">
            <button
              type="button"
              onClick={handleAddHashtag}
              title="Add Hashtags"
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <Tag size={13} />
            </button>
            <button
              type="button"
              onClick={() => onRewrite("technical")}
              title="Check Tone & Grammar"
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <MagicWand size={13} />
            </button>
            <button
              type="button"
              onClick={handleResetDraft}
              title="Discard Edits"
              className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <ArrowCounterClockwise size={13} />
            </button>

            <div className="mx-1 h-3.5 w-px bg-outline/60" />

            {/* Embedded Voice Dictation Button */}
            <VoiceDictationButton
              onTranscript={(text) => {
                onDraftChange(draftText ? `${draftText} ${text}` : text);
              }}
            />
          </div>
        </div>

        {/* Bottom Workspace Action Buttons */}
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2 border-t border-outline/50 pt-2.5">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              data-testid="regenerate-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onRegenerate}
              className="flex items-center gap-1 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-high active:scale-[0.99] disabled:opacity-50"
            >
              <ArrowClockwise
                size={12}
                className={
                  activeRewriteTone === "regenerate"
                    ? "animate-spin text-primary"
                    : ""
                }
              />
              <span>Regenerate</span>
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              data-testid="reject-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onReject}
              className="flex items-center gap-1 rounded-md border border-error/30 bg-error/10 px-2.5 py-1 text-xs font-medium text-error transition-colors hover:bg-error/20 active:scale-[0.99] disabled:opacity-50"
            >
              <X size={12} weight="bold" />
              <span>Reject</span>
              <kbd className="ml-0.5 rounded border border-error/30 bg-error/10 px-1 py-0.2 font-sans text-[10px] text-error">
                R
              </kbd>
            </button>

            <button
              type="button"
              data-testid="approve-action-btn"
              disabled={isProcessing || !!activeRewriteTone}
              onClick={onApprove}
              className="flex items-center gap-1 rounded-md border border-primary/40 bg-primary px-3 py-1 text-xs font-medium text-on-primary transition-colors hover:bg-primary-container active:scale-[0.99] disabled:opacity-50 shadow-2xs"
            >
              <Check size={12} weight="bold" />
              <span>Approve &amp; Queue</span>
              <kbd className="ml-0.5 rounded border border-white/20 bg-white/15 px-1 py-0.2 font-sans text-[10px] text-on-primary">
                A
              </kbd>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
