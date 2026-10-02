import React, { useState, useMemo, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import { ScheduledPost, MediaAttachment } from "../types";
import {
  PencilSimple,
  Calendar,
  CheckCircle,
  Trash,
  Quotes,
} from "../components/icons";
import { VoiceDictationButton } from "../components/VoiceDictationButton";
import {
  HookArchetype,
  TOPIC_PILLARS,
} from "../components/composer/types";
import { HookStudio } from "../components/composer/HookStudio";
import { CutoffInspector } from "../components/composer/CutoffInspector";
import { MediaStudio } from "../components/composer/MediaStudio";
import { PillarBenchmarkCard } from "../components/composer/PillarBenchmarkCard";
import { ScheduleDispatcher } from "../components/composer/ScheduleDispatcher";

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
  const [activeTone, setActiveTone] = useState<string>("High-Signal Engineering");

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

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
    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const fileUrl =
      typeof window !== "undefined" &&
      window.URL &&
      typeof window.URL.createObjectURL === "function"
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
    setFeedbackMessage(
      `Attached ${isPdf ? "PDF document" : "image"}: ${file.name}`
    );
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
      scheduled_time: new Date(
        `${scheduledDate}T${scheduledTime}:00Z`
      ).toISOString(),
      status: "scheduled",
      media: mediaList,
      topic_pillar: topicPillar,
      created_at: activePostForEditing?.created_at || new Date().toISOString(),
      approved_at: new Date().toISOString(),
    };

    saveScheduledPost(post);
    setFeedbackMessage("Post scheduled successfully.");
    setTimeout(() => {
      setFeedbackMessage(null);
      setActivePostForEditing(null);
      setCurrentTab("calendar");
    }, 1200);
  };

  // Formatting helpers matching Stitch
  const handleFormatText = (type: "bold" | "italic" | "list" | "code" | "tag") => {
    if (type === "bold") {
      setPostText((prev) => (prev ? `${prev} **bold takeaway**` : "**bold takeaway**"));
    } else if (type === "italic") {
      setPostText((prev) => (prev ? `${prev} *italic emphasis*` : "*italic emphasis*"));
    } else if (type === "list") {
      setPostText((prev) => (prev ? `${prev}\n- Key insight 1\n- Key insight 2` : "- Key insight 1\n- Key insight 2"));
    } else if (type === "code") {
      setPostText((prev) => (prev ? `${prev}\n\`\`\`bash\nnpx create-hitl-agent@latest\n\`\`\`` : "```bash\nnpx create-hitl-agent@latest\n```"));
    } else if (type === "tag") {
      setPostText((prev) => (prev ? `${prev}\n\n#AgentArchitecture #AIEngineering #HITL` : "#AgentArchitecture #AIEngineering #HITL"));
    }
  };

  // Clear / Discard handler
  const handleDiscard = () => {
    setActivePostForEditing(null);
    setHeadline("");
    setPostText("");
    setMediaList([]);
    setAppliedHookName(null);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Things 3 / Apple Mail Studio Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-surface-container-high">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-surface-container-highest flex items-center justify-center text-primary shadow-xs border border-surface-container-high">
            <PencilSimple size={20} weight="bold" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="font-headline-sm text-headline-sm text-on-surface tracking-tight font-semibold">
                Post Composer Studio
              </h1>
              <span className="font-code-sm text-[10px] px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant font-medium">
                v1.2 High-Signal
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Structured technical composition with AI hook archetypes &amp; cutoff preview
            </span>
          </div>
        </div>

        {/* Top Action Pills: Discard, Open Calendar, New Blank Post */}
        <div className="flex items-center gap-2">
          {(activePostForEditing || headline || postText) && (
            <button
              type="button"
              onClick={handleDiscard}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-surface-container-high bg-surface-container-lowest hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors font-body-strong text-body-strong shadow-2xs"
            >
              <Trash size={14} />
              <span>{activePostForEditing ? "New Blank Post" : "Discard"}</span>
            </button>
          )}

          <button
            type="button"
            data-testid="view-calendar-quick-btn"
            onClick={() => setCurrentTab("calendar")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors font-body-strong text-body-strong shadow-2xs border border-surface-container-high"
          >
            <Calendar size={15} className="text-on-surface-variant" />
            <span>Open Calendar</span>
          </button>
        </div>
      </div>

      {/* Feedback Toast Notification */}
      {feedbackMessage && (
        <div
          data-testid="composer-feedback"
          className="flex items-center justify-between rounded-xl border border-tertiary/30 bg-tertiary-container/15 px-4 py-2.5 text-xs text-on-surface shadow-xs transition-all animate-fadeIn"
        >
          <div className="flex items-center gap-2">
            <CheckCircle size={16} weight="fill" className="text-tertiary" />
            <span className="font-medium">{feedbackMessage}</span>
          </div>
          <span className="font-code-sm text-[10px] text-tertiary font-semibold">
            Status Updated
          </span>
        </div>
      )}

      {/* Two-Pane Studio Workspace Layout */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* LEFT / MAIN PANE: Composition & Analysis Canvas (flex-1) */}
        <div className="flex-1 flex flex-col gap-5 min-w-0">
          {/* 1. Topic Pillar & Working Headline Input Card */}
          <div className="p-4 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="font-label-sm text-label-sm uppercase tracking-wider font-semibold text-outline">
                Post Configuration
              </span>
              <span className="font-code-sm text-code-sm text-on-surface-variant">
                Pillar ID: #{topicPillar.toLowerCase().replace(/\s+/g, "-")}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
              <div className="md:col-span-8 flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high/60 focus-within:border-primary/60 transition-colors">
                <input
                  id="headline-input"
                  data-testid="post-headline-input"
                  type="text"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder="Catchy post title or working concept..."
                  className="w-full bg-transparent border-0 outline-hidden font-body-strong text-body-strong text-on-surface placeholder:text-on-surface-variant/60 font-medium"
                />
              </div>
              <div className="md:col-span-4 relative flex items-center px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high/60 focus-within:border-primary/60 transition-colors">
                <select
                  data-testid="topic-pillar-select"
                  value={topicPillar}
                  onChange={(e) => setTopicPillar(e.target.value)}
                  className="w-full bg-transparent border-0 outline-hidden font-body-strong text-body-strong text-on-surface appearance-none cursor-pointer pr-5"
                >
                  {TOPIC_PILLARS.map((p) => (
                    <option key={p} value={p} className="bg-surface text-on-surface">
                      Topic: {p}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-3 text-on-surface-variant">
                  ▼
                </div>
              </div>
            </div>
          </div>

          {/* 2. AI Hook Studio Pill Bar */}
          <HookStudio
            appliedHookName={appliedHookName}
            onApplyHook={handleApplyHook}
          />

          {/* 3. Post Text Editor Canvas */}
          <div className="p-5 rounded-2xl bg-surface-container-lowest border border-surface-container-high/70 shadow-xs flex flex-col gap-3 focus-within:shadow-md transition-shadow">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-2 border-b border-surface-container-high/60 gap-2">
              <div className="flex items-center gap-2">
                <Quotes size={18} className="text-primary" />
                <span className="font-headline-sm text-headline-sm text-on-surface">
                  Post Text Editor
                </span>
                <div className="mx-1 h-3.5 w-px bg-surface-container-high" />
                <VoiceDictationButton
                  onTranscript={(text) => {
                    setPostText((prev) => (prev ? `${prev} ${text}` : text));
                  }}
                />
              </div>

              {/* Real-time Character, Word & Reading Time Badges */}
              <div className="flex items-center gap-2.5 font-code-sm text-code-sm text-on-surface-variant">
                <span data-testid="char-counter" className="text-on-surface font-semibold">
                  {charCount} / 3000 chars
                </span>
                <span>·</span>
                <span data-testid="word-counter">{wordCount} words</span>
                <span>·</span>
                <span data-testid="reading-time">{readingTimeMin}</span>
              </div>
            </div>

            {/* Writing Textarea */}
            <textarea
              ref={textareaRef}
              id="post-textarea"
              data-testid="post-content-editor"
              value={postText}
              onChange={(e) => setPostText(e.target.value)}
              rows={11}
              placeholder="Write your LinkedIn post here... Focus on technical depth, clear takeaways, and concrete metrics."
              className="w-full resize-y bg-transparent border-0 outline-hidden font-body-lg text-body-lg text-on-surface placeholder:text-on-surface-variant/60 leading-relaxed min-h-[220px]"
            />

            {/* High-Signal Formatting Bar & Tone Selector */}
            <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-surface-container-high/60">
              <div className="flex items-center gap-1 text-on-surface-variant">
                <button
                  type="button"
                  onClick={() => handleFormatText("bold")}
                  title="Bold (**text**)"
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface transition-colors font-bold text-xs"
                >
                  B
                </button>
                <button
                  type="button"
                  onClick={() => handleFormatText("italic")}
                  title="Italic (*text*)"
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface transition-colors italic text-xs"
                >
                  I
                </button>
                <button
                  type="button"
                  onClick={() => handleFormatText("list")}
                  title="Bullet List (- item)"
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface transition-colors text-xs font-mono"
                >
                  •-
                </button>
                <button
                  type="button"
                  onClick={() => handleFormatText("code")}
                  title="Code Block"
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface transition-colors text-xs font-mono"
                >
                  &lt;/&gt;
                </button>
                <button
                  type="button"
                  onClick={() => handleFormatText("tag")}
                  title="Hashtags"
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-container hover:text-on-surface transition-colors text-xs font-bold"
                >
                  #
                </button>
              </div>

              {/* Tone Quick-Buttons */}
              <div className="flex items-center gap-1 p-0.5 rounded-lg bg-surface-container-low text-xs">
                {["High-Signal Engineering", "Executive Brief", "Pragmatic Teardown"].map(
                  (tone) => (
                    <button
                      key={tone}
                      type="button"
                      onClick={() => setActiveTone(tone)}
                      className={`px-2.5 py-1 rounded-md text-label-md font-medium transition-colors ${
                        activeTone === tone
                          ? "bg-surface-container-lowest text-on-surface shadow-2xs font-semibold"
                          : "text-on-surface-variant hover:text-on-surface"
                      }`}
                    >
                      {tone}
                    </button>
                  )
                )}
              </div>
            </div>
          </div>

          {/* 4. Above-the-Fold 140-Character Mobile Cutoff Inspector */}
          <CutoffInspector postText={postText} />
        </div>

        {/* RIGHT PANE (390px): Media Studio, Pillar Benchmark & Dispatch */}
        <div className="w-full lg:w-[390px] shrink-0 flex flex-col gap-5">
          {/* Media Studio */}
          <MediaStudio
            mediaList={mediaList}
            currentSlideIndex={currentSlideIndex}
            setCurrentSlideIndex={setCurrentSlideIndex}
            onFileUpload={handleFileUpload}
            onRemoveMedia={handleRemoveMedia}
          />

          {/* Content Pillar & Reach Benchmark */}
          <PillarBenchmarkCard topicPillar={topicPillar} />

          {/* Schedule Dispatcher */}
          <ScheduleDispatcher
            scheduledDate={scheduledDate}
            setScheduledDate={setScheduledDate}
            scheduledTime={scheduledTime}
            setScheduledTime={setScheduledTime}
            onSaveDraft={handleSaveDraft}
            onSchedulePost={handleSchedulePost}
          />
        </div>
      </div>
    </div>
  );
};
