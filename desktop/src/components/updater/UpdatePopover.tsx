import React, { useEffect, useRef, useMemo } from "react";
import { Download, ArrowClockwise, CheckCircle, X } from "../icons";
import { formatBytes, formatSpeed, formatEta } from "./updaterUtils";
import { formatAndSanitizeReleaseNotes } from "./releaseNotesSanitizer";
import type { UpdateState } from "../../types/api";

interface UpdatePopoverProps {
  state: UpdateState;
  isOpen: boolean;
  onClose: () => void;
  onStartDownload: () => void;
  onCancelDownload: () => void;
  onQuitAndInstall: () => void;
}

export const UpdatePopover: React.FC<UpdatePopoverProps> = ({
  state,
  isOpen,
  onClose,
  onStartDownload,
  onCancelDownload,
  onQuitAndInstall,
}) => {
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  const sanitizedReleaseNotes = useMemo(() => {
    return formatAndSanitizeReleaseNotes(state.info?.releaseNotes);
  }, [state.info?.releaseNotes]);

  const handleReleaseNotesClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = (e.target as HTMLElement).closest("a");
    if (target && target.href) {
      e.preventDefault();
      e.stopPropagation();
      window.open(target.href, "_blank", "noopener,noreferrer");
    }
  };

  if (!isOpen) return null;

  const version = state.info?.version || "1.3.1";
  const progress = state.progress;

  return (
    <div
      ref={popoverRef}
      data-testid="update-popover"
      className="absolute right-0 top-full mt-2 w-84 min-h-[270px] flex flex-col justify-between rounded-xl border border-outline/70 bg-surface-container-high/95 p-4 text-xs text-on-surface shadow-2xl backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/95 z-50 select-none animate-in fade-in zoom-in-95 duration-100"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-outline/50 pb-2.5 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs tracking-tight text-on-surface">
            LinkedAide Update
          </span>
          <span className="rounded bg-blue-500/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-blue-600 dark:text-blue-400 tabular-nums">
            v{version}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close update panel"
          className="flex h-5 w-5 items-center justify-center rounded-md text-on-surface-variant hover:bg-surface-container hover:text-on-surface active:scale-95 transition-colors cursor-pointer"
        >
          <X size={12} weight="bold" />
        </button>
      </div>

      {/* State-specific Body */}
      {state.status === "available" && (
        <div className="flex flex-col flex-1 justify-between gap-3">
          <div className="space-y-2">
            <div className="text-[11px] text-on-surface-variant leading-relaxed">
              {state.info?.releaseName || "A new software update is available."}
            </div>

            {state.info?.releaseNotes && (
              <div
                data-testid="update-release-notes"
                onClick={handleReleaseNotesClick}
                className="release-notes-prose min-h-[130px] max-h-40 overflow-y-auto rounded-lg border border-outline/40 bg-surface-container-lowest/80 p-2.5 text-on-surface-variant select-text"
                dangerouslySetInnerHTML={{ __html: sanitizedReleaseNotes }}
              />
            )}
          </div>

          <div className="pt-1 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-2.5 py-1.5 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors cursor-pointer"
            >
              Later
            </button>
            <button
              type="button"
              data-testid="start-download-btn"
              onClick={onStartDownload}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-blue-500 active:scale-[0.98] transition-all cursor-pointer"
            >
              <Download size={13} weight="bold" />
              <span>Download Update</span>
            </button>
          </div>
        </div>
      )}

      {state.status === "downloading" && (
        <div className="flex flex-col flex-1 justify-between gap-3">
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-medium text-on-surface">Downloading...</span>
              <span className="font-mono tabular-nums text-blue-600 dark:text-blue-400 font-semibold">
                {progress ? `${progress.percent.toFixed(1)}%` : "0%"}
              </span>
            </div>

            {/* Clean linear progress bar */}
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-lowest dark:bg-zinc-800">
              <div
                data-testid="progress-bar-fill"
                className="h-full bg-blue-500 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${Math.min(100, progress?.percent || 0)}%` }}
              />
            </div>

            {/* Telemetry Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-outline/40 bg-surface-container-lowest/70 p-2.5 text-[11px] font-mono tabular-nums text-on-surface-variant">
              <div>
                <span className="block text-[10px] text-on-surface-variant/70 font-sans">
                  Transferred
                </span>
                <span className="text-on-surface">
                  {formatBytes(progress?.transferred || 0)} /{" "}
                  {formatBytes(progress?.total || 0)}
                </span>
              </div>
              <div>
                <span className="block text-[10px] text-on-surface-variant/70 font-sans">
                  Speed
                </span>
                <span className="text-on-surface">
                  {formatSpeed(progress?.bytesPerSecond || 0)}
                </span>
              </div>
              <div>
                <span className="block text-[10px] text-on-surface-variant/70 font-sans">
                  Remaining
                </span>
                <span className="text-on-surface">
                  {formatBytes(progress?.remainingBytes || 0)}
                </span>
              </div>
              <div>
                <span className="block text-[10px] text-on-surface-variant/70 font-sans">
                  Est. Time
                </span>
                <span className="text-on-surface">
                  {formatEta(progress?.etaSeconds || 0)}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-1 flex items-center justify-between">
            <span className="text-[10px] text-on-surface-variant/70">
              Downloading in background
            </span>
            <button
              type="button"
              data-testid="cancel-download-btn"
              onClick={onCancelDownload}
              className="rounded-lg px-2.5 py-1 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {state.status === "downloaded" && (
        <div className="flex flex-col flex-1 justify-between gap-3">
          <div className="flex items-start gap-2.5 pt-1">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-blue-600 dark:text-blue-400">
              <CheckCircle size={15} weight="bold" />
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-xs text-on-surface">
                Ready to Install
              </span>
              <span className="text-[11px] text-on-surface-variant leading-relaxed">
                LinkedAide v{version} is downloaded. Restart the application now to complete the update.
              </span>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-outline/40">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-2.5 py-1.5 text-xs text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors cursor-pointer"
            >
              Later
            </button>
            <button
              type="button"
              data-testid="restart-install-btn"
              onClick={onQuitAndInstall}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-xs hover:bg-blue-500 active:scale-[0.98] transition-all cursor-pointer"
            >
              <ArrowClockwise size={13} weight="bold" />
              <span>Restart Application</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
