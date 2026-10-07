import React, { useState, useEffect, useRef } from "react";
import { ToastNotification } from "./types";
import { X, CheckCircle, WarningCircle, Info } from "@phosphor-icons/react";

interface ToastItemProps {
  toast: ToastNotification;
  onDismiss: (id: string) => void;
}

export const ToastItem: React.FC<ToastItemProps> = ({ toast, onDismiss }) => {
  const totalDuration = toast.durationMs ?? 5000;
  const [remainingMs, setRemainingMs] = useState<number>(totalDuration);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const lastTickRef = useRef<number>(Date.now());

  useEffect(() => {
    lastTickRef.current = Date.now();
  }, []);

  useEffect(() => {
    if (isHovered || remainingMs <= 0) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = now - lastTickRef.current;
      lastTickRef.current = now;

      setRemainingMs((prev) => {
        const next = prev - elapsed;
        if (next <= 0) {
          clearInterval(interval);
          onDismiss(toast.id);
          return 0;
        }
        return next;
      });
    }, 50);

    return () => clearInterval(interval);
  }, [isHovered, remainingMs, toast.id, onDismiss]);

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    lastTickRef.current = Date.now();
    setIsHovered(false);
  };

  const progressPercent = Math.max(0, Math.min(100, (remainingMs / totalDuration) * 100));

  const type = toast.type || "info";

  return (
    <div
      data-testid="realtime-toast"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="pointer-events-auto relative overflow-hidden rounded-lg border border-outline bg-surface-bright/95 shadow-lg backdrop-blur-md transition-all duration-200 ease-out text-on-surface"
    >
      {/* Top Countdown Progress Bar */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-surface-container-high overflow-hidden">
        <div
          data-testid="toast-progress-bar"
          style={{ width: `${progressPercent}%` }}
          className={`h-full transition-all duration-75 ${
            type === "success"
              ? "bg-tertiary"
              : type === "error"
              ? "bg-error"
              : type === "warn"
              ? "bg-amber-500"
              : "bg-primary"
          }`}
        />
      </div>

      <div className="flex items-center gap-2.5 px-3.5 py-3 pt-3.5 text-xs font-medium">
        {type === "success" ? (
          <CheckCircle size={15} weight="bold" className="text-tertiary shrink-0" />
        ) : type === "error" ? (
          <WarningCircle size={15} weight="bold" className="text-error shrink-0" />
        ) : type === "warn" ? (
          <WarningCircle size={15} weight="bold" className="text-amber-500 shrink-0" />
        ) : (
          <Info size={15} weight="bold" className="text-primary shrink-0" />
        )}

        <span className="flex-1 leading-snug">{toast.message}</span>

        <button
          type="button"
          data-testid="toast-close-btn"
          aria-label="Close notification"
          onClick={() => onDismiss(toast.id)}
          className="rounded p-0.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors shrink-0"
        >
          <X size={13} weight="bold" />
        </button>
      </div>
    </div>
  );
};
