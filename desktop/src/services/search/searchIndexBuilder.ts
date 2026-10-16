import {
  Inbox,
  UserPlus,
  PencilSimple,
  Calendar,
  ClockCounterClockwise,
  Stethoscope,
  Play,
  Pause,
  Sun,
  Moon,
  ArrowClockwise,
  WarningCircle,
  Sparkle,
} from "../../components/icons";
import {
  ScheduledPost,
  AutomatedCommentWindow,
  ConnectionRequestAction,
  AuditEntry,
  DoctorCheck,
} from "../../types";
import { SearchDocument } from "./types";
import {
  VIEW_SEARCH_DOCUMENTS,
  SETTINGS_SECTION_DOCUMENTS,
  SUBSYSTEM_SECTION_DOCUMENTS,
} from "./searchRegistry";

export interface BuildSearchIndexOptions {
  pendingItems?: any[];
  connectionQueue?: ConnectionRequestAction[];
  scheduledPosts?: ScheduledPost[];
  commentWindows?: AutomatedCommentWindow[];
  auditEntries?: AuditEntry[];
  doctorChecks?: DoctorCheck[];
  isPaused?: boolean;
  onTogglePause?: () => void;
  onToggleTheme?: () => void;
  currentTheme?: string;
  onTriggerScout?: () => void;
  onRunDoctor?: () => void;
  onClearIncident?: () => void;
  hasIncident?: boolean;
  onCreateNewPost?: () => void;
}

/**
 * Builds the full searchable document collection from current application context.
 */
export function buildSearchIndex(options: BuildSearchIndexOptions): SearchDocument[] {
  const documents: SearchDocument[] = [
    ...VIEW_SEARCH_DOCUMENTS,
    ...SETTINGS_SECTION_DOCUMENTS,
    ...SUBSYSTEM_SECTION_DOCUMENTS,
  ];

  // 1. Pending Approval Queue Items
  if (options.pendingItems && options.pendingItems.length > 0) {
    for (const item of options.pendingItems) {
      const rawId = item.item_id || item.id || `pending-${Math.random()}`;
      const docId = rawId.startsWith("queue-") ? rawId : `queue-${rawId}`;
      const author = item.author || item.author_name || "LinkedIn Member";
      const headline = item.headline || item.author_headline || "";
      const draft = item.draft_text || item.draftText || "";
      const excerpt = item.post_excerpt || item.postExcerpt || "";
      const actionType = (item.action_type || item.actionType || "comment").replace("approve_", "");
      const confidence = item.confidence ? Math.round(item.confidence * 100) : 85;

      const subtitleSnippet = draft
        ? `“${draft.slice(0, 65).trim()}${draft.length > 65 ? "..." : ""}”`
        : excerpt
        ? `Target: “${excerpt.slice(0, 65).trim()}...”`
        : headline || "Pending Review";

      documents.push({
        id: docId,
        title: `${author} (${actionType.toUpperCase()})`,
        subtitle: subtitleSnippet,
        category: "Queue",
        icon: Inbox,
        badge: `${confidence}% Match`,
        keywords: [
          author,
          headline,
          draft,
          excerpt,
          actionType,
          item.reasoning || "",
          item.topic || "",
          "pending approval",
          "triage",
        ].filter(Boolean),
        target: {
          tab: "queue",
          itemId: rawId,
        },
      });
    }
  }

  // 2. Outreach Connection Candidates
  if (options.connectionQueue && options.connectionQueue.length > 0) {
    for (const candidate of options.connectionQueue) {
      const docId = candidate.id.startsWith("outreach-") ? candidate.id : `outreach-${candidate.id}`;
      const note = candidate.note_text || "";
      const headline = candidate.target_headline || "Candidate";
      const subtitleSnippet = note
        ? `Note: “${note.slice(0, 60).trim()}${note.length > 60 ? "..." : ""}”`
        : headline;

      documents.push({
        id: docId,
        title: candidate.target_name,
        subtitle: subtitleSnippet,
        category: "Outreach",
        icon: UserPlus,
        badge: candidate.status === "pending" ? "Pending Invite" : candidate.status,
        keywords: [
          candidate.target_name,
          headline,
          candidate.mutual_context || "",
          note,
          "outreach",
          "connection",
          "invite",
          "lead",
        ].filter(Boolean),
        target: {
          tab: "outreach",
          itemId: candidate.id,
        },
      });
    }
  }

  // 3. Scheduled & Draft Posts
  if (options.scheduledPosts && options.scheduledPosts.length > 0) {
    for (const post of options.scheduledPosts) {
      const docId = post.id.startsWith("post-") ? post.id : `post-${post.id}`;
      const postText = post.post_text || "";
      const subtitleSnippet = postText
        ? `${post.topic_pillar || "Post"} • “${postText.slice(0, 60).trim()}${postText.length > 60 ? "..." : ""}”`
        : post.topic_pillar || "Post";

      documents.push({
        id: docId,
        title: post.headline || "Untitled Post",
        subtitle: subtitleSnippet,
        category: "Post",
        icon: Calendar,
        badge: post.status === "scheduled" ? "Scheduled" : post.status === "published" ? "Published" : "Draft",
        keywords: [
          post.headline,
          post.topic_pillar,
          postText,
          post.status,
          "scheduled post",
          "content calendar",
          "post draft",
        ].filter(Boolean),
        target: {
          tab: "calendar",
          itemId: post.id,
        },
      });
    }
  }

  // 4. Automated Scout Windows
  if (options.commentWindows && options.commentWindows.length > 0) {
    for (const win of options.commentWindows) {
      documents.push({
        id: `schedule-${win.id}`,
        title: win.title,
        subtitle: `${win.start_time} - ${win.end_time} (${win.days.join(", ")}) • ${win.topic_filter}`,
        category: "Schedule",
        icon: Calendar,
        badge: win.status.toUpperCase(),
        keywords: [
          win.title,
          win.topic_filter,
          ...win.days,
          "scout window",
          "schedule cadence",
          "automated comment window",
        ],
        target: {
          tab: "calendar",
          itemId: win.id,
          sectionId: "scout-schedule",
        },
      });
    }
  }

  // 5. Audit History Records
  if (options.auditEntries && options.auditEntries.length > 0) {
    for (const entry of options.auditEntries) {
      const author = entry.targetAuthor || "LinkedIn Member";
      const excerpt = entry.draftExcerpt || entry.error || "";
      const statusClean = entry.status.replace("_", " ").toUpperCase();

      documents.push({
        id: `history-${entry.id || entry.itemId}`,
        title: `History: ${author} (${entry.actionType})`,
        subtitle: `${statusClean} • “${excerpt.slice(0, 55).trim()}${excerpt.length > 55 ? "..." : ""}”`,
        category: "History",
        icon: ClockCounterClockwise,
        badge: statusClean,
        keywords: [
          author,
          entry.actionType,
          entry.status,
          excerpt,
          entry.itemId,
          "audit history",
          "executed outcome",
          "decision log",
        ].filter(Boolean),
        target: {
          tab: "history",
          itemId: entry.id || entry.itemId,
        },
      });
    }
  }

  // 6. Diagnostics Checks
  if (options.doctorChecks && options.doctorChecks.length > 0) {
    for (const check of options.doctorChecks) {
      documents.push({
        id: `doctor-${check.id}`,
        title: check.title,
        subtitle: `${check.category.toUpperCase()} • ${check.detail}`,
        category: "Diagnostic",
        icon: Stethoscope,
        badge: check.status.toUpperCase(),
        keywords: [
          check.title,
          check.category,
          check.detail,
          check.recommendation || "",
          "diagnostic check",
          "subsystem",
        ].filter(Boolean),
        target: {
          tab: "doctor",
          itemId: check.id,
          sectionId: "doctor-subsystems",
        },
      });
    }
  }

  // 7. Interactive Quick Actions & System Commands
  if (options.onTriggerScout) {
    documents.push({
      id: "act-scout-now",
      title: "Trigger Feed Scout Now",
      subtitle: "Execute immediate LinkedIn feed scrape and LLM triage in background",
      category: "Action",
      icon: ArrowClockwise,
      badge: "Command",
      keywords: ["trigger scout", "run scout", "feed scan", "scrape linkedin", "find posts"],
      target: { tab: "dashboard" },
      action: options.onTriggerScout,
    });
  }

  if (options.onRunDoctor) {
    documents.push({
      id: "act-doctor-run",
      title: "Run System Diagnostics Doctor",
      subtitle: "Execute full diagnostic verification of session, edge relay, and NIM models",
      category: "Action",
      icon: Stethoscope,
      badge: "Command",
      keywords: ["run doctor", "diagnostics", "health check", "verify system", "audit secrets"],
      target: { tab: "doctor" },
      action: options.onRunDoctor,
    });
  }

  if (options.onCreateNewPost) {
    documents.push({
      id: "act-new-post",
      title: "Create New Post Draft",
      subtitle: "Open Post Composer studio with a blank draft and hook suggestions",
      category: "Action",
      icon: PencilSimple,
      badge: "Command",
      keywords: ["new post", "create post", "compose", "draft post", "write"],
      target: { tab: "composer" },
      action: options.onCreateNewPost,
    });
  }

  if (options.onTogglePause) {
    documents.push({
      id: "act-pause",
      title: options.isPaused ? "Resume Agent Operations" : "Pause Agent Operations",
      subtitle: options.isPaused
        ? "Resume automated feed scouting and action dispatching"
        : "Temporarily suspend automated workflows and execution",
      category: "Action",
      icon: options.isPaused ? Play : Pause,
      badge: "Command",
      keywords: ["pause agent", "resume agent", "suspend", "standby", "unpause"],
      target: { tab: "dashboard" },
      action: options.onTogglePause,
    });
  }

  if (options.onToggleTheme) {
    const isDark = options.currentTheme === "dark";
    documents.push({
      id: "act-theme",
      title: isDark ? "Switch to Light Theme" : "Switch to Dark Theme",
      subtitle: `Currently using ${options.currentTheme || "light"} mode`,
      category: "Action",
      icon: isDark ? Sun : Moon,
      badge: "Command",
      keywords: ["theme", "light mode", "dark mode", "switch theme", "toggle theme"],
      target: { tab: "settings" },
      action: options.onToggleTheme,
    });
  }

  if (options.hasIncident && options.onClearIncident) {
    documents.push({
      id: "act-clear-incident",
      title: "Clear Circuit Breaker Incident",
      subtitle: "Reset tripped safety status and resume autonomous execution",
      category: "Action",
      icon: WarningCircle,
      badge: "Alert",
      keywords: ["clear incident", "circuit breaker", "reset safety", "resume after error"],
      target: { tab: "dashboard" },
      action: options.onClearIncident,
    });
  }

  return documents;
}
