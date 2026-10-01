import React, { useState, useMemo, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import { ScheduledPost, MediaAttachment } from "../types";
import {
  PencilSimple,
  Sparkle,
  FilePdf,
  Image as ImageIcon,
  Calendar,
  Clock,
  CheckCircle,
  Lightning,
  Trash,
  Eye,
  CaretLeft,
  CaretRight,
  UploadSimple,
  IconProps,
} from "../components/icons";
import { VoiceDictationButton } from "../components/VoiceDictationButton";

interface HookArchetype {
  id: string;
  name: string;
  tagline: string;
  icon: React.ComponentType<IconProps>;
  templates: Record<string, string>;
}

const HOOK_ARCHETYPES: HookArchetype[] = [
  {
    id: "contrarian",
    name: "Contrarian Stance",
    tagline: "Challenge prevailing industry consensus with conviction",
    icon: Lightning,
    templates: {
      "Agent Architecture":
        "Most engineering teams are building agent workflows completely wrong:\n\nThey rely on autonomous ReAct loops instead of deterministic state machines.",
      "Distributed Systems":
        "Database-backed state stores are often overkill for agent pipelines:\n\nPrivate edge KV namespaces provide sub-40ms latency without commit storms.",
      "AI Safety & Guardrails":
        "Prompt-based safety filters do not work in production:\n\nDeterministic code gates and human verification are the only real safety invariant.",
      "System Design":
        "Microservices for LLM agents introduce unnecessary operational friction:\n\nA compact, typed workflow engine outperforms distributed graphs 10x.",
      General:
        "The prevailing approach to this problem is fundamentally backwards:\n\nHere is why the consensus fails when scaled to production.",
    },
  },
  {
    id: "data_shock",
    name: "Data Shock",
    tagline: "Anchor attention with a surprising, counter-intuitive statistic",
    icon: Sparkle,
    templates: {
      "Agent Architecture":
        "93% of LLM production incidents are not hallucination errors:\n\nThey are state leakage, race conditions, and unverified side effects.",
      "Distributed Systems":
        "Over 80% of automated CI failures in multi-agent repos stem from git merge conflicts in state files.",
      "AI Safety & Guardrails":
        "Only 6% of enterprise AI prototypes survive into production without human approval loops.",
      "System Design":
        "74% of API latency in agentic systems is spent waiting for un-cached model round-trips.",
      General:
        "87% of teams struggle with this specific bottleneck in production:\n\nHere is the exact data breakdown and how we addressed it.",
    },
  },
  {
    id: "micro_story",
    name: "Micro-Story Teardown",
    tagline: "Hook readers with a vivid, high-stakes incident narrative",
    icon: Clock,
    templates: {
      "Agent Architecture":
        "Last Tuesday at 2 AM, our production agent halted mid-execution:\n\nHere is the exact architectural flaw that triggered the incident, and how we resolved it in 15 minutes.",
      "Distributed Systems":
        "We watched our state synchronization deadlock across three regions simultaneously.\n\nThe culprit? A 3-line retry loop with no jitter.",
      "AI Safety & Guardrails":
        "A client almost published an unreviewed autonomous comment to 500k followers.\n\nOur Telegram HITL approval circuit tripped just in time. Here is the postmortem.",
      "System Design":
        "We spent three weeks chasing an intermittent agent bug.\n\nThe root cause was surprisingly simple, and it changed how we design all state stores.",
      General:
        "Three days ago, a small edge case brought down our primary pipeline:\n\nHere is the step-by-step postmortem and the key takeaway.",
    },
  },
  {
    id: "framework",
    name: "Counter-Intuitive Framework",
    tagline: "Introduce a surprising mental model that reframes the problem",
    icon: CheckCircle,
    templates: {
      "Agent Architecture":
        "The fastest way to scale autonomous systems is to make human approval mandatory:\n\nHere is the 3-layer architecture we use to guarantee zero unintended side effects.",
      "Distributed Systems":
        "To increase automation velocity, you must slow down write executions.\n\nHere is the dual-queue rate limiting framework that protects our accounts.",
      "AI Safety & Guardrails":
        "Zero-trust session vaults: Why browser session cookies should never touch CI/CD runner logs.\n\nHere is our Fernet encryption architecture.",
      "System Design":
        "The Inverted Pipeline pattern: How to design workflows where the model proposes but deterministic code executes.",
      General:
        "The 3-stage validation framework that eliminated 99% of our deployment regressions:\n\n1. State isolation\n2. Deterministic triage\n3. Dom-verified execution",
    },
  },
  {
    id: "synthesis",
    name: "Curated Synthesis",
    tagline: "Condense deep research or extensive production experience",
    icon: PencilSimple,
    templates: {
      "Agent Architecture":
        "I analyzed 50 enterprise agent deployments over the last 6 months:\n\n4 non-negotiable architectural patterns emerged across every successful system.",
      "Distributed Systems":
        "After auditing 12 high-throughput edge architectures, here are the 5 lessons on state persistence nobody talks about.",
      "AI Safety & Guardrails":
        "We tested 1,000 edge cases against human-in-the-loop agents:\n\nThese 3 safety invariants prevented 100% of unauthorized platform actions.",
      "System Design":
        "A comprehensive teardown of production LLM orchestration engines: LangGraph, Temporal, and custom state machines compared.",
      General:
        "After 200 hours of performance tuning and production benchmarks:\n\nHere are the top 5 takeaways you can apply to your stack today.",
    },
  },
];

const TOPIC_PILLARS = [
  "Agent Architecture",
  "Distributed Systems",
  "AI Safety & Guardrails",
  "System Design",
  "General",
];



export const ComposerView: React.FC = () => {
  const {
    saveScheduledPost,
    activePostForEditing,
    setActivePostForEditing,
    setCurrentTab,
  } = useApp();

  const [headline, setHeadline] = useState("");
  const [postText, setPostText] = useState("");
  const [topicPillar, setTopicPillar] = useState("Agent Architecture");
  const [scheduledDate, setScheduledDate] = useState("");
  const [scheduledTime, setScheduledTime] = useState("14:00");
  const [mediaList, setMediaList] = useState<MediaAttachment[]>([]);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [appliedHookName, setAppliedHookName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize or populate when activePostForEditing changes
  useEffect(() => {
    if (activePostForEditing) {
      setHeadline(activePostForEditing.headline);
      setPostText(activePostForEditing.post_text);
      setTopicPillar(activePostForEditing.topic_pillar || "Agent Architecture");
      setMediaList(activePostForEditing.media || []);
      if (activePostForEditing.scheduled_time) {
        const d = new Date(activePostForEditing.scheduled_time);
        if (!isNaN(d.getTime())) {
          setScheduledDate(d.toISOString().split("T")[0]);
          setScheduledTime(
            d.toISOString().split("T")[1]?.substring(0, 5) || "14:00"
          );
        }
      }
    } else {
      // Default scheduled date to tomorrow
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      setScheduledDate(tomorrow.toISOString().split("T")[0]);
    }
  }, [activePostForEditing]);

  // Editor metrics
  const charCount = postText.length;
  const wordCount = useMemo(() => {
    const trimmed = postText.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }, [postText]);

  const readingTimeMin = useMemo(() => {
    if (wordCount < 100) return "< 1 min read";
    const mins = Math.ceil(wordCount / 200);
    return `~${mins} min read`;
  }, [wordCount]);

  // 140-Character Mobile Cutoff Calculations
  const foldCutoff = 140;
  const aboveFoldText = postText.slice(0, foldCutoff);
  const belowFoldText = postText.slice(foldCutoff);
  const isOverFold = charCount > foldCutoff;
  const charsRemainingInFold = Math.max(0, foldCutoff - charCount);

  // Apply AI Hook
  const handleApplyHook = (archetype: HookArchetype) => {
    const template =
      archetype.templates[topicPillar] || archetype.templates["General"];
    if (!postText.trim()) {
      setPostText(template);
    } else {
      // Prepend hook or replace opening paragraph
      const paragraphs = postText.split("\n\n");
      if (paragraphs.length > 1) {
        setPostText(`${template}\n\n${paragraphs.slice(1).join("\n\n")}`);
      } else {
        setPostText(`${template}\n\n${postText}`);
      }
    }
    setAppliedHookName(archetype.name);
    setFeedbackMessage(`Applied ${archetype.name} hook archetype.`);
    setTimeout(() => setFeedbackMessage(null), 4000);
  };

  // Remove media
  const handleRemoveMedia = () => {
    setMediaList([]);
    setCurrentSlideIndex(0);
  };

  // Upload user file from device
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const fileUrl =
      typeof window !== "undefined" && window.URL && typeof window.URL.createObjectURL === "function"
        ? window.URL.createObjectURL(file)
        : "";
    const attachment: MediaAttachment = {
      media_type: isPdf ? "carousel_pdf" : "image",
      file_name: file.name,
      file_url: fileUrl,
      slide_count: isPdf ? 5 : 1,
    };
    setMediaList([attachment]);
    setCurrentSlideIndex(0);
    setFeedbackMessage(`Attached ${isPdf ? "PDF document" : "image"}: ${file.name}`);
    setTimeout(() => setFeedbackMessage(null), 3000);
  };

  // Save as Draft
  const handleSaveDraft = () => {
    if (!postText.trim()) {
      setFeedbackMessage("Please add post text before saving draft.");
      return;
    }

    const post: ScheduledPost = {
      id: activePostForEditing?.id || `post-${Date.now().toString(36)}`,
      headline: headline || "Untitled Draft Post",
      post_text: postText,
      scheduled_time: scheduledDate
        ? new Date(`${scheduledDate}T${scheduledTime}:00Z`).toISOString()
        : null,
      status: "draft",
      media: mediaList,
      topic_pillar: topicPillar,
      created_at: activePostForEditing?.created_at || new Date().toISOString(),
      approved_at: activePostForEditing?.approved_at,
    };

    saveScheduledPost(post);
    setFeedbackMessage("Draft saved successfully.");
    setTimeout(() => setFeedbackMessage(null), 3500);
  };

  // Schedule Post
  const handleSchedulePost = () => {
    if (!postText.trim()) {
      setFeedbackMessage("Please add post text before scheduling.");
      return;
    }
    if (!scheduledDate) {
      setFeedbackMessage("Please select a scheduled date.");
      return;
    }

    const post: ScheduledPost = {
      id: activePostForEditing?.id || `post-${Date.now().toString(36)}`,
      headline: headline || "Scheduled Original Post",
      post_text: postText,
      scheduled_time: new Date(`${scheduledDate}T${scheduledTime}:00Z`).toISOString(),
      status: "scheduled",
      media: mediaList,
      topic_pillar: topicPillar,
      created_at: activePostForEditing?.created_at || new Date().toISOString(),
      approved_at: new Date().toISOString(),
    };

    saveScheduledPost(post);
    setFeedbackMessage("Post scheduled successfully. Added to Content Calendar.");
    setTimeout(() => {
      setFeedbackMessage(null);
      setActivePostForEditing(null);
      setCurrentTab("calendar");
    }, 1200);
  };

  const activeMedia = mediaList[0];
  const totalSlides = activeMedia?.slide_count || 1;

  return (
    <div className="space-y-6">
      {/* Studio Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <PencilSimple size={18} weight="bold" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              Post Composer Studio
            </h1>
            <span className="rounded border border-zinc-800 bg-zinc-900/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
              v1.2 High-Signal
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Draft high-converting technical LinkedIn posts with AI hook archetypes, above-the-fold cutoff analysis, and carousel previews.
          </p>
        </div>

        {/* Top Action Pills */}
        <div className="flex items-center gap-2">
          {activePostForEditing && (
            <button
              type="button"
              onClick={() => {
                setActivePostForEditing(null);
                setHeadline("");
                setPostText("");
                setMediaList([]);
              }}
              className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-xs text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
            >
              <span>New Blank Post</span>
            </button>
          )}
          <button
            type="button"
            data-testid="view-calendar-quick-btn"
            onClick={() => setCurrentTab("calendar")}
            className="flex items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:border-zinc-700 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <Calendar size={14} className="text-zinc-400" />
            <span>Open Calendar</span>
          </button>
        </div>
      </div>

      {/* Feedback Toast Notification */}
      {feedbackMessage && (
        <div
          data-testid="composer-feedback"
          className="flex items-center justify-between rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-300"
        >
          <div className="flex items-center gap-2">
            <CheckCircle size={15} weight="bold" className="text-emerald-400" />
            <span>{feedbackMessage}</span>
          </div>
          <span className="font-mono text-[10px] text-emerald-500">Live Status</span>
        </div>
      )}

      {/* Topic Pillar & Working Headline */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-400">
            Working Headline / Concept Title
          </label>
          <input
            type="text"
            data-testid="post-headline-input"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. The 3 Invariants of Production LLM Agents"
            className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-900/60 px-3.5 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-hidden"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-400">
            Topic Pillar
          </label>
          <select
            data-testid="topic-pillar-select"
            value={topicPillar}
            onChange={(e) => setTopicPillar(e.target.value)}
            className="mt-1.5 w-full rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-200 focus:border-emerald-500/50 focus:outline-hidden"
          >
            {TOPIC_PILLARS.map((p) => (
              <option key={p} value={p} className="bg-zinc-900 text-zinc-200">
                {p}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* AI Hook Studio Bar */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <Sparkle size={16} className="text-amber-400" />
            <h2 className="text-xs font-semibold tracking-wide text-zinc-200 uppercase">
              AI Hook Studio
            </h2>
            <span className="font-mono text-[10px] text-zinc-500">
              1-Click High-Retention Openers
            </span>
          </div>
          {appliedHookName && (
            <span className="rounded bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-300">
              Active: {appliedHookName}
            </span>
          )}
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          {HOOK_ARCHETYPES.map((arch) => {
            const Icon = arch.icon;
            return (
              <button
                key={arch.id}
                type="button"
                data-testid={`hook-btn-${arch.id}`}
                onClick={() => handleApplyHook(arch)}
                className="group flex flex-col justify-between rounded-md border border-zinc-800/90 bg-zinc-950/60 p-3 text-left transition-all duration-150 hover:border-zinc-700 hover:bg-zinc-900/80 active:translate-y-[1px] active:scale-[0.98]"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded border border-zinc-800 bg-zinc-900 text-zinc-300 transition-colors group-hover:border-zinc-700 group-hover:text-emerald-400">
                    <Icon size={13} />
                  </div>
                  <span className="text-xs font-medium text-zinc-200 group-hover:text-emerald-300">
                    {arch.name}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-[11px] text-zinc-500 group-hover:text-zinc-400">
                  {arch.tagline}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Composer Layout: Editor + Mobile Fold + Previewer */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Interactive Editor & Metrics (7 cols) */}
        <div className="space-y-4 lg:col-span-7">
          {/* Editor Header Bar with Counters */}
          <div className="flex items-center justify-between rounded-t-md border border-b-0 border-zinc-800 bg-zinc-900/80 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <PencilSimple size={14} className="text-emerald-400" />
              <span className="text-xs font-medium text-zinc-300">
                Post Text Editor
              </span>
              <div className="mx-1 h-3.5 w-px bg-zinc-700/60" />
              <VoiceDictationButton
                onTranscript={(text) => {
                  setPostText((prev) => (prev ? `${prev} ${text}` : text));
                }}
              />
            </div>
            {/* Real-time Character, Word & Reading Time Estimates */}
            <div className="flex items-center gap-3 font-mono text-[11px] text-zinc-400">
              <span data-testid="char-counter" className="text-zinc-300">
                {charCount} / 3000 chars
              </span>
              <span className="text-zinc-600">|</span>
              <span data-testid="word-counter">{wordCount} words</span>
              <span className="text-zinc-600">|</span>
              <span data-testid="reading-time" className="text-zinc-400">
                {readingTimeMin}
              </span>
            </div>
          </div>

          {/* Text Area Editor */}
          <div className="relative">
            <textarea
              data-testid="post-content-editor"
              value={postText}
              onChange={(e) => setPostText(e.target.value)}
              rows={12}
              placeholder="Write your LinkedIn post here... Focus on technical depth, clear takeaways, and concrete metrics."
              className="w-full resize-y rounded-b-md border border-zinc-800 bg-zinc-950 p-4 font-sans text-xs leading-relaxed text-zinc-100 placeholder-zinc-600 focus:border-emerald-500/50 focus:outline-hidden"
            />
          </div>

          {/* Above-the-Fold 140-Character Cutoff Line Component */}
          <div
            data-testid="cutoff-indicator"
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Eye size={15} className="text-cyan-400" />
                <span className="text-xs font-semibold tracking-wide text-zinc-200">
                  Above-the-Fold 140-Character Mobile Cutoff
                </span>
              </div>
              <span
                data-testid="fold-status-badge"
                className={`rounded px-2 py-0.5 font-mono text-[10px] font-medium ${
                  isOverFold
                    ? "border border-amber-500/30 bg-amber-500/10 text-amber-300"
                    : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                }`}
              >
                {isOverFold
                  ? `${charCount - foldCutoff} chars below fold (...see more)`
                  : `${charsRemainingInFold} chars remaining in fold`}
              </span>
            </div>

            {/* Fold Progress Meter */}
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
              <div
                className={`h-full transition-all duration-200 ${
                  isOverFold ? "bg-amber-400" : "bg-emerald-400"
                }`}
                style={{
                  width: `${Math.min(100, (charCount / foldCutoff) * 100)}%`,
                }}
              />
            </div>

            {/* Visual Fold Splitter Simulation */}
            <div className="mt-3.5 rounded-md border border-zinc-800/80 bg-zinc-950/80 p-3 font-sans text-xs">
              <div className="text-[11px] font-medium text-zinc-400">
                Mobile Feed First Viewport:
              </div>
              <p className="mt-1 text-zinc-200">
                {aboveFoldText || (
                  <span className="text-zinc-600 italic">
                    Type in the editor to test your above-the-fold opening...
                  </span>
                )}
              </p>

              {/* Cutoff Divider Line */}
              {isOverFold && (
                <div
                  data-testid="visual-fold-line"
                  className="my-2.5 flex items-center gap-2 font-mono text-[10px] text-amber-400/90"
                >
                  <div className="h-px flex-1 border-t border-dashed border-amber-500/40" />
                  <span className="rounded bg-amber-500/10 px-2 py-0.5">
                    140 Chars Fold Cutoff (...see more)
                  </span>
                  <div className="h-px flex-1 border-t border-dashed border-amber-500/40" />
                </div>
              )}

              {/* Below Fold Preview */}
              {isOverFold && (
                <p className="text-[11px] text-zinc-500 line-clamp-2">
                  {belowFoldText}
                </p>
              )}
            </div>

            <p className="mt-2 text-[11px] text-zinc-500">
              LinkedIn mobile cuts off post copy around 140 characters before showing &quot;...see more&quot;. Your hook must create curiosity before this line.
            </p>
          </div>
        </div>

        {/* Right Column: Carousel PDF / Image Previewer (5 cols) */}
        <div className="space-y-4 lg:col-span-5">
          <div
            data-testid="media-previewer"
            className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
          >
            {/* Previewer Header */}
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                {activeMedia?.media_type === "carousel_pdf" ? (
                  <FilePdf size={16} className="text-red-400" />
                ) : (
                  <ImageIcon size={16} className="text-blue-400" />
                )}
                <span className="text-xs font-semibold text-zinc-200">
                  {activeMedia
                    ? activeMedia.media_type === "carousel_pdf"
                      ? "Carousel PDF Previewer"
                      : "Image Attachment Preview"
                    : "Media Attachment Studio"}
                </span>
              </div>
              {activeMedia && (
                <button
                  type="button"
                  data-testid="remove-media-btn"
                  onClick={handleRemoveMedia}
                  className="flex items-center gap-1 rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-red-400"
                  title="Remove media"
                >
                  <Trash size={13} />
                </button>
              )}
            </div>

            {/* Media Dropzone and Upload */}
            {!activeMedia ? (
              <div
                data-testid="media-dropzone"
                className="my-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-800 bg-zinc-950/60 p-6 text-center transition-colors hover:border-zinc-700"
              >
                <input
                  ref={fileInputRef}
                  data-testid="media-file-input"
                  type="file"
                  accept="application/pdf,image/png,image/jpeg,image/webp"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900 text-zinc-400">
                  <UploadSimple size={20} />
                </div>
                <p className="mt-2 text-xs font-medium text-zinc-300">
                  Drag and drop carousel PDF or image
                </p>
                <p className="mt-1 text-[11px] text-zinc-500">
                  Supports multi-slide PDF documents and high-res PNG/JPG
                </p>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="mt-3 flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20 active:translate-y-[1px]"
                >
                  <UploadSimple size={14} className="text-emerald-400" />
                  <span>Browse Device Files</span>
                </button>
              </div>
            ) : (
              /* Media Preview Canvas */
              <div className="my-3 space-y-3">
                {/* Meta info strip */}
                <div className="flex items-center justify-between font-mono text-[11px] text-zinc-400">
                  <span className="truncate max-w-[200px]" title={activeMedia.file_name}>
                    {activeMedia.file_name}
                  </span>
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-300">
                    {activeMedia.media_type === "carousel_pdf"
                      ? `${activeMedia.slide_count} Slides`
                      : "Single Image"}
                  </span>
                </div>

                {/* Interactive Slide Canvas */}
                <div className="relative aspect-4/3 w-full overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 p-4 shadow-inner">
                  {activeMedia.media_type === "carousel_pdf" ? (
                    <div className="flex h-full flex-col justify-between">
                      {/* Slide Header */}
                      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                        <span className="font-mono text-[10px] text-emerald-400 uppercase tracking-widest">
                          LinkedIn Safe Agent
                        </span>
                        <span className="font-mono text-[10px] text-zinc-500">
                          Slide {currentSlideIndex + 1} of {totalSlides}
                        </span>
                      </div>

                      {/* Slide Core Content */}
                      <div className="flex flex-1 flex-col items-center justify-center p-4 text-center">
                        <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 text-red-400">
                          <FilePdf size={24} />
                        </div>
                        <h3 className="text-xs font-semibold text-zinc-200 truncate max-w-xs">
                          {activeMedia.file_name}
                        </h3>
                        <p className="mt-1 font-mono text-[11px] text-zinc-400">
                          Page {currentSlideIndex + 1} of {totalSlides}
                        </p>
                        <p className="mt-1.5 text-[10px] text-zinc-500">
                          Multi-page Carousel Document
                        </p>
                      </div>

                      {/* Slide Footer */}
                      <div className="flex items-center justify-between border-t border-zinc-800/80 pt-2 font-mono text-[9px] text-zinc-500">
                        <span>Swipe to explore &rarr;</span>
                        <span>PDF Carousel</span>
                      </div>
                    </div>
                  ) : (
                    /* Image preview */
                    <div className="flex h-full flex-col items-center justify-center text-center p-2">
                      {activeMedia.file_url && (activeMedia.file_url.startsWith("blob:") || activeMedia.file_url.startsWith("data:") || activeMedia.file_url.startsWith("http")) ? (
                        <img
                          src={activeMedia.file_url}
                          alt={activeMedia.file_name}
                          className="max-h-40 max-w-full rounded object-contain"
                        />
                      ) : (
                        <ImageIcon size={36} className="text-blue-400/80" />
                      )}
                      <p className="mt-2 text-xs font-medium text-zinc-200 truncate max-w-xs">
                        {activeMedia.file_name}
                      </p>
                      <p className="mt-1 text-[11px] text-zinc-500">
                        Image attachment ({activeMedia.file_name.endsWith(".png") ? "PNG" : activeMedia.file_name.endsWith(".jpg") || activeMedia.file_name.endsWith(".jpeg") ? "JPEG" : "Media"})
                      </p>
                    </div>
                  )}
                </div>

                {/* Multi-Slide Navigation Controls */}
                {activeMedia.media_type === "carousel_pdf" && (
                  <div className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2">
                    <button
                      type="button"
                      data-testid="prev-slide-btn"
                      disabled={currentSlideIndex === 0}
                      onClick={() => setCurrentSlideIndex((prev) => Math.max(0, prev - 1))}
                      className="flex items-center gap-1 rounded p-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-30 disabled:hover:bg-transparent"
                    >
                      <CaretLeft size={14} />
                      <span>Previous</span>
                    </button>

                    <span
                      data-testid="slide-indicator"
                      className="font-mono text-xs text-zinc-300"
                    >
                      Slide {currentSlideIndex + 1} of {totalSlides}
                    </span>

                    <button
                      type="button"
                      data-testid="next-slide-btn"
                      disabled={currentSlideIndex >= totalSlides - 1}
                      onClick={() =>
                        setCurrentSlideIndex((prev) =>
                          Math.min(totalSlides - 1, prev + 1)
                        )
                      }
                      className="flex items-center gap-1 rounded p-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-30 disabled:hover:bg-transparent"
                    >
                      <span>Next</span>
                      <CaretRight size={14} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick Pillar Strategy Card */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
            <h4 className="text-xs font-semibold text-zinc-300">
              Content Pillar: {topicPillar}
            </h4>
            <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">
              Optimized for high-signal engineering audience. Carousel PDFs generate up to 3.8x higher engagement and bookmark rates than plain text links.
            </p>
          </div>
        </div>
      </div>

      {/* Scheduling & Publication Bar */}
      <div
        data-testid="scheduling-bar"
        className="flex flex-col justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 sm:flex-row sm:items-center"
      >
        {/* Date and Time Picker */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar size={15} className="text-zinc-400" />
            <input
              type="date"
              data-testid="schedule-date-input"
              value={scheduledDate}
              onChange={(e) => setScheduledDate(e.target.value)}
              className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/50 focus:outline-hidden"
            />
          </div>
          <div className="flex items-center gap-2">
            <Clock size={15} className="text-zinc-400" />
            <input
              type="time"
              data-testid="schedule-time-input"
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 font-mono text-xs text-zinc-200 focus:border-emerald-500/50 focus:outline-hidden"
            />
          </div>
          <span className="font-mono text-[10px] text-zinc-500">UTC Timezone</span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            data-testid="save-draft-btn"
            onClick={handleSaveDraft}
            className="rounded-md border border-zinc-700/80 bg-zinc-800/80 px-4 py-2 text-xs font-semibold text-zinc-200 transition-colors hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100 active:translate-y-[1px]"
          >
            Save Draft
          </button>
          <button
            type="button"
            data-testid="schedule-post-btn"
            onClick={handleSchedulePost}
            className="flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-4 py-2 text-xs font-semibold text-emerald-300 transition-colors hover:border-emerald-500/60 hover:bg-emerald-500/25 active:translate-y-[1px]"
          >
            <Clock size={14} weight="bold" className="text-emerald-400" />
            <span>Schedule Post</span>
          </button>
        </div>
      </div>
    </div>
  );
};
