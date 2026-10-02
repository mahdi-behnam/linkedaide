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
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Sparkle size={16} weight="fill" className="text-primary" />
          <h2 className="font-body-strong text-body-strong text-on-surface font-semibold">
            AI Hook Studio
          </h2>
          <span className="hidden text-on-surface-variant font-label-sm text-label-sm sm:inline">
            · AI Hook Archetypes · 1-click high-retention openers
          </span>
        </div>
        <div className="flex items-center gap-2">
          {appliedHookName && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary border border-primary/20">
              Active: {appliedHookName}
            </span>
          )}
          <span className="font-code-sm text-code-sm text-on-surface-variant hidden sm:inline">
            Click to apply formula
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
        {HOOK_ARCHETYPES.map((arch, idx) => {
          const isActive = appliedHookName === arch.name;
          const indexStr = String(idx + 1).padStart(2, "0");

          return (
            <button
              key={arch.id}
              type="button"
              data-testid={`hook-btn-${arch.id}`}
              onClick={() => onApplyHook(arch)}
              className={`group p-3 rounded-xl text-left shadow-xs transition-all duration-150 flex flex-col justify-between border ${
                isActive
                  ? "bg-surface-container-lowest border-primary ring-1 ring-primary shadow-xs"
                  : "bg-surface-container-lowest hover:bg-surface-container-low border-surface-container-high/70 hover:border-surface-container-highest"
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  {isActive && (
                    <CheckCircle
                      size={14}
                      weight="fill"
                      className="text-primary shrink-0"
                    />
                  )}
                  <span
                    className={`font-body-strong text-body-strong truncate transition-colors ${
                      isActive
                        ? "text-primary font-semibold"
                        : "text-on-surface group-hover:text-primary"
                    }`}
                  >
                    {arch.name}
                  </span>
                </div>
                <span className="font-code-sm text-code-sm text-on-surface-variant/70 shrink-0 ml-1">
                  {indexStr}
                </span>
              </div>
              <p className="font-label-sm text-label-sm text-on-surface-variant line-clamp-2 mt-1">
                {arch.tagline}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
