import React from "react";
import { WarningCircle, ArrowClockwise, Check } from "./icons";

interface UnsavedChangesModalProps {
  isOpen: boolean;
  isSaving: boolean;
  onStay: () => void;
  onDiscardAndLeave: () => void;
  onSaveAndLeave: () => void;
}

export const UnsavedChangesModal: React.FC<UnsavedChangesModalProps> = ({
  isOpen,
  isSaving,
  onStay,
  onDiscardAndLeave,
  onSaveAndLeave,
}) => {
  if (!isOpen) return null;

  return (
    <div
      data-testid="unsaved-changes-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150 select-none"
    >
      <div className="w-full max-w-md rounded-xl border border-outline bg-surface-container-high p-5 shadow-2xl flex flex-col gap-4 text-on-surface">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-500 flex items-center justify-center shrink-0">
            <WarningCircle size={22} weight="bold" />
          </div>
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-on-surface">
              Unsaved Settings Changes
            </h3>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              You have modified your settings without saving. Leaving this tab will cause your changes to be lost.
            </p>
          </div>
        </div>

        <div className="flex flex-col-reverse sm:flex-row items-center justify-end gap-2 pt-2 border-t border-outline/50">
          <button
            type="button"
            data-testid="unsaved-modal-stay-btn"
            disabled={isSaving}
            onClick={onStay}
            className="w-full sm:w-auto px-3.5 py-1.5 text-xs font-medium rounded-md border border-outline bg-surface-container hover:bg-surface-container-highest text-on-surface transition-colors cursor-pointer"
          >
            Stay on Settings
          </button>
          <button
            type="button"
            data-testid="unsaved-modal-discard-btn"
            disabled={isSaving}
            onClick={onDiscardAndLeave}
            className="w-full sm:w-auto px-3.5 py-1.5 text-xs font-medium rounded-md border border-error/40 bg-error/10 text-error hover:bg-error/20 transition-colors cursor-pointer"
          >
            Discard &amp; Leave
          </button>
          <button
            type="button"
            data-testid="unsaved-modal-save-btn"
            disabled={isSaving}
            onClick={onSaveAndLeave}
            className="w-full sm:w-auto px-3.5 py-1.5 text-xs font-semibold rounded-md bg-primary hover:bg-primary-container text-on-primary transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-xs disabled:opacity-50"
          >
            {isSaving ? (
              <ArrowClockwise size={13} className="animate-spin text-on-primary" />
            ) : (
              <Check size={13} weight="bold" />
            )}
            <span>{isSaving ? "Saving..." : "Save & Continue"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
