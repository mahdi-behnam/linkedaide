import React, { useState } from "react";
import {
  Cpu,
  ArrowClockwise,
  CheckCircle,
  WarningCircle,
  Eye,
  SlidersHorizontal,
  Key,
} from "../../components/icons";

interface NimIntelligenceCardProps {
  nimModel: string;
  nimApiKey: string;
  nimModelFallback?: string;
  llmProvider?: string;
  openaiApiKey?: string;
  anthropicApiKey?: string;
  geminiApiKey?: string;
  groqApiKey?: string;
  ollamaBaseUrl?: string;
  nimModelTriage?: string;
  nimModelVision?: string;
  nimTemperature?: number;
  nimTimeoutSeconds?: number;
  nimMaxTokens?: number;
  nimBaseUrl?: string;
  modelsList: string[];
  isCustomModel: boolean;
  isFetchingModels: boolean;
  modelFetchFeedback: {
    type: "success" | "error";
    message: string;
  } | null;
  showNimKey: boolean;
  onToggleShowNimKey: () => void;
  onModelChange: (model: string) => void;
  onModelFallbackChange?: (fallbackModel: string) => void;
  onProviderChange?: (provider: string) => void;
  onCustomModelToggle: (isCustom: boolean) => void;
  onApiKeyChange: (key: string) => void;
  onOpenaiApiKeyChange?: (key: string) => void;
  onAnthropicApiKeyChange?: (key: string) => void;
  onGeminiApiKeyChange?: (key: string) => void;
  onGroqApiKeyChange?: (key: string) => void;
  onOllamaBaseUrlChange?: (url: string) => void;
  onModelTriageChange?: (model: string) => void;
  onModelVisionChange?: (model: string) => void;
  onTemperatureChange?: (temp: number) => void;
  onTimeoutChange?: (timeout: number) => void;
  onMaxTokensChange?: (maxTokens: number) => void;
  onBaseUrlChange?: (url: string) => void;
  onFetchModels: () => void;
}

const PROVIDER_NAMES: Record<string, string> = {
  nvidia: "NVIDIA NIM",
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  groq: "Groq",
  ollama: "Ollama",
  "openai-compatible": "Custom Provider",
};

export const NimIntelligenceCard: React.FC<NimIntelligenceCardProps> = ({
  nimModel,
  nimApiKey,
  nimModelFallback = "",
  llmProvider = "nvidia",
  openaiApiKey = "",
  anthropicApiKey = "",
  geminiApiKey = "",
  groqApiKey = "",
  ollamaBaseUrl = "http://localhost:11434",
  nimModelTriage = "",
  nimModelVision = "",
  nimTemperature = 0.2,
  nimTimeoutSeconds = 60,
  nimMaxTokens = 1024,
  nimBaseUrl = "",
  modelsList,
  isCustomModel,
  isFetchingModels,
  modelFetchFeedback,
  showNimKey,
  onToggleShowNimKey,
  onModelChange,
  onModelFallbackChange,
  onProviderChange,
  onCustomModelToggle,
  onApiKeyChange,
  onOpenaiApiKeyChange,
  onAnthropicApiKeyChange,
  onGeminiApiKeyChange,
  onGroqApiKeyChange,
  onOllamaBaseUrlChange,
  onModelTriageChange,
  onModelVisionChange,
  onTemperatureChange,
  onTimeoutChange,
  onMaxTokensChange,
  onBaseUrlChange,
  onFetchModels,
}) => {
  const [showSecondaryKeys, setShowSecondaryKeys] = useState(false);
  const [showHyperparameters, setShowHyperparameters] = useState(false);
  const [showOpenaiKey, setShowOpenaiKey] = useState(false);
  const [showAnthropicKey, setShowAnthropicKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [showGroqKey, setShowGroqKey] = useState(false);

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-secondary/10 flex items-center justify-center text-secondary shrink-0">
            <Cpu size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              AI Intelligence &amp; Model Architecture
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
              Multi-provider selection, inference parameters, and reasoning engines
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onFetchModels}
          disabled={isFetchingModels}
          className="px-3 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 transition-colors font-medium text-[12px] flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer disabled:opacity-50 self-end sm:self-auto"
        >
          <ArrowClockwise
            size={13}
            weight="bold"
            className={isFetchingModels ? "animate-spin text-secondary" : "text-on-surface-variant"}
          />
          <span>
            {isFetchingModels
              ? "Fetching Models..."
              : `Fetch Models from ${PROVIDER_NAMES[llmProvider] || "Provider"}`}
          </span>
        </button>
      </div>

      {modelFetchFeedback && (
        <div
          className={`flex items-center gap-2 rounded-md border p-2.5 text-xs font-mono ${
            modelFetchFeedback.type === "success"
              ? "border-tertiary/30 bg-tertiary-container/15 text-tertiary"
              : "border-error/30 bg-error-container/20 text-error"
          }`}
        >
          {modelFetchFeedback.type === "success" ? (
            <CheckCircle size={15} weight="fill" className="shrink-0" />
          ) : (
            <WarningCircle size={15} weight="fill" className="shrink-0" />
          )}
          <span>{modelFetchFeedback.message}</span>
        </div>
      )}

      {/* Row 1: Provider Selection & Context-Aware Primary Credential */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* LLM Provider Architecture */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="llm-provider-select"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            LLM Provider Architecture
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <select
              id="llm-provider-select"
              aria-label="LLM Provider Architecture"
              value={llmProvider}
              onChange={(e) => onProviderChange?.(e.target.value)}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              <option value="nvidia">NVIDIA NIM (Hosted / High Performance)</option>
              <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
              <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
              <option value="gemini">Google Gemini (Gemini 2.0 Flash)</option>
              <option value="groq">Groq (Ultra-Low Latency Llama)</option>
              <option value="ollama">Ollama (Local Private Models)</option>
              <option value="openai-compatible">Custom OpenAI-Compatible</option>
            </select>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Underlying AI provider backend utilized across LangChain and LangGraph runners.
          </span>
        </div>

        {/* Dynamic Context-Aware Primary Credential */}
        {llmProvider === "nvidia" && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                NVIDIA NIM API Key
              </label>
              <button
                type="button"
                onClick={onToggleShowNimKey}
                aria-label="Toggle NIM API Key visibility"
                className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
              >
                <Eye size={13} />
                <span>{showNimKey ? "Hide" : "Show"}</span>
              </button>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type={showNimKey ? "text" : "password"}
                data-testid="nim-key-input"
                value={nimApiKey}
                onChange={(e) => onApiKeyChange(e.target.value)}
                placeholder="Enter NVIDIA_NIM_API_KEY (nvapi-...)"
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Personal API key from NVIDIA build catalog for local and agent execution.
            </span>
          </div>
        )}

        {llmProvider === "openai" && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                OpenAI API Key
              </label>
              <button
                type="button"
                onClick={() => setShowOpenaiKey((p) => !p)}
                className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
              >
                <Eye size={13} />
                <span>{showOpenaiKey ? "Hide" : "Show"}</span>
              </button>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type={showOpenaiKey ? "text" : "password"}
                value={openaiApiKey}
                onChange={(e) => onOpenaiApiKeyChange?.(e.target.value)}
                placeholder="sk-proj-..."
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Authentication key for OpenAI models.
            </span>
          </div>
        )}

        {llmProvider === "anthropic" && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Anthropic API Key
              </label>
              <button
                type="button"
                onClick={() => setShowAnthropicKey((p) => !p)}
                className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
              >
                <Eye size={13} />
                <span>{showAnthropicKey ? "Hide" : "Show"}</span>
              </button>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type={showAnthropicKey ? "text" : "password"}
                value={anthropicApiKey}
                onChange={(e) => onAnthropicApiKeyChange?.(e.target.value)}
                placeholder="sk-ant-..."
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Authentication key for Anthropic Claude models.
            </span>
          </div>
        )}

        {llmProvider === "gemini" && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Google Gemini API Key
              </label>
              <button
                type="button"
                onClick={() => setShowGeminiKey((p) => !p)}
                className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
              >
                <Eye size={13} />
                <span>{showGeminiKey ? "Hide" : "Show"}</span>
              </button>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type={showGeminiKey ? "text" : "password"}
                value={geminiApiKey}
                onChange={(e) => onGeminiApiKeyChange?.(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              API key from Google AI Studio for Gemini models.
            </span>
          </div>
        )}

        {llmProvider === "groq" && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                Groq API Key
              </label>
              <button
                type="button"
                onClick={() => setShowGroqKey((p) => !p)}
                className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
              >
                <Eye size={13} />
                <span>{showGroqKey ? "Hide" : "Show"}</span>
              </button>
            </div>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type={showGroqKey ? "text" : "password"}
                value={groqApiKey}
                onChange={(e) => onGroqApiKeyChange?.(e.target.value)}
                placeholder="gsk_..."
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Low-latency LPU inference key from Groq Cloud.
            </span>
          </div>
        )}

        {llmProvider === "ollama" && (
          <div className="flex flex-col gap-1.5">
            <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
              Ollama Daemon Endpoint URL
            </label>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type="text"
                value={ollamaBaseUrl}
                onChange={(e) => onOllamaBaseUrlChange?.(e.target.value)}
                placeholder="http://localhost:11434"
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Local Ollama HTTP daemon endpoint for private offline inference.
            </span>
          </div>
        )}

        {llmProvider === "openai-compatible" && (
          <div className="flex flex-col gap-1.5">
            <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
              Custom Base URL &amp; Key
            </label>
            <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-secondary transition-all">
              <input
                type="text"
                value={nimBaseUrl}
                onChange={(e) => onBaseUrlChange?.(e.target.value)}
                placeholder="https://api.together.xyz/v1"
                className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
              />
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Endpoint for self-hosted vLLM, Together AI, or custom proxies.
            </span>
          </div>
        )}
      </div>

      {/* Row 2: Primary and Fallback Models */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* Primary Model Selection */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="primary-nim-model-select"
              className="font-body-strong text-body-strong text-on-surface text-[12px]"
            >
              Primary Model Identifier
            </label>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              {modelsList.length > 0 ? `${modelsList.length} models available` : "No models fetched"}
            </span>
          </div>

          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <select
              id="primary-nim-model-select"
              aria-label="Primary LLM Model"
              data-testid="nim-model-select"
              value={isCustomModel ? "__custom__" : (nimModel || "")}
              onChange={(e) => {
                const val = e.target.value;
                if (val === "__custom__") {
                  onCustomModelToggle(true);
                } else {
                  onCustomModelToggle(false);
                  onModelChange(val);
                }
              }}
              className="w-full bg-transparent border-0 outline-none font-body-md text-body-md text-on-surface text-[13px] p-0 focus:ring-0 cursor-pointer"
            >
              {modelsList.length === 0 ? (
                <option value="" disabled>
                  No models loaded — enter key &amp; click &apos;Fetch Models&apos;
                </option>
              ) : (
                <optgroup label="Available Models">
                  {modelsList.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label="Other">
                <option value="__custom__">Enter custom model name...</option>
              </optgroup>
            </select>
          </div>

          {isCustomModel && (
            <input
              type="text"
              aria-label="Custom LLM Model Identifier"
              value={nimModel}
              onChange={(e) => onModelChange(e.target.value)}
              placeholder="e.g. model identifier URN or name"
              className="mt-1 w-full px-3 py-1.5 rounded-md bg-surface-container-low focus:bg-surface-container-lowest border border-secondary focus:border-secondary outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant text-[12px]"
            />
          )}

          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Primary model used for post triage, reasoning analysis, and comment drafting.
          </span>
        </div>

        {/* Fallback Model Selection */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="fallback-nim-model-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Fallback LLM Model
          </label>

          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <input
              id="fallback-nim-model-input"
              type="text"
              value={nimModelFallback}
              onChange={(e) => onModelFallbackChange?.(e.target.value)}
              placeholder="e.g. fallback model identifier (e.g. gpt-4o-mini)"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>

          <span className="font-label-sm text-[11px] text-on-surface-variant">
            High-reliability fallback model invoked automatically if primary model hits rate limits or errors.
          </span>
        </div>
      </div>

      {/* Row 3: Specialized Model Roles (Triage & Vision) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* Fast Triage Model */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="triage-model-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px] flex items-center gap-1.5"
          >
            <span>Fast Triage Model</span>
            <span className="font-label-sm text-[10px] text-on-surface-variant font-normal">
              (Optional)
            </span>
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <input
              id="triage-model-input"
              type="text"
              value={nimModelTriage}
              onChange={(e) => onModelTriageChange?.(e.target.value)}
              placeholder="e.g. lightweight model identifier (optional)"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Lightweight, high-speed model for initial feed scanning. Falls back to Primary Model if blank.
          </span>
        </div>

        {/* Multimodal Vision Model */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="vision-model-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Multimodal Vision Model
          </label>
          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <input
              id="vision-model-input"
              type="text"
              value={nimModelVision}
              onChange={(e) => onModelVisionChange?.(e.target.value)}
              placeholder="e.g. vision model identifier (e.g. gpt-4o)"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Analyzes post image attachments, architecture diagrams, and slide carousels.
          </span>
        </div>
      </div>

      {/* Disclosure Drawer A: Secondary & Fallback Provider Keys */}
      <div className="pt-2 border-t border-surface-container-high">
        <button
          type="button"
          onClick={() => setShowSecondaryKeys((prev) => !prev)}
          className="flex items-center gap-2 text-[12px] font-medium text-on-surface hover:text-secondary transition-colors cursor-pointer"
        >
          <Key size={14} className="text-secondary" />
          <span>Secondary &amp; Fallback Provider Credentials</span>
          <span className="text-[11px] text-on-surface-variant font-normal">
            {showSecondaryKeys ? "▴ Hide" : "▾ Expand"}
          </span>
        </button>

        {showSecondaryKeys && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3 p-3.5 rounded-md bg-surface-container-low/60 border border-outline-variant/20">
            {/* Secondary OpenAI Key */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-on-surface">OpenAI Key (Fallback)</label>
              <input
                type="password"
                value={openaiApiKey}
                onChange={(e) => onOpenaiApiKeyChange?.(e.target.value)}
                placeholder="sk-proj-..."
                className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
              />
            </div>

            {/* Secondary Anthropic Key */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-on-surface">Anthropic Key (Fallback)</label>
              <input
                type="password"
                value={anthropicApiKey}
                onChange={(e) => onAnthropicApiKeyChange?.(e.target.value)}
                placeholder="sk-ant-..."
                className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
              />
            </div>

            {/* Secondary Gemini Key */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-on-surface">Google Gemini Key (Fallback)</label>
              <input
                type="password"
                value={geminiApiKey}
                onChange={(e) => onGeminiApiKeyChange?.(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
              />
            </div>

            {/* Secondary Groq Key */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold text-on-surface">Groq Key (Fallback)</label>
              <input
                type="password"
                value={groqApiKey}
                onChange={(e) => onGroqApiKeyChange?.(e.target.value)}
                placeholder="gsk_..."
                className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
              />
            </div>
          </div>
        )}
      </div>

      {/* Disclosure Drawer B: Model Hyperparameters & Custom Endpoints */}
      <div className="pt-2 border-t border-surface-container-high">
        <button
          type="button"
          onClick={() => setShowHyperparameters((prev) => !prev)}
          className="flex items-center gap-2 text-[12px] font-medium text-on-surface hover:text-secondary transition-colors cursor-pointer"
        >
          <SlidersHorizontal size={14} className="text-secondary" />
          <span>Model Hyperparameters &amp; Custom Endpoints</span>
          <span className="text-[11px] text-on-surface-variant font-normal">
            {showHyperparameters ? "▴ Hide" : "▾ Expand"}
          </span>
        </button>

        {showHyperparameters && (
          <div className="flex flex-col gap-3.5 mt-3 p-3.5 rounded-md bg-surface-container-low/60 border border-outline-variant/20">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Temperature */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-semibold text-on-surface">Sampling Temperature</label>
                  <span className="font-mono text-[11px] text-secondary font-semibold">
                    {Number(nimTemperature).toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={nimTemperature}
                  onChange={(e) => onTemperatureChange?.(parseFloat(e.target.value))}
                  className="w-full accent-secondary cursor-pointer"
                />
                <span className="text-[10px] text-on-surface-variant">
                  0.0: Analytical &amp; deterministic; 1.0: Creative variety.
                </span>
              </div>

              {/* Max Tokens */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-on-surface">Max Generation Tokens</label>
                <input
                  type="number"
                  min="128"
                  max="4096"
                  step="64"
                  value={nimMaxTokens}
                  onChange={(e) => onMaxTokensChange?.(parseInt(e.target.value, 10))}
                  className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
                />
                <span className="text-[10px] text-on-surface-variant">
                  Hard ceiling on reasoning and draft output tokens.
                </span>
              </div>

              {/* Request Timeout */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold text-on-surface">Inference Timeout (Seconds)</label>
                <input
                  type="number"
                  min="5"
                  max="180"
                  step="5"
                  value={nimTimeoutSeconds}
                  onChange={(e) => onTimeoutChange?.(parseInt(e.target.value, 10))}
                  className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
                />
                <span className="text-[10px] text-on-surface-variant">
                  Maximum wait time before initiating secondary fallback.
                </span>
              </div>
            </div>

            {/* Custom Endpoints */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-outline-variant/20">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-semibold text-on-surface">Custom NIM Base URL</label>
                <input
                  type="text"
                  value={nimBaseUrl}
                  onChange={(e) => onBaseUrlChange?.(e.target.value)}
                  placeholder="https://integrate.api.nvidia.com/v1"
                  className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-semibold text-on-surface">Ollama Base URL</label>
                <input
                  type="text"
                  value={ollamaBaseUrl}
                  onChange={(e) => onOllamaBaseUrlChange?.(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-full px-2.5 py-1 rounded bg-surface-container-lowest border border-outline-variant/30 font-code-sm text-[11px] outline-none"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
