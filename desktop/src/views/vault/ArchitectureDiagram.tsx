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
    <div className="rounded-2xl bg-surface-container-lowest p-6 shadow-xs border border-surface-container-high flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck size={18} weight="bold" />
            </span>
            <h3 className="font-headline-sm text-headline-sm text-on-surface">
              Architecture &amp; Security Invariants
            </h3>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Zero-knowledge credential flow: plaintext authentication never escapes local runtime memory.
          </p>
        </div>
        <span className="font-code-sm text-code-sm text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-lg">
          Protocol v2.4
        </span>
      </div>

      {/* Native SVG / HTML Pipeline Visualization */}
      <div className="p-5 rounded-2xl bg-surface-container-low border border-surface-container-high flex flex-col gap-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 relative">
          {/* Step 1: Local Embedded Browser */}
          <div className="p-4 rounded-xl bg-surface-container-lowest shadow-2xs border border-surface-container-high flex flex-col justify-between gap-3 relative">
            <div className="flex items-center justify-between">
              <span className="w-6 h-6 rounded-md bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold">
                1
              </span>
              <span className="text-primary flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <Globe size={16} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface">
                Local Browser
              </span>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                Isolated session launch
              </span>
            </div>
            <div className="pt-2 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant">
              <Check size={13} weight="bold" className="text-tertiary" />
              <span>Captures cookies</span>
            </div>
          </div>

          {/* Step 2: In-Memory Fernet Encryption */}
          <div className="p-4 rounded-xl bg-surface-container-lowest shadow-2xs border border-surface-container-high flex flex-col justify-between gap-3 relative">
            <div className="flex items-center justify-between">
              <span className="w-6 h-6 rounded-md bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold">
                2
              </span>
              <span className="text-secondary flex h-6 w-6 items-center justify-center rounded-md bg-secondary/10">
                <LockKey size={16} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface">
                Fernet In-Memory
              </span>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                AES-128-CBC + HMAC
              </span>
            </div>
            <div className="pt-2 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant">
              <Check size={13} weight="bold" className="text-tertiary" />
              <span>Zero disk plaintext</span>
            </div>
          </div>

          {/* Step 3: Cloudflare KV Edge */}
          <div className="p-4 rounded-xl bg-surface-container-lowest shadow-2xs border border-surface-container-high flex flex-col justify-between gap-3 relative">
            <div className="flex items-center justify-between">
              <span className="w-6 h-6 rounded-md bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold">
                3
              </span>
              <span className="text-primary flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <Globe size={16} />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface">
                Cloudflare Edge KV
              </span>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                Distributed edge state
              </span>
            </div>
            <div className="pt-2 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant">
              <Check size={13} weight="bold" className="text-tertiary" />
              <span>Protected namespace</span>
            </div>
          </div>

          {/* Step 4: Automated Worker Dispatcher */}
          <div className="p-4 rounded-xl bg-surface-container-lowest shadow-2xs border border-surface-container-high flex flex-col justify-between gap-3 relative">
            <div className="flex items-center justify-between">
              <span className="w-6 h-6 rounded-md bg-surface-container-high flex items-center justify-center font-code-sm text-code-sm text-on-surface font-semibold">
                4
              </span>
              <span className="text-tertiary flex h-6 w-6 items-center justify-center rounded-md bg-tertiary/10">
                <Lightning size={16} weight="bold" />
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="font-body-strong text-body-strong text-on-surface">
                Worker Dispatch
              </span>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                HITL authorized relay
              </span>
            </div>
            <div className="pt-2 border-t border-surface-container flex items-center gap-1 font-code-sm text-code-sm text-on-surface-variant">
              <Check size={13} weight="bold" className="text-tertiary" />
              <span>Rate-limited queue</span>
            </div>
          </div>
        </div>

        {/* Invariants Summary Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between pt-3 border-t border-surface-container gap-2 text-on-surface-variant font-code-sm text-code-sm">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tertiary shrink-0" />
            <span>Invariant 1: No plaintext credentials written to git, sqlite or local logs.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tertiary shrink-0" />
            <span>Invariant 2: Fernet rotation propagates to Edge KV within 60s.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
