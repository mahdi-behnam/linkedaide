import React from "react";
import { Check, ArrowClockwise } from "../../components/icons";

interface UnsavedChangesBarProps {
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export const UnsavedChangesBar: React.FC<UnsavedChangesBarProps> = ({
  isSaving,
  onSave,
  onDiscard,
}) => {
  return (
    <div
      data-testid="unsaved-changes-bar"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 max-w-lg w-[calc(100%-2rem)] sm:w-auto animate-in fade-in slide-in-from-bottom-4 duration-200"
    >
      <div className="flex items-center justify-between sm:justify-start gap-3 sm:gap-5 px-4 py-2.5 rounded-xl bg-surface-container-highest/95 border border-primary/40 shadow-2xl backdrop-blur-md text-on-surface">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-on-surface whitespace-nowrap">
            Careful — you have unsaved changes!
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            data-testid="discard-settings-btn"
            disabled={isSaving}
            onClick={onDiscard}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-outline hover:bg-surface-container text-on-surface transition-colors cursor-pointer disabled:opacity-50"
          >
            Discard
          </button>
          <button
            type="button"
            data-testid="save-settings-btn"
            disabled={isSaving}
            onClick={onSave}
            className="px-3.5 py-1.5 text-xs font-semibold rounded-md bg-primary hover:bg-primary-container text-on-primary shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50 active:scale-[0.98]"
          >
            {isSaving ? (
              <ArrowClockwise size={13} className="animate-spin text-on-primary" />
            ) : (
              <Check size={13} weight="bold" />
            )}
            <span>{isSaving ? "Saving..." : "Save Changes"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
