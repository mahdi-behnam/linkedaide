import React, { useState } from "react";
import { Target, Hash, Globe, Plus, X, Trash } from "../../components/icons";

interface ScoutTargetingCardProps {
  userPersona: string;
  userFocusAreas: string[];
  targetHashtags: string[];
  scoutTargetUrls: string[];
  onPersonaChange: (persona: string) => void;
  onFocusAreasChange: (areas: string[]) => void;
  onHashtagsChange: (hashtags: string[]) => void;
  onTargetUrlsChange: (urls: string[]) => void;
}

export const ScoutTargetingCard: React.FC<ScoutTargetingCardProps> = ({
  userPersona,
  userFocusAreas,
  targetHashtags,
  scoutTargetUrls,
  onPersonaChange,
  onFocusAreasChange,
  onHashtagsChange,
  onTargetUrlsChange,
}) => {
  const [newFocusInput, setNewFocusInput] = useState("");
  const [newHashtagInput, setNewHashtagInput] = useState("");
  const [newUrlInput, setNewUrlInput] = useState("");

  const handleAddFocusArea = () => {
    const trimmed = newFocusInput.trim();
    if (!trimmed) return;
    if (!userFocusAreas.includes(trimmed)) {
      onFocusAreasChange([...userFocusAreas, trimmed]);
    }
    setNewFocusInput("");
  };

  const handleRemoveFocusArea = (index: number) => {
    onFocusAreasChange(userFocusAreas.filter((_, i) => i !== index));
  };

  const handleAddHashtag = () => {
    let trimmed = newHashtagInput.trim();
    if (!trimmed) return;
    // Normalize: ensure clean #tag format
    if (!trimmed.startsWith("#")) {
      trimmed = `#${trimmed}`;
    }
    // Clean hashtag alphanumeric + underscore
    trimmed = `#${trimmed.replace(/^#+/, "").toLowerCase()}`;
    if (trimmed !== "#" && !targetHashtags.includes(trimmed)) {
      onHashtagsChange([...targetHashtags, trimmed]);
    }
    setNewHashtagInput("");
  };

  const handleRemoveHashtag = (index: number) => {
    onHashtagsChange(targetHashtags.filter((_, i) => i !== index));
  };

  const handleAddUrl = () => {
    const trimmed = newUrlInput.trim();
    if (!trimmed) return;
    if (!scoutTargetUrls.includes(trimmed)) {
      onTargetUrlsChange([...scoutTargetUrls, trimmed]);
    }
    setNewUrlInput("");
  };

  const handleRemoveUrl = (index: number) => {
    onTargetUrlsChange(scoutTargetUrls.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex items-center gap-2.5 pb-1 border-b border-surface-container-high">
        <div className="w-8 h-8 rounded-md bg-blue-500/10 flex items-center justify-center text-blue-500 shrink-0">
          <Target size={16} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Scout Targets &amp; Focus Topics
          </h2>
          <p className="font-label-sm text-[11px] text-on-surface-variant">
            Hashtags, direct feed URLs, and domain evaluation topics for intelligent post discovery
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4 pt-1">
        {/* Thought Leadership Voice & Persona */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="user-persona-input"
              className="font-body-strong text-body-strong text-on-surface text-[12px] flex items-center gap-1.5"
            >
              <span>Thought Leadership Voice &amp; Persona</span>
            </label>
            <span className="font-label-sm text-[11px] text-on-surface-variant font-mono">
              {userPersona ? userPersona.length : 0} characters
            </span>
          </div>
          <textarea
            id="user-persona-input"
            rows={3}
            value={userPersona || ""}
            onChange={(e) => onPersonaChange(e.target.value)}
            placeholder="e.g. Senior Software Architect specializing in distributed consensus, edge computing, and Kubernetes. Shares analytical, high-substance engineering perspectives without corporate buzzwords."
            className="w-full rounded-md bg-surface-container-low border border-outline-variant/30 p-2.5 font-body-md text-on-surface text-[12px] placeholder:text-on-surface-variant/50 focus:border-blue-500 focus:outline-none resize-y min-h-[72px]"
          />
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Defines your background, professional voice, perspective, and domain terminology for generated comments and post drafts.
          </span>
        </div>

        {/* User Focus Areas */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="focus-area-input"
              className="font-body-strong text-body-strong text-on-surface text-[12px] flex items-center gap-1.5"
            >
              <span>User Focus Areas</span>
              <span className="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant">
                {userFocusAreas.length} active
              </span>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 p-2 rounded-md bg-surface-container-low border border-outline-variant/30 min-h-[38px]">
            {userFocusAreas.map((topic, idx) => (
              <span
                key={`${topic}-${idx}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container text-on-surface text-[11px] font-medium border border-outline-variant/30"
              >
                <span>{topic}</span>
                <button
                  type="button"
                  aria-label={`Remove focus area ${topic}`}
                  onClick={() => handleRemoveFocusArea(idx)}
                  className="text-on-surface-variant hover:text-error transition-colors ml-0.5 cursor-pointer"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
            <div className="flex items-center gap-1 flex-1 min-w-[160px]">
              <input
                id="focus-area-input"
                type="text"
                value={newFocusInput}
                onChange={(e) => setNewFocusInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddFocusArea();
                  }
                }}
                placeholder="Add focus topic (e.g. Agentic AI, PyTorch) and press Enter..."
                className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[12px] p-0 focus:ring-0 placeholder:text-on-surface-variant/60"
              />
              {newFocusInput.trim() && (
                <button
                  type="button"
                  aria-label="Add focus area"
                  onClick={handleAddFocusArea}
                  className="p-1 rounded hover:bg-surface-container text-primary cursor-pointer shrink-0"
                >
                  <Plus size={13} weight="bold" />
                </button>
              )}
            </div>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Domain topics and technical specialties evaluated by LLM triage to prioritize high-value posts.
          </span>
        </div>

        {/* Target Hashtags */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="target-hashtag-input"
              className="font-body-strong text-body-strong text-on-surface text-[12px] flex items-center gap-1.5"
            >
              <span>Target Hashtags</span>
              <span className="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant">
                {targetHashtags.length} configured
              </span>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 p-2 rounded-md bg-surface-container-low border border-outline-variant/30 min-h-[38px]">
            {targetHashtags.map((tag, idx) => (
              <span
                key={`${tag}-${idx}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container text-primary text-[11px] font-mono border border-outline-variant/30"
              >
                <Hash size={11} className="opacity-70" />
                <span>{tag.replace(/^#/, "")}</span>
                <button
                  type="button"
                  aria-label={`Remove hashtag ${tag}`}
                  onClick={() => handleRemoveHashtag(idx)}
                  className="text-on-surface-variant hover:text-error transition-colors ml-0.5 cursor-pointer"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
            <div className="flex items-center gap-1 flex-1 min-w-[160px]">
              <input
                id="target-hashtag-input"
                type="text"
                value={newHashtagInput}
                onChange={(e) => setNewHashtagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddHashtag();
                  }
                }}
                placeholder="Add hashtag (e.g. #python, #ai) and press Enter..."
                className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[12px] p-0 focus:ring-0 placeholder:text-on-surface-variant/60 font-mono"
              />
              {newHashtagInput.trim() && (
                <button
                  type="button"
                  aria-label="Add target hashtag"
                  onClick={handleAddHashtag}
                  className="p-1 rounded hover:bg-surface-container text-primary cursor-pointer shrink-0"
                >
                  <Plus size={13} weight="bold" />
                </button>
              )}
            </div>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Specific hashtag feeds to scout during each run in addition to your primary timeline (auto-normalized with #).
          </span>
        </div>

        {/* Custom Target URLs */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="target-url-input"
              className="font-body-strong text-body-strong text-on-surface text-[12px] flex items-center gap-1.5"
            >
              <span>Direct Target URLs</span>
              <span className="font-code-sm text-[10px] px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant">
                {scoutTargetUrls.length} configured
              </span>
            </label>
          </div>

          <div className="flex flex-col gap-1.5">
            {scoutTargetUrls.map((url, idx) => (
              <div
                key={`${url}-${idx}`}
                className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 text-[12px]"
              >
                <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap mr-2">
                  <Globe size={13} className="text-on-surface-variant shrink-0" />
                  <span className="font-mono text-on-surface text-[11px] truncate">
                    {url}
                  </span>
                </div>
                <button
                  type="button"
                  aria-label={`Remove URL ${url}`}
                  onClick={() => handleRemoveUrl(idx)}
                  className="text-on-surface-variant hover:text-error transition-colors p-1 cursor-pointer shrink-0"
                >
                  <Trash size={13} />
                </button>
              </div>
            ))}

            <div className="flex items-center gap-1.5">
              <div className="flex-1 flex items-center px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus-within:border-blue-500">
                <Globe size={14} className="text-on-surface-variant mr-2 shrink-0" />
                <input
                  id="target-url-input"
                  type="url"
                  value={newUrlInput}
                  onChange={(e) => setNewUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddUrl();
                    }
                  }}
                  placeholder="https://www.linkedin.com/company/.../posts/ or feed URL"
                  className="w-full bg-transparent border-0 outline-none font-body-md text-on-surface text-[12px] p-0 focus:ring-0 placeholder:text-on-surface-variant/60 font-mono"
                />
              </div>
              <button
                type="button"
                aria-label="Add target URL"
                onClick={handleAddUrl}
                disabled={!newUrlInput.trim()}
                className="px-3 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 hover:bg-surface-container text-on-surface text-[12px] font-medium flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Plus size={13} weight="bold" />
                <span>Add</span>
              </button>
            </div>
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Direct LinkedIn URLs (creator activity tabs, company posts) to scrape during scout runs.
          </span>
        </div>
      </div>
    </div>
  );
};
