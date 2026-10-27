import React from "react";
import {
  Cpu,
  ArrowClockwise,
  CheckCircle,
  WarningCircle,
  Eye,
} from "../../components/icons";

interface NimIntelligenceCardProps {
  nimModel: string;
  nimApiKey: string;
  nimModelFallback?: string;
  llmProvider?: string;
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
  onFetchModels: () => void;
}

export const NimIntelligenceCard: React.FC<NimIntelligenceCardProps> = ({
  nimModel,
  nimApiKey,
  nimModelFallback = "openai/gpt-oss-20b",
  llmProvider = "nvidia",
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
  onFetchModels,
}) => {
  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-secondary/10 flex items-center justify-center text-secondary shrink-0">
            <Cpu size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              NVIDIA NIM Intelligence &amp; LLM Engine
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
              Model selection, structured output parser, and inference credentials
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
          <span>{isFetchingModels ? "Fetching Models..." : "Fetch Models from NVIDIA"}</span>
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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* LLM Provider */}
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

        {/* NIM API Key */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
              NVIDIA NIM API Key
            </label>
            <button
              type="button"
              onClick={onToggleShowNimKey}
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
              {modelsList.length} models available
            </span>
          </div>

          <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-secondary">
            <select
              id="primary-nim-model-select"
              aria-label="Primary NIM Model"
              data-testid="nim-model-select"
              value={isCustomModel ? "__custom__" : (nimModel || "nvidia/nemotron-3-ultra-550b-a55b")}
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
              <optgroup label="Available Models">
                {modelsList.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Other">
                <option value="__custom__">Enter custom model name...</option>
              </optgroup>
            </select>
          </div>

          {isCustomModel && (
            <input
              type="text"
              aria-label="Custom NIM Model Identifier"
              value={nimModel}
              onChange={(e) => onModelChange(e.target.value)}
              placeholder="e.g. nvidia/nemotron-3-ultra-550b-a55b or custom URN"
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
              placeholder="e.g. openai/gpt-oss-20b or gpt-4o-mini"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>

          <span className="font-label-sm text-[11px] text-on-surface-variant">
            High-reliability fallback model invoked automatically if primary model hits rate limits or errors.
          </span>
        </div>
      </div>
    </div>
  );
};
