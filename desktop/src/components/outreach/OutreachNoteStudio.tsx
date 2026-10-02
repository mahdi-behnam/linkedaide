import React from "react";
import { ChatText, X, Check } from "@phosphor-icons/react";
import { ConnectionRequestAction } from "../../types";

export type OutreachToneType = "casual" | "technical" | "concise";

interface OutreachNoteStudioProps {
  candidate: ConnectionRequestAction;
  noteText: string;
  onNoteChange: (text: string) => void;
  onToneSelect: (tone: OutreachToneType) => void;
  onApprove: () => void;
  onReject: () => void;
  isProcessing: boolean;
}

export const OutreachNoteStudio: React.FC<OutreachNoteStudioProps> = ({
  candidate,
  noteText,
  onNoteChange,
  onToneSelect,
  onApprove,
  onReject,
  isProcessing,
}) => {
  const charCount = noteText.length;
  const isOverLimit = charCount > 300;
  const isWarning = charCount > 280 && charCount <= 300;

  return (
    <div className="rounded-lg border border-outline/70 bg-surface-container-lowest p-4 shadow-2xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ChatText size={16} className="text-primary" />
          <h3 className="text-sm font-semibold text-on-surface">Personalized Note</h3>
        </div>

        {/* Character countdown pill */}
        <div
          data-testid="char-count-pill"
          className={`rounded-[4px] border px-2 py-0.5 font-mono text-[11px] tabular-nums ${
            isOverLimit
              ? "border-error/40 bg-error/10 font-bold text-error"
              : isWarning
              ? "border-amber-500/40 bg-amber-500/10 font-medium text-amber-500"
              : "border-outline bg-surface-container text-on-surface-variant"
          }`}
        >
          {charCount} / 300 chars
        </div>
      </div>

      {/* Character Progress Bar */}
      <div className="mt-2.5 h-1 w-full overflow-hidden rounded-xs bg-surface-container-high">
        <div
          data-testid="char-progress-bar"
          className={`h-full rounded-xs transition-all duration-150 ${
            isOverLimit
              ? "bg-error"
              : isWarning
              ? "bg-amber-500"
              : "bg-tertiary"
          }`}
          style={{ width: `${Math.min(100, (charCount / 300) * 100)}%` }}
        />
      </div>

      {/* Tone Quick-Pills */}
      <div className="mt-3.5 flex items-center gap-2">
        <span className="text-xs text-on-surface-variant font-medium">Tone:</span>
        <button
          type="button"
          data-testid="tone-pill-casual"
          onClick={() => onToneSelect("casual")}
          className="flex items-center gap-1 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs text-on-surface transition hover:bg-surface-container-high hover:border-primary/40"
        >
          <span>Casual</span>
        </button>
        <button
          type="button"
          data-testid="tone-pill-technical"
          onClick={() => onToneSelect("technical")}
          className="flex items-center gap-1 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs text-on-surface transition hover:bg-surface-container-high hover:border-primary/40"
        >
          <span>Technical</span>
        </button>
        <button
          type="button"
          data-testid="tone-pill-concise"
          onClick={() => onToneSelect("concise")}
          className="flex items-center gap-1 rounded-md border border-outline bg-surface-container px-2.5 py-1 text-xs text-on-surface transition hover:bg-surface-container-high hover:border-primary/40"
        >
          <span>Concise</span>
        </button>
      </div>

      {/* Textarea */}
      <div className="mt-3">
        <textarea
          data-testid="note-editor-textarea"
          rows={4}
          value={noteText}
          onChange={(e) => onNoteChange(e.target.value)}
          placeholder="Add a personalized note to accompany your connection request (max 300 chars)..."
          className={`w-full rounded-md border bg-surface-container-low/70 p-3 text-xs leading-relaxed text-on-surface placeholder:text-on-surface-variant transition focus:outline-none focus:ring-1 ${
            isOverLimit
              ? "border-error focus:border-error focus:ring-error/20"
              : "border-outline focus:border-primary focus:ring-primary/20"
          }`}
        />
      </div>

      {isOverLimit && (
        <p
          data-testid="limit-warning-text"
          className="mt-1 text-xs font-medium text-error"
        >
          Note exceeds the strict 300 character limit by {charCount - 300} characters. Please shorten it before sending.
        </p>
      )}
      {isWarning && (
        <p
          data-testid="approaching-warning-text"
          className="mt-1 text-xs font-medium text-amber-500"
        >
          Approaching 300 character limit ({300 - charCount} characters remaining).
        </p>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex items-center justify-end gap-2 border-t border-outline/50 pt-3">
        <button
          type="button"
          data-testid="reject-button"
          onClick={onReject}
          disabled={isProcessing || candidate.status === "rejected"}
          className="flex items-center gap-1.5 rounded-md border border-outline bg-surface-container px-3 py-1.5 text-xs font-medium text-error transition hover:bg-error/10 hover:border-error/30 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <X size={14} weight="bold" />
          <span>Reject</span>
        </button>

        <button
          type="button"
          data-testid="approve-button"
          onClick={onApprove}
          disabled={
            isProcessing ||
            isOverLimit ||
            candidate.status === "approved" ||
            candidate.status === "sent"
          }
          className="flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary px-3 py-1.5 text-xs font-medium text-on-primary shadow-2xs transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:border-outline disabled:bg-surface-container disabled:text-on-surface-variant"
        >
          <Check size={14} weight="bold" />
          <span>
            {candidate.status === "approved"
              ? "Approved"
              : "Approve & Send Invitation"}
          </span>
        </button>
      </div>
    </div>
  );
};
