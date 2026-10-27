import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { CheckCircle, WarningCircle } from "../components/icons";
import { ExecutionModeCard } from "./settings/ExecutionModeCard";
import { CloudflareRelayCard } from "./settings/CloudflareRelayCard";
import { GitHubActionsCard } from "./settings/GitHubActionsCard";
import { VaultEncryptionCard } from "./settings/VaultEncryptionCard";
import { NimIntelligenceCard } from "./settings/NimIntelligenceCard";
import { SafetyGuardrailsCard } from "./settings/SafetyGuardrailsCard";
import { ScoutTargetingCard } from "./settings/ScoutTargetingCard";
import { ScoutEngineCard, type ReactionType } from "./settings/ScoutEngineCard";
import { ScoutScheduleCard } from "./settings/ScoutScheduleCard";
import { NotificationsCard } from "./settings/NotificationsCard";
import { TimezoneCard } from "./settings/TimezoneCard";
import { UnsavedChangesBar } from "./settings/UnsavedChangesBar";
import { getDefaultTimezone } from "../utils/datetime";
import { useDeepNavigation } from "../hooks/useDeepNavigation";
import type { DesktopSettings } from "../types/api";

export function areSettingsEqual(
  a: DesktopSettings,
  b: DesktopSettings,
): boolean {
  const allKeys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<
    keyof DesktopSettings
  >;
  for (const k of allKeys) {
    const valA = a[k];
    const valB = b[k];
    if (Array.isArray(valA) || Array.isArray(valB)) {
      if (JSON.stringify(valA || []) !== JSON.stringify(valB || []))
        return false;
      continue;
    }
    const normalizedA = valA !== undefined ? valA : "";
    const normalizedB = valB !== undefined ? valB : "";
    if (normalizedA !== normalizedB) return false;
  }
  return true;
}

const defaultSettings: DesktopSettings = {
  workerUrl: "https://relay.linkedaide.workers.dev",
  apiSecret: "",
  encryptionKey: "",
  nimModel: "nvidia/nemotron-3-ultra-550b-a55b",
  nimApiKey: "",
  githubRepoOwner: "",
  githubRepoName: "linkedaide",
  githubDispatchPat: "",
  autoRefreshInterval: 600,
  executionMode: "cloud",
  headless: true,
  minimizeToTray: true,
  notificationsEnabled: true,
  maxCommentsPerDay: 15,
  maxPostsPerDay: 3,
  maxConnectionsPerDay: 10,
  maxSuggestionsPerRun: 3,
  actionTtlHours: 12,
  feedScrollScreens: 2,
  candidatePoolMultiplier: 3,
  minTriageConfidence: 0.7,
  maxCommentWords: 80,
  enablePreCommentReaction: false,
  defaultReactionType: "like",
  userFocusAreas: [],
  targetHashtags: [],
  scoutTargetUrls: [],
  timezone: getDefaultTimezone(),
};

const DEFAULT_NIM_MODELS = [
  "nvidia/nemotron-3-ultra-550b-a55b",
  "nvidia/llama-3.1-nemotron-70b-instruct",
  "mistralai/mistral-large-2-instruct",
  "deepseek-ai/deepseek-r1",
  "qwen/qwen2.5-72b-instruct",
];

export const SettingsView: React.FC = () => {
  const {
    quota,
    setTimezone: setAppTimezone,
    setAutoRefreshInterval: setAppInterval,
    setHasUnsavedSettings,
    setSaveSettingsHandler,
    setDiscardSettingsHandler,
  } = useApp();
  const [settings, setSettings] = useState<DesktopSettings>(defaultSettings);
  const [savedSettings, setSavedSettings] =
    useState<DesktopSettings>(defaultSettings);
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

  useDeepNavigation("settings");

  const hasUnsavedChanges = useMemo(
    () => !areSettingsEqual(settings, savedSettings),
    [settings, savedSettings],
  );

  const handleDiscard = useCallback(() => {
    setSettings(savedSettings);
    if (savedSettings.timezone) {
      setAppTimezone(savedSettings.timezone);
    }
    if (typeof savedSettings.autoRefreshInterval === "number") {
      setAppInterval(savedSettings.autoRefreshInterval);
    }
    setSaveSuccess(false);
    setSaveError(null);
  }, [savedSettings, setAppTimezone, setAppInterval]);

  const handleSave = useCallback(
    async (e?: React.FormEvent): Promise<boolean> => {
      if (e) e.preventDefault();
      setIsSaving(true);
      setSaveSuccess(false);
      setSaveError(null);

      if (settings.timezone) {
        setAppTimezone(settings.timezone);
      }
      if (typeof settings.autoRefreshInterval === "number") {
        setAppInterval(settings.autoRefreshInterval);
      }

      try {
        if (typeof window !== "undefined" && window.api?.saveSettings) {
          const ok = await window.api.saveSettings(settings);
          if (ok) {
            setSavedSettings(settings);
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 3000);
            return true;
          } else {
            setSaveError("Failed to save settings to local disk.");
            return false;
          }
        } else {
          setSavedSettings(settings);
          setSaveSuccess(true);
          setTimeout(() => setSaveSuccess(false), 3000);
          return true;
        }
      } catch (err) {
        setSaveError(
          err instanceof Error ? err.message : "Error saving settings",
        );
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [settings, setAppTimezone, setAppInterval],
  );

  const handleChange = <K extends keyof DesktopSettings>(
    key: K,
    value: DesktopSettings[K],
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    if (key === "timezone" && typeof value === "string") {
      setAppTimezone(value);
    }
    setSaveSuccess(false);
    setSaveError(null);
  };

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      if (typeof window !== "undefined" && window.api?.getSettings) {
        try {
          const loaded = await window.api.getSettings();
          if (isMounted && loaded) {
            setSettings((prev) => ({ ...prev, ...loaded }));
            setSavedSettings((prev) => ({ ...prev, ...loaded }));
            if (loaded.nimModel) {
              setModelsList((prev) =>
                prev.includes(loaded.nimModel!)
                  ? prev
                  : [loaded.nimModel!, ...prev],
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

  useEffect(() => {
    setHasUnsavedSettings(hasUnsavedChanges);
  }, [hasUnsavedChanges, setHasUnsavedSettings]);

  useEffect(() => {
    setSaveSettingsHandler(handleSave);
    setDiscardSettingsHandler(handleDiscard);
    return () => {
      setSaveSettingsHandler(null);
      setDiscardSettingsHandler(null);
      setHasUnsavedSettings(false);
    };
  }, [
    handleSave,
    handleDiscard,
    setSaveSettingsHandler,
    setDiscardSettingsHandler,
    setHasUnsavedSettings,
  ]);

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

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
    <div className="w-full max-w-5xl mx-auto flex flex-col gap-5 pb-8">
      {/* Top Header Block matching macOS HIG */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-1">
        <div className="flex flex-col gap-1 max-w-2xl">
          <div className="flex items-center gap-1.5 text-on-surface-variant font-label-sm text-[11px] mb-0.5">
            <span>System</span>
            <span className="text-outline-variant">/</span>
            <span className="text-on-surface font-medium">Settings</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight font-semibold">
            Agent Configuration &amp; Settings
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            Configure execution architecture, Cloudflare Workers edge
            credentials, Fernet encryption keyrings, notification triggers, and
            autonomous safety boundaries.
          </p>
        </div>

        {(saveSuccess || saveError) && (
          <div className="flex items-center gap-2 self-start md:self-auto shrink-0">
            {saveSuccess && (
              <div className="flex items-center gap-1.5 font-mono text-[11px] text-tertiary font-medium">
                <CheckCircle size={14} weight="bold" />
                <span>Settings Saved &amp; Applied</span>
              </div>
            )}
            {saveError && (
              <div className="flex items-center gap-1.5 font-mono text-[11px] text-error font-medium">
                <WarningCircle size={14} weight="bold" />
                <span>{saveError}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-4">
        {/* Section 1: Execution Mode */}
        <div id="setting-execution-mode">
          <ExecutionModeCard
            executionMode={settings.executionMode ?? "cloud"}
            onChange={(mode) => handleChange("executionMode", mode)}
          />
        </div>

        {/* Section 2: Cloudflare Relay */}
        <div id="setting-cloudflare-relay">
          <CloudflareRelayCard
            workerUrl={settings.workerUrl}
            apiSecret={settings.apiSecret}
            autoRefreshInterval={settings.autoRefreshInterval ?? 600}
            showSecret={showSecret}
            onToggleShowSecret={() => setShowSecret((prev) => !prev)}
            onWorkerUrlChange={(url) => handleChange("workerUrl", url)}
            onApiSecretChange={(secret) => handleChange("apiSecret", secret)}
            onIntervalChange={(interval) =>
              handleChange("autoRefreshInterval", interval)
            }
            isTesting={isTesting}
            testResult={testResult}
            onTestConnection={handleTestConnection}
          />
        </div>

        {/* Section 3: GitHub Actions Cloud Runner Dispatch */}
        <div id="setting-github-actions">
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
        </div>

        {/* Section 4: Vault Encryption */}
        <div id="setting-vault-encryption">
          <VaultEncryptionCard
            encryptionKey={settings.encryptionKey || ""}
            onKeyChange={(key) => handleChange("encryptionKey", key)}
            onGenerateKey={handleGenerateKey}
            onCopyKey={handleCopyKey}
            copiedKey={copiedKey}
          />
        </div>

        {/* Section 5: NVIDIA NIM Intelligence */}
        <div id="setting-nim-intelligence">
          <NimIntelligenceCard
            nimModel={settings.nimModel || "nvidia/nemotron-3-ultra-550b-a55b"}
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
        </div>

        {/* Section 6: Safety Guardrails */}
        <div id="setting-safety-guardrails">
          <SafetyGuardrailsCard
            maxCommentsPerDay={settings.maxCommentsPerDay ?? quota.commentsMax}
            maxPostsPerDay={settings.maxPostsPerDay ?? quota.postsMax}
            maxConnectionsPerDay={
              settings.maxConnectionsPerDay ?? quota.connectionsMax ?? 10
            }
            maxSuggestionsPerRun={settings.maxSuggestionsPerRun ?? 10}
            actionTtlHours={settings.actionTtlHours ?? 24}
            autoRefreshInterval={settings.autoRefreshInterval ?? 600}
            headless={settings.headless ?? true}
            onCommentsChange={(val) => handleChange("maxCommentsPerDay", val)}
            onPostsChange={(val) => handleChange("maxPostsPerDay", val)}
            onConnectionsChange={(val) =>
              handleChange("maxConnectionsPerDay", val)
            }
            onSuggestionsChange={(val) =>
              handleChange("maxSuggestionsPerRun", val)
            }
            onTtlChange={(val) => handleChange("actionTtlHours", val)}
            onIntervalChange={(val) => handleChange("autoRefreshInterval", val)}
            onHeadlessChange={(val) => handleChange("headless", val)}
          />
        </div>

        {/* Section 7: Scout Targets & Focus Topics */}
        <div id="setting-scout-targeting">
          <ScoutTargetingCard
            userFocusAreas={settings.userFocusAreas ?? []}
            targetHashtags={settings.targetHashtags ?? []}
            scoutTargetUrls={settings.scoutTargetUrls ?? []}
            onFocusAreasChange={(areas) => handleChange("userFocusAreas", areas)}
            onHashtagsChange={(hashtags) =>
              handleChange("targetHashtags", hashtags)
            }
            onTargetUrlsChange={(urls) => handleChange("scoutTargetUrls", urls)}
          />
        </div>

        {/* Section 8: Scout Engine & Scraping Parameters */}
        <div id="setting-scout-engine">
          <ScoutEngineCard
            feedScrollScreens={settings.feedScrollScreens ?? 2}
            candidatePoolMultiplier={settings.candidatePoolMultiplier ?? 3}
            minTriageConfidence={settings.minTriageConfidence ?? 0.7}
            maxCommentWords={settings.maxCommentWords ?? 80}
            enablePreCommentReaction={settings.enablePreCommentReaction ?? false}
            defaultReactionType={
              (settings.defaultReactionType as ReactionType) ?? "like"
            }
            onScrollScreensChange={(screens) =>
              handleChange("feedScrollScreens", screens)
            }
            onMultiplierChange={(multiplier) =>
              handleChange("candidatePoolMultiplier", multiplier)
            }
            onConfidenceChange={(confidence) =>
              handleChange("minTriageConfidence", confidence)
            }
            onMaxWordsChange={(words) => handleChange("maxCommentWords", words)}
            onPreReactionToggle={(enabled) =>
              handleChange("enablePreCommentReaction", enabled)
            }
            onReactionTypeChange={(type) =>
              handleChange("defaultReactionType", type)
            }
          />
        </div>

        {/* Section 9: Scout Schedule & Cadence */}
        <div id="setting-scout-schedule">
          <ScoutScheduleCard />
        </div>

        {/* Section 10: Notifications & Desktop Integration */}
        <div id="setting-notifications">
          <NotificationsCard
            minimizeToTray={settings.minimizeToTray ?? true}
            notificationsEnabled={settings.notificationsEnabled ?? true}
            onMinimizeChange={(val) => handleChange("minimizeToTray", val)}
            onNotificationsChange={(val) =>
              handleChange("notificationsEnabled", val)
            }
          />
        </div>

        {/* Section 11: Regional & Timezone Preferences */}
        <div id="setting-timezone">
          <TimezoneCard
            timezone={settings.timezone ?? getDefaultTimezone()}
            onChange={(tz) => handleChange("timezone", tz)}
          />
        </div>
      </form>

      {hasUnsavedChanges && (
        <UnsavedChangesBar
          isSaving={isSaving}
          onSave={() => void handleSave()}
          onDiscard={handleDiscard}
        />
      )}
    </div>
  );
};
