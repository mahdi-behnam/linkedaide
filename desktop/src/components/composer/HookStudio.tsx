import React from "react";
import { Sparkle, CheckCircle } from "../icons";
import { HookArchetype, HOOK_ARCHETYPES } from "./types";

interface HookStudioProps {
  appliedHookName: string | null;
  onApplyHook: (archetype: HookArchetype) => void;
}

export const HookStudio: React.FC<HookStudioProps> = ({
  appliedHookName,
  onApplyHook,
}) => {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2">
          <Sparkle size={15} className="text-primary" />
          <h2 className="text-xs font-semibold text-on-surface">
            AI Hook Studio
          </h2>
          <span className="hidden text-on-surface-variant text-[11px] sm:inline">
            · Editorial formulas for opening lines
          </span>
        </div>
        <div className="flex items-center gap-2">
          {appliedHookName && (
            <span className="font-mono text-[11px] text-primary font-medium">
              {appliedHookName}
            </span>
          )}
          <span className="text-[10px] text-on-surface-variant hidden sm:inline font-sans">
            Click to apply formula
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
        {HOOK_ARCHETYPES.map((arch, idx) => {
          const isActive = appliedHookName === arch.name;
          const indexStr = String(idx + 1).padStart(2, "0");

          return (
            <button
              key={arch.id}
              type="button"
              data-testid={`hook-btn-${arch.id}`}
              onClick={() => onApplyHook(arch)}
              className={`group p-2.5 rounded-md text-left transition-colors flex flex-col justify-between border ${
                isActive
                  ? "bg-surface-bright border-primary/60 shadow-2xs"
                  : "bg-surface-container-lowest hover:bg-surface-container border-outline/50 hover:border-outline"
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  {isActive && (
                    <CheckCircle
                      size={13}
                      weight="fill"
                      className="text-primary shrink-0"
                    />
                  )}
                  <span
                    className={`text-xs truncate transition-colors font-medium ${
                      isActive
                        ? "text-primary font-semibold"
                        : "text-on-surface group-hover:text-primary"
                    }`}
                  >
                    {arch.name}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-on-surface-variant/70 shrink-0 ml-1 tabular-nums">
                  {indexStr}
                </span>
              </div>
              <p className="text-[11px] text-on-surface-variant line-clamp-2 mt-0.5 leading-snug">
                {arch.tagline}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
