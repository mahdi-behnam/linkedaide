import React, { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { Check, CheckCircle, WarningCircle, ArrowClockwise } from "../components/icons";
import { ExecutionModeCard } from "./settings/ExecutionModeCard";
import { CloudflareRelayCard } from "./settings/CloudflareRelayCard";
import { GitHubActionsCard } from "./settings/GitHubActionsCard";
import { VaultEncryptionCard } from "./settings/VaultEncryptionCard";
import { NimIntelligenceCard } from "./settings/NimIntelligenceCard";
import { SafetyGuardrailsCard } from "./settings/SafetyGuardrailsCard";
import { NotificationsCard } from "./settings/NotificationsCard";
import type { DesktopSettings } from "../types/api";

const defaultSettings: DesktopSettings = {
  workerUrl: "https://relay.hitl-agent.workers.dev",
  apiSecret: "",
  encryptionKey: "",
  nimModel: "meta/llama-3.1-70b-instruct",
  nimApiKey: "",
  githubRepoOwner: "mahdi-behnam",
  githubRepoName: "linkedin-hitl-agent",
  githubDispatchPat: "",
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

const DEFAULT_NIM_MODELS = [
  "meta/llama-3.1-70b-instruct",
  "meta/llama-3.3-70b-instruct",
  "nvidia/llama-3.1-nemotron-70b-instruct",
  "mistralai/mistral-large-2-instruct",
  "deepseek-ai/deepseek-r1",
  "qwen/qwen2.5-72b-instruct",
];

export const SettingsView: React.FC = () => {
  const { quota } = useApp();
  const [settings, setSettings] = useState<DesktopSettings>(defaultSettings);
  const [showSecret, setShowSecret] = useState(false);
  const [showNimKey, setShowNimKey] = useState(false);
  const [showGithubPat, setShowGithubPat] = useState(false);
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
  const [modelsList, setModelsList] = useState<string[]>(DEFAULT_NIM_MODELS);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [modelFetchFeedback, setModelFetchFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [isCustomModel, setIsCustomModel] = useState(false);

  const handleDiscard = async () => {
    if (typeof window !== "undefined" && window.api?.getSettings) {
      try {
        const loaded = await window.api.getSettings();
        if (loaded) {
          setSettings((prev) => ({ ...prev, ...loaded }));
        }
      } catch (err) {
        console.error("Failed to discard settings:", err);
      }
    }
  };

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const loaded = await window.api.getSettings();
          if (isMounted && loaded) {
            setSettings((prev) => ({ ...prev, ...loaded }));
            if (loaded.nimModel) {
              setModelsList((prev) =>
                prev.includes(loaded.nimModel!) ? prev : [loaded.nimModel!, ...prev]
              );
            }
          }
        } catch (err) {
          console.error("Failed to load settings:", err);
        }
      }
    };
    void init();
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

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
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
    const rawUrl = settings.workerUrl?.trim() || "";
    const rawSecret = settings.apiSecret?.trim() || "";

    setIsTesting(true);
    setTestResult(null);
    const start = performance.now();

    try {
      if (typeof window !== "undefined" && window.api?.testConnection) {
        const result = await window.api.testConnection({
          workerUrl: rawUrl,
          apiSecret: rawSecret,
        });
        setTestResult(result);
      } else if (typeof window !== "undefined" && window.api?.fetchState) {
        await window.api.fetchState({
          workerUrl: rawUrl,
          apiSecret: rawSecret,
        });
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

  const handleFetchModels = async () => {
    setIsFetchingModels(true);
    setModelFetchFeedback(null);
    try {
      if (typeof window !== "undefined" && window.api?.fetchNimModels) {
        const res = await window.api.fetchNimModels(settings.nimApiKey);
        if (res.success && res.models && res.models.length > 0) {
          const fetched = res.models;
          if (settings.nimModel && !fetched.includes(settings.nimModel)) {
            setModelsList([settings.nimModel, ...fetched]);
          } else {
            setModelsList(fetched);
          }
          setIsCustomModel(false);
          setModelFetchFeedback({
            type: "success",
            message: `Loaded ${fetched.length} models from NVIDIA`,
          });
        } else {
          setModelFetchFeedback({
            type: "error",
            message: res.error || "Failed to fetch models from NVIDIA",
          });
        }
      } else {
        setModelFetchFeedback({
          type: "error",
          message: "Model fetching API not available in this environment",
        });
      }
    } catch (err) {
      setModelFetchFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to fetch models",
      });
    } finally {
      setIsFetchingModels(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-8 pb-10">
      {/* Top Header Block matching Stitch */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-2">
        <div className="flex flex-col gap-1.5 max-w-2xl">
          <div className="flex items-center gap-2 text-on-surface-variant font-label-md text-label-md mb-1">
            <span>System</span>
            <span className="text-outline-variant">/</span>
            <span className="text-on-surface font-semibold">Settings</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight font-semibold">
            Agent Configuration &amp; Settings
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            Configure execution architecture, Cloudflare Workers edge credentials, Fernet encryption keyrings, notification triggers, and autonomous safety boundaries.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start md:self-auto shrink-0">
          {saveSuccess && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-tertiary/30 bg-tertiary-container/15 font-mono text-xs text-tertiary font-semibold">
              <CheckCircle size={15} weight="bold" />
              <span>Settings Saved &amp; Applied</span>
            </div>
          )}
          {saveError && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-error/30 bg-error-container/20 font-mono text-xs text-error font-semibold">
              <WarningCircle size={15} weight="bold" />
              <span>{saveError}</span>
            </div>
          )}
          <button
            type="button"
            onClick={() => void handleDiscard()}
            className="px-3.5 py-1.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors font-body-strong text-body-strong flex items-center gap-1.5 cursor-pointer"
          >
            <span>Discard</span>
          </button>
          <button
            type="button"
            onClick={() => handleSave()}
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-primary hover:bg-primary-container text-on-primary transition-all font-body-strong text-body-strong shadow-xs flex items-center gap-2 shrink-0 whitespace-nowrap cursor-pointer active:scale-95 disabled:opacity-50"
          >
            {isSaving ? (
              <ArrowClockwise size={16} className="animate-spin text-on-primary" />
            ) : (
              <Check size={16} weight="bold" />
            )}
            <span>Save Changes</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-6">
        {/* Section 1: Execution Mode */}
        <ExecutionModeCard
          executionMode={settings.executionMode ?? "cloud"}
          onChange={(mode) => handleChange("executionMode", mode)}
        />

        {/* Section 2: Cloudflare Relay */}
        <CloudflareRelayCard
          workerUrl={settings.workerUrl}
          apiSecret={settings.apiSecret}
          autoRefreshInterval={settings.autoRefreshInterval ?? 300}
          showSecret={showSecret}
          onToggleShowSecret={() => setShowSecret((prev) => !prev)}
          onWorkerUrlChange={(url) => handleChange("workerUrl", url)}
          onApiSecretChange={(secret) => handleChange("apiSecret", secret)}
          onIntervalChange={(interval) => handleChange("autoRefreshInterval", interval)}
          isTesting={isTesting}
          testResult={testResult}
          onTestConnection={handleTestConnection}
        />

        {/* Section 3: GitHub Actions Cloud Runner Dispatch */}
        <GitHubActionsCard
          executionMode={settings.executionMode ?? "cloud"}
          githubRepoOwner={settings.githubRepoOwner || ""}
          githubRepoName={settings.githubRepoName || ""}
          githubDispatchPat={settings.githubDispatchPat || ""}
          showGithubPat={showGithubPat}
          onToggleShowPat={() => setShowGithubPat((prev) => !prev)}
          onRepoOwnerChange={(owner) => handleChange("githubRepoOwner", owner)}
          onRepoNameChange={(name) => handleChange("githubRepoName", name)}
          onDispatchPatChange={(pat) => handleChange("githubDispatchPat", pat)}
        />

        {/* Section 4: Vault Encryption */}
        <VaultEncryptionCard
          encryptionKey={settings.encryptionKey || ""}
          onKeyChange={(key) => handleChange("encryptionKey", key)}
          onGenerateKey={handleGenerateKey}
          onCopyKey={handleCopyKey}
          copiedKey={copiedKey}
        />

        {/* Section 5: NVIDIA NIM Intelligence */}
        <NimIntelligenceCard
          nimModel={settings.nimModel || "meta/llama-3.1-70b-instruct"}
          nimApiKey={settings.nimApiKey || ""}
          modelsList={modelsList}
          isCustomModel={isCustomModel}
          isFetchingModels={isFetchingModels}
          modelFetchFeedback={modelFetchFeedback}
          showNimKey={showNimKey}
          onToggleShowNimKey={() => setShowNimKey((prev) => !prev)}
          onModelChange={(model) => handleChange("nimModel", model)}
          onCustomModelToggle={(custom) => setIsCustomModel(custom)}
          onApiKeyChange={(key) => handleChange("nimApiKey", key)}
          onFetchModels={handleFetchModels}
        />

        {/* Section 6: Safety Guardrails */}
        <SafetyGuardrailsCard
          maxCommentsPerDay={settings.maxCommentsPerDay ?? quota.commentsMax}
          maxPostsPerDay={settings.maxPostsPerDay ?? quota.postsMax}
          maxSuggestionsPerRun={settings.maxSuggestionsPerRun ?? 10}
          actionTtlHours={settings.actionTtlHours ?? 24}
          autoRefreshInterval={settings.autoRefreshInterval ?? 300}
          headless={settings.headless ?? true}
          onCommentsChange={(val) => handleChange("maxCommentsPerDay", val)}
          onPostsChange={(val) => handleChange("maxPostsPerDay", val)}
          onSuggestionsChange={(val) => handleChange("maxSuggestionsPerRun", val)}
          onTtlChange={(val) => handleChange("actionTtlHours", val)}
          onIntervalChange={(val) => handleChange("autoRefreshInterval", val)}
          onHeadlessChange={(val) => handleChange("headless", val)}
        />

        {/* Section 7: Notifications & Desktop Integration */}
        <NotificationsCard
          minimizeToTray={settings.minimizeToTray ?? true}
          notificationsEnabled={settings.notificationsEnabled ?? true}
          onMinimizeChange={(val) => handleChange("minimizeToTray", val)}
          onNotificationsChange={(val) => handleChange("notificationsEnabled", val)}
        />

        {/* Bottom Save Button Bar */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-container-high">
          <button
            type="submit"
            data-testid="save-settings-btn"
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-body-strong text-body-strong shadow-xs transition-all cursor-pointer active:scale-95 disabled:opacity-50"
          >
            {isSaving && <ArrowClockwise size={15} className="animate-spin" />}
            <span>{isSaving ? "Saving Configuration..." : "Save & Apply Settings"}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
