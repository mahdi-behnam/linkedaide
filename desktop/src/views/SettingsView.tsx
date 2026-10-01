import React, { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import {
  SlidersHorizontal,
  Globe,
  LockKey,
  Key,
  CheckCircle,
  WarningCircle,
  ArrowClockwise,
  Copy,
  Check,
  Cpu,
  ShieldCheck,
} from "../components/icons";
import type { DesktopSettings } from "../types/api";

const defaultSettings: DesktopSettings = {
  workerUrl: "https://relay.hitl-agent.workers.dev",
  apiSecret: "",
  encryptionKey: "",
  autoRefreshInterval: 300,
  executionMode: "cloud",
  headless: true,
  minimizeToTray: true,
  notificationsEnabled: true,
  maxCommentsPerDay: 15,
  maxPostsPerDay: 3,
  maxSuggestionsPerRun: 10,
  actionTtlHours: 24,
};

export const SettingsView: React.FC = () => {
  const { quota } = useApp();
  const [settings, setSettings] = useState<DesktopSettings>(defaultSettings);
  const [showSecret, setShowSecret] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    latencyMs?: number;
    error?: string;
  } | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const loaded = await window.api.getSettings();
          if (isMounted && loaded) {
            setSettings((prev) => ({ ...prev, ...loaded }));
          }
        } catch (err) {
          console.error("Failed to load settings:", err);
        }
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleChange = <K extends keyof DesktopSettings>(
    key: K,
    value: DesktopSettings[K]
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaveSuccess(false);
    setSaveError(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccess(false);
    setSaveError(null);

    try {
      if (typeof window !== "undefined" && window.api?.saveSettings) {
        const ok = await window.api.saveSettings(settings);
        if (ok) {
          setSaveSuccess(true);
          setTimeout(() => setSaveSuccess(false), 3000);
        } else {
          setSaveError("Failed to save settings to local disk.");
        }
      } else {
        // Fallback simulated save in browser/test
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Error saving settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerateKey = async () => {
    try {
      if (typeof window !== "undefined" && window.api?.generateFernetKey) {
        const newKey = await window.api.generateFernetKey();
        handleChange("encryptionKey", newKey);
      } else {
        const randomBytes = new Uint8Array(32);
        crypto.getRandomValues(randomBytes);
        const newKey = btoa(String.fromCharCode(...randomBytes));
        handleChange("encryptionKey", newKey);
      }
    } catch (err) {
      console.error("Failed to generate Fernet key:", err);
    }
  };

  const handleCopyKey = () => {
    if (settings.encryptionKey) {
      navigator.clipboard?.writeText(settings.encryptionKey);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    const start = performance.now();

    try {
      if (typeof window !== "undefined" && window.api?.fetchState) {
        await window.api.fetchState();
        const latencyMs = Math.round(performance.now() - start);
        setTestResult({ success: true, latencyMs });
      } else {
        setTestResult({
          success: false,
          error: "Desktop API runner is not connected",
        });
      }
    } catch (err) {
      setTestResult({
        success: false,
        error: err instanceof Error ? err.message : "Connection failed",
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* View Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Agent Configuration & Settings
          </h1>
          <p className="mt-1 text-xs text-zinc-400">
            Configure dual execution modes (Cloudflare KV vs Local Playwright), API tokens, encryption keys, and safety caps.
          </p>
        </div>

        {saveSuccess && (
          <div className="flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 font-mono text-xs text-emerald-400">
            <CheckCircle size={14} weight="bold" />
            <span>Settings Saved & Applied</span>
          </div>
        )}
        {saveError && (
          <div className="flex items-center gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-1 font-mono text-xs text-rose-400">
            <WarningCircle size={14} weight="bold" />
            <span>{saveError}</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Execution Mode Selector */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3">
            <Cpu size={16} className="text-emerald-400" />
            <h2 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              Execution Architecture Mode
            </h2>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Cloud Runner Option */}
            <label
              className={`flex cursor-pointer flex-col rounded-lg border p-4 transition-all ${
                settings.executionMode === "cloud"
                  ? "border-emerald-500/50 bg-emerald-500/5 shadow-xs"
                  : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Globe size={18} className="text-emerald-400" />
                  <span className="text-xs font-semibold text-zinc-100">
                    Cloud Remote Runner
                  </span>
                </div>
                <input
                  type="radio"
                  name="executionMode"
                  value="cloud"
                  checked={settings.executionMode === "cloud"}
                  onChange={() => handleChange("executionMode", "cloud")}
                  className="accent-emerald-500"
                />
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-zinc-400">
                Orchestrates state via Cloudflare Workers KV and triggers GitHub Actions dispatch runners. Zero local machine uptime required.
              </p>
            </label>

            {/* Local Runner Option */}
            <label
              className={`flex cursor-pointer flex-col rounded-lg border p-4 transition-all ${
                settings.executionMode === "local"
                  ? "border-cyan-500/50 bg-cyan-500/5 shadow-xs"
                  : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={18} className="text-cyan-400" />
                  <span className="text-xs font-semibold text-zinc-100">
                    Local Playwright Runner
                  </span>
                </div>
                <input
                  type="radio"
                  name="executionMode"
                  value="local"
                  checked={settings.executionMode === "local"}
                  onChange={() => handleChange("executionMode", "local")}
                  className="accent-cyan-500"
                />
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-zinc-400">
                Executes browser actions directly on this machine using local Playwright and Python agent CLI. Ideal for desktop-first control.
              </p>
            </label>
          </div>
        </div>

        {/* Cloudflare Worker & API Credentials */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Globe size={16} className="text-emerald-400" />
              <h2 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                Cloudflare Worker Edge Relay
              </h2>
            </div>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={isTesting}
              className="flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-zinc-600 hover:text-zinc-100 active:translate-y-[1px] disabled:opacity-50"
            >
              <ArrowClockwise size={13} className={isTesting ? "animate-spin" : ""} />
              <span>{isTesting ? "Testing..." : "Test Connection"}</span>
            </button>
          </div>

          {testResult && (
            <div
              className={`mt-3 flex items-center justify-between rounded-md border px-3 py-2 text-xs font-mono ${
                testResult.success
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-rose-500/30 bg-rose-500/10 text-rose-400"
              }`}
            >
              <span>
                {testResult.success
                  ? "Connected successfully to Cloudflare Worker API."
                  : `Connection error: ${testResult.error}`}
              </span>
              {testResult.latencyMs !== undefined && (
                <span className="font-semibold">{testResult.latencyMs} ms</span>
              )}
            </div>
          )}

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-zinc-300">
                Worker API Endpoint URL
              </label>
              <input
                type="text"
                value={settings.workerUrl}
                onChange={(e) => handleChange("workerUrl", e.target.value)}
                placeholder="https://relay.your-subdomain.workers.dev"
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 placeholder-zinc-600 focus:border-emerald-500 focus:outline-hidden"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-zinc-300">
                  Desktop API Secret (Bearer Token)
                </label>
                <button
                  type="button"
                  onClick={() => setShowSecret((prev) => !prev)}
                  className="text-[11px] text-zinc-500 hover:text-zinc-300"
                >
                  {showSecret ? "Hide" : "Show"}
                </button>
              </div>
              <input
                type={showSecret ? "text" : "password"}
                value={settings.apiSecret}
                onChange={(e) => handleChange("apiSecret", e.target.value)}
                placeholder="Enter DESKTOP_API_SECRET"
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 placeholder-zinc-600 focus:border-emerald-500 focus:outline-hidden"
              />
            </div>
          </div>
        </div>

        {/* Session Encryption & Fernet Key */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2">
              <LockKey size={16} className="text-violet-400" />
              <h2 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                Session Vault Encryption (Fernet AES-128-CBC)
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopyKey}
                disabled={!settings.encryptionKey}
                className="flex items-center gap-1 rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 active:translate-y-[1px] disabled:opacity-40"
              >
                {copiedKey ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                <span>{copiedKey ? "Copied" : "Copy"}</span>
              </button>
              <button
                type="button"
                onClick={handleGenerateKey}
                className="flex items-center gap-1 rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-300 hover:bg-violet-500/20 active:translate-y-[1px]"
              >
                <Key size={12} />
                <span>Generate Key</span>
              </button>
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-xs font-medium text-zinc-300">
              32-Byte URL-Safe Base64 Fernet Key
            </label>
            <input
              type="text"
              value={settings.encryptionKey || ""}
              onChange={(e) => handleChange("encryptionKey", e.target.value)}
              placeholder="Base64 URL-safe 32-byte key matching SESSION_ENCRYPTION_KEY"
              className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 placeholder-zinc-600 focus:border-violet-500 focus:outline-hidden"
            />
            <p className="mt-1.5 text-[11px] text-zinc-500">
              Must match the SESSION_ENCRYPTION_KEY repository secret used by Python agents to decrypt LinkedIn session state.
            </p>
          </div>
        </div>

        {/* Background Polling & App Preferences */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5">
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-3">
            <SlidersHorizontal size={16} className="text-amber-400" />
            <h2 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              Background Monitoring & Safety Limits
            </h2>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-zinc-300">
                Poll Interval
              </label>
              <select
                value={settings.autoRefreshInterval ?? 300}
                onChange={(e) =>
                  handleChange("autoRefreshInterval", Number(e.target.value))
                }
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 focus:border-amber-500 focus:outline-hidden"
              >
                <option value={60}>1 Minute (Fast)</option>
                <option value={120}>2 Minutes</option>
                <option value={300}>5 Minutes (Default)</option>
                <option value={600}>10 Minutes</option>
                <option value={900}>15 Minutes</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300">
                Max Comments / Day
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={settings.maxCommentsPerDay ?? quota.commentsMax}
                onChange={(e) =>
                  handleChange("maxCommentsPerDay", Number(e.target.value))
                }
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 focus:border-amber-500 focus:outline-hidden"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300">
                Max Posts / Day
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={settings.maxPostsPerDay ?? quota.postsMax}
                onChange={(e) =>
                  handleChange("maxPostsPerDay", Number(e.target.value))
                }
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 focus:border-amber-500 focus:outline-hidden"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300">
                Approval TTL (Hours)
              </label>
              <input
                type="number"
                min={1}
                max={72}
                value={settings.actionTtlHours ?? 24}
                onChange={(e) =>
                  handleChange("actionTtlHours", Number(e.target.value))
                }
                className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-200 focus:border-amber-500 focus:outline-hidden"
              />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-6 pt-3 border-t border-zinc-800/60">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={settings.minimizeToTray ?? true}
                onChange={(e) => handleChange("minimizeToTray", e.target.checked)}
                className="accent-emerald-500 rounded"
              />
              <span>Minimize to System Tray on Window Close</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={settings.notificationsEnabled ?? true}
                onChange={(e) =>
                  handleChange("notificationsEnabled", e.target.checked)
                }
                className="accent-emerald-500 rounded"
              />
              <span>Native OS Notifications on New Approvals</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs text-zinc-300">
              <input
                type="checkbox"
                checked={settings.headless ?? true}
                onChange={(e) => handleChange("headless", e.target.checked)}
                className="accent-emerald-500 rounded"
              />
              <span>Headless Playwright Browser (Local Mode)</span>
            </label>
          </div>
        </div>

        {/* Submit Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-2 rounded-md bg-emerald-500 px-5 py-2 text-xs font-semibold text-zinc-950 shadow-sm transition-all hover:bg-emerald-400 active:translate-y-[1px] active:scale-[0.98] disabled:opacity-50"
          >
            {isSaving && <ArrowClockwise size={14} className="animate-spin" />}
            <span>{isSaving ? "Saving Configuration..." : "Save & Apply Settings"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
