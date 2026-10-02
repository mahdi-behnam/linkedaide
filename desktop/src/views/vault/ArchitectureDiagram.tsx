import React from "react";
import {
  Globe,
  LockKey,
  ShieldCheck,
  Check,
  Lightning,
} from "../../components/icons";

export const ArchitectureDiagram: React.FC = () => {
  return (
    <div className="rounded-lg bg-surface-container-lowest p-5 border border-outline-variant/30 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
              <ShieldCheck size={16} weight="bold" />
            </span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface text-[15px]">
              Architecture &amp; Security Invariants
            </h3>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant text-[13px]">
            Zero-knowledge credential flow: plaintext authentication never escapes local runtime memory.
          </p>
        </div>
        <span className="font-code-sm text-[11px] text-on-surface-variant font-medium">
          Protocol v2.4
        </span>
      </div>

      {/* Native SVG / HTML Pipeline Visualization */}
      <div className="p-4 rounded-md bg-surface-container-low border border-outline-variant/20 flex flex-col gap-3.5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5 relative">
          {/* Step 1: Local Embedded Browser */}
          <div className="p-3 rounded-md bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between gap-2.5 relative">
            <div className="flex items-center justify-between">
              <span className="w-5 h-5 rounded-[4px] bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold text-[11px]">
                1
              </span>
              <span className="text-primary flex h-5 w-5 items-center justify-center rounded-[4px] bg-primary/10">
                <Globe size={13} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Local Browser
              </span>
              <span className="font-label-sm text-[11px] text-on-surface-variant">
                Isolated session launch
              </span>
            </div>
            <div className="pt-1.5 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant text-[11px]">
              <Check size={12} weight="bold" className="text-tertiary" />
              <span>Captures cookies</span>
            </div>
          </div>

          {/* Step 2: In-Memory Fernet Encryption */}
          <div className="p-3 rounded-md bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between gap-2.5 relative">
            <div className="flex items-center justify-between">
              <span className="w-5 h-5 rounded-[4px] bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold text-[11px]">
                2
              </span>
              <span className="text-secondary flex h-5 w-5 items-center justify-center rounded-[4px] bg-secondary/10">
                <LockKey size={13} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Fernet In-Memory
              </span>
              <span className="font-label-sm text-[11px] text-on-surface-variant">
                AES-128-CBC + HMAC
              </span>
            </div>
            <div className="pt-1.5 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant text-[11px]">
              <Check size={12} weight="bold" className="text-tertiary" />
              <span>Zero disk plaintext</span>
            </div>
          </div>

          {/* Step 3: Cloudflare KV Edge */}
          <div className="p-3 rounded-md bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between gap-2.5 relative">
            <div className="flex items-center justify-between">
              <span className="w-5 h-5 rounded-[4px] bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold text-[11px]">
                3
              </span>
              <span className="text-primary flex h-5 w-5 items-center justify-center rounded-[4px] bg-primary/10">
                <Globe size={13} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Cloudflare Edge KV
              </span>
              <span className="font-label-sm text-[11px] text-on-surface-variant">
                Distributed edge state
              </span>
            </div>
            <div className="pt-1.5 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant text-[11px]">
              <Check size={12} weight="bold" className="text-tertiary" />
              <span>Protected namespace</span>
            </div>
          </div>

          {/* Step 4: Automated Worker Dispatcher */}
          <div className="p-3 rounded-md bg-surface-container-lowest border border-outline-variant/30 flex flex-col justify-between gap-2.5 relative">
            <div className="flex items-center justify-between">
              <span className="w-5 h-5 rounded-[4px] bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold text-[11px]">
                4
              </span>
              <span className="text-tertiary flex h-5 w-5 items-center justify-center rounded-[4px] bg-tertiary/10">
                <Lightning size={13} weight="bold" />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Worker Dispatch
              </span>
              <span className="font-label-sm text-[11px] text-on-surface-variant">
                HITL authorized relay
              </span>
            </div>
            <div className="pt-1.5 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant text-[11px]">
              <Check size={12} weight="bold" className="text-tertiary" />
              <span>Rate-limited queue</span>
            </div>
          </div>
        </div>

        {/* Invariants Summary Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between pt-2.5 border-t border-surface-container gap-2 text-on-surface-variant font-code-sm text-code-sm text-[12px]">
          <div>
            <span>Invariant 1: No plaintext credentials written to git, sqlite or local logs.</span>
          </div>
          <div>
            <span>Invariant 2: Fernet rotation propagates to Edge KV within 60s.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
