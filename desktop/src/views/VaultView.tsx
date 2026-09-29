import React from "react";
import { ShieldCheck, LockKey } from "../components/icons";

export const VaultView: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              LinkedIn Session Vault
            </h1>
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-xs text-emerald-400">
              AES-256-GCM Encrypted
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Secure local session credentials storage. Plaintext cookies are never logged or stored in version control.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center gap-2.5 border-b border-zinc-800/80 pb-3">
            <LockKey size={18} className="text-emerald-400" />
            <h3 className="text-xs font-semibold text-zinc-200">
              Session Encryption Key
            </h3>
          </div>
          <div className="mt-3 space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-500">Status</span>
              <span className="text-emerald-400 font-semibold">Configured & Loaded</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Cipher</span>
              <span className="text-zinc-300">AES-256-GCM + PBKDF2</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Payload Source</span>
              <span className="text-zinc-300">LINKEDIN_SESSION_STATE_ENC</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center gap-2.5 border-b border-zinc-800/80 pb-3">
            <ShieldCheck size={18} className="text-emerald-400" />
            <h3 className="text-xs font-semibold text-zinc-200">
              Playwright Cookie Health
            </h3>
          </div>
          <div className="mt-3 space-y-2 font-mono text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-500">li_at cookie</span>
              <span className="text-emerald-400">Active (18 days remaining)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">JSESSIONID</span>
              <span className="text-emerald-400">Present (CSRF token valid)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Challenge Check</span>
              <span className="text-emerald-400">No CAPTCHA / No Checkpoint</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
