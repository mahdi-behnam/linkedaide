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
      className="p-5 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-3.5"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-surface-container text-tertiary">
            <Eye size={16} weight="bold" />
          </div>
          <div>
            <span className="font-body-strong text-body-strong text-on-surface font-semibold block">
              Above-the-Fold 140-Character Mobile Cutoff
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant block">
              Live viewport simulation with fold truncation
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Desktop vs Mobile feed preview toggle */}
          <div className="flex items-center p-0.5 rounded-lg bg-surface-container text-xs">
            <button
              type="button"
              onClick={() => setPreviewDevice("mobile")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-label-md font-medium transition-colors ${
                previewDevice === "mobile"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
              title="Mobile Feed Preview (140 chars fold)"
            >
              <DeviceMobile size={13} />
              <span>Mobile</span>
            </button>
            <button
              type="button"
              onClick={() => setPreviewDevice("desktop")}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-label-md font-medium transition-colors ${
                previewDevice === "desktop"
                  ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
              title="Desktop Feed Preview"
            >
              <Desktop size={13} />
              <span>Desktop</span>
            </button>
          </div>

          {/* Fold Status Badge */}
          <span
            data-testid="fold-status-badge"
            className={`font-code-sm text-code-sm px-2.5 py-1 rounded-full font-medium transition-colors ${
              isOverFold
                ? "bg-error-container text-on-error-container border border-error/20"
                : "bg-surface-container text-on-surface-variant border border-surface-container-high"
            }`}
          >
            {isOverFold
              ? `${charsBelowFold} chars below fold (...see more)`
              : `${charsRemainingInFold} chars remaining in fold`}
          </span>
        </div>
      </div>

      {/* Fold Progress Bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container">
        <div
          className={`h-full transition-all duration-200 rounded-full ${
            isOverFold ? "bg-error" : "bg-tertiary"
          }`}
          style={{
            width: `${Math.min(100, (charCount / foldCutoff) * 100)}%`,
          }}
        />
      </div>

      {/* Viewport Simulation Box */}
      <div className="p-3.5 rounded-xl bg-surface-container-low flex flex-col gap-2 border border-surface-container-high/60">
        <div className="flex items-center justify-between text-on-surface-variant">
          <span className="font-label-sm text-label-sm uppercase tracking-wider font-semibold text-outline">
            {previewDevice === "mobile"
              ? "Mobile Feed First Viewport Simulation"
              : "Desktop Feed First Viewport Simulation"}
          </span>
          <span className="font-code-sm text-code-sm">
            {previewDevice === "mobile" ? "Fold Limit ~140 chars" : "Full Viewport (~240 chars)"}
          </span>
        </div>

        <div className="font-body-md text-body-md text-on-surface leading-relaxed relative">
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
              className="my-2.5 flex items-center gap-2 font-code-sm text-[10px] text-error font-medium"
            >
              <div className="h-px flex-1 border-t border-dashed border-error/50" />
              <span className="rounded-full bg-error-container px-2.5 py-0.5 border border-error/20">
                140 Chars Fold Cutoff (...see more)
              </span>
              <div className="h-px flex-1 border-t border-dashed border-error/50" />
            </div>
          )}

          {/* Below Fold Preview */}
          {isOverFold && (
            <p className="text-on-surface-variant text-[12px] line-clamp-2 mt-1">
              {belowFoldText}
            </p>
          )}
        </div>
      </div>

      <p className="font-label-sm text-label-sm text-on-surface-variant">
        LinkedIn mobile cuts off post copy around 140 characters before displaying &quot;...see more&quot;. Your opening hook must generate instant curiosity before this threshold.
      </p>
    </div>
  );
};
