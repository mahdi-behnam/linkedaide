import React, { useState } from "react";
import { Download, ArrowClockwise } from "../icons";
import { useAppUpdater } from "../../hooks/useAppUpdater";
import { UpdatePopover } from "./UpdatePopover";

export const UpdatePill: React.FC = () => {
  const {
    state,
    isVisible,
    startDownload,
    cancelDownload,
    quitAndInstall,
  } = useAppUpdater();

  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  if (!isVisible) {
    return null;
  }

  const { status, progress } = state;

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        data-testid="update-pill-button"
        onClick={() => setIsPopoverOpen((prev) => !prev)}
        title="Application update available"
        className={`relative flex h-7 items-center gap-1.5 rounded-md border border-transparent bg-primary px-2.5 text-xs font-medium text-on-primary shadow-2xs transition-all duration-100 hover:bg-primary-container active:scale-[0.98] cursor-pointer overflow-hidden ${
          isPopoverOpen ? "ring-2 ring-primary/40 bg-primary-container" : ""
        }`}
      >
        {status === "available" && (
          <>
            <Download size={12} weight="bold" className="shrink-0 text-on-primary" />
            <span className="truncate">Update Available</span>
          </>
        )}

        {status === "downloading" && (
          <>
            <Download size={12} weight="bold" className="shrink-0 text-on-primary" />
            <span className="truncate font-mono tabular-nums">
              Downloading {progress ? `${progress.percent.toFixed(0)}%` : "0%"}
            </span>
            {/* Subtle bottom micro progress indicator */}
            <div className="absolute bottom-0 left-0 h-[2px] w-full bg-white/30">
              <div
                className="h-full bg-white transition-all duration-300 ease-out"
                style={{ width: `${Math.min(100, progress?.percent || 0)}%` }}
              />
            </div>
          </>
        )}

        {status === "downloaded" && (
          <>
            <ArrowClockwise size={12} weight="bold" className="shrink-0 text-on-primary" />
            <span className="truncate">Restart to Update</span>
          </>
        )}
      </button>

      {/* Floating Popover Card */}
      <UpdatePopover
        state={state}
        isOpen={isPopoverOpen}
        onClose={() => setIsPopoverOpen(false)}
        onStartDownload={startDownload}
        onCancelDownload={cancelDownload}
        onQuitAndInstall={quitAndInstall}
      />
    </div>
  );
};
