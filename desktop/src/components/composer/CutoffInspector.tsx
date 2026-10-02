import React, { useState } from "react";
import { Eye, DeviceMobile, Desktop } from "../icons";

interface CutoffInspectorProps {
  postText: string;
}

export const CutoffInspector: React.FC<CutoffInspectorProps> = ({ postText }) => {
  const [previewDevice, setPreviewDevice] = useState<"mobile" | "desktop">("mobile");

  const foldCutoff = 140;
  const charCount = postText.length;
  const isOverFold = charCount > foldCutoff;
  const charsRemainingInFold = Math.max(0, foldCutoff - charCount);
  const charsBelowFold = Math.max(0, charCount - foldCutoff);

  const aboveFoldText = postText.slice(0, foldCutoff);
  const belowFoldText = postText.slice(foldCutoff);

  return (
    <div
      data-testid="cutoff-indicator"
      className="p-4 rounded-lg bg-surface-container-lowest border border-outline/70 shadow-2xs flex flex-col gap-3"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-surface-container text-tertiary">
            <Eye size={14} weight="bold" />
          </div>
          <div>
            <span className="text-xs font-semibold text-on-surface block">
              Above-the-Fold 140-Character Mobile Cutoff
            </span>
            <span className="text-[11px] text-on-surface-variant block">
              Live viewport simulation with fold truncation
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Desktop vs Mobile feed preview toggle */}
          <div className="flex items-center p-0.5 rounded-md bg-surface-container text-xs border border-outline/40">
            <button
              type="button"
              onClick={() => setPreviewDevice("mobile")}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
                previewDevice === "mobile"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
              title="Mobile Feed Preview (140 chars fold)"
            >
              <DeviceMobile size={12} />
              <span>Mobile</span>
            </button>
            <button
              type="button"
              onClick={() => setPreviewDevice("desktop")}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11px] font-medium transition-colors ${
                previewDevice === "desktop"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
              title="Desktop Feed Preview"
            >
              <Desktop size={12} />
              <span>Desktop</span>
            </button>
          </div>

          {/* Fold Status Badge */}
          <span
            data-testid="fold-status-badge"
            className={`font-mono text-[10px] px-2 py-0.5 rounded-[4px] font-medium transition-colors tabular-nums ${
              isOverFold
                ? "bg-error-container/30 text-error border border-error/30"
                : "bg-surface-container text-on-surface-variant border border-outline/50"
            }`}
          >
            {isOverFold
              ? `${charsBelowFold} chars below fold (...see more)`
              : `${charsRemainingInFold} chars remaining in fold`}
          </span>
        </div>
      </div>

      {/* Fold Progress Bar */}
      <div className="h-1 w-full overflow-hidden rounded-xs bg-surface-container">
        <div
          className={`h-full transition-all duration-200 rounded-xs ${
            isOverFold ? "bg-error" : "bg-tertiary"
          }`}
          style={{
            width: `${Math.min(100, (charCount / foldCutoff) * 100)}%`,
          }}
        />
      </div>

      {/* Viewport Simulation Box */}
      <div className="p-3 rounded-md bg-surface-container-low flex flex-col gap-1.5 border border-outline/50">
        <div className="flex items-center justify-between text-on-surface-variant">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-outline">
            {previewDevice === "mobile"
              ? "Mobile Feed First Viewport Simulation"
              : "Desktop Feed First Viewport Simulation"}
          </span>
          <span className="font-mono text-[10px] text-on-surface-variant">
            {previewDevice === "mobile" ? "Fold Limit ~140 chars" : "Full Viewport (~240 chars)"}
          </span>
        </div>

        <div className="text-xs text-on-surface leading-relaxed relative">
          <span className="text-on-surface font-medium">
            {aboveFoldText || (
              <span className="text-on-surface-variant/60 italic">
                Type in the editor to test your above-the-fold opening...
              </span>
            )}
          </span>

          {/* Visual Fold Cutoff Line */}
          {isOverFold && (
            <div
              data-testid="visual-fold-line"
              className="my-2 flex items-center gap-2 font-mono text-[10px] text-error font-medium"
            >
              <div className="h-px flex-1 border-t border-dashed border-error/40" />
              <span className="rounded-[4px] bg-error-container/30 px-1.5 py-0.2 border border-error/20">
                140 Chars Fold Cutoff (...see more)
              </span>
              <div className="h-px flex-1 border-t border-dashed border-error/40" />
            </div>
          )}

          {/* Below Fold Preview */}
          {isOverFold && (
            <p className="text-on-surface-variant text-[11px] line-clamp-2 mt-1">
              {belowFoldText}
            </p>
          )}
        </div>
      </div>

      <p className="text-[11px] text-on-surface-variant">
        LinkedIn mobile cuts off post copy around 140 characters before displaying &quot;...see more&quot;. Your opening hook must generate instant curiosity before this threshold.
      </p>
    </div>
  );
};
