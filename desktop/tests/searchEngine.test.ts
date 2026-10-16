import { describe, it, expect, vi } from "vitest";
import {
  tokenizeQuery,
  scoreDocument,
  searchAndRank,
} from "../src/services/search/searchScorer";
import { buildSearchIndex } from "../src/services/search/searchIndexBuilder";
import {
  VIEW_SEARCH_DOCUMENTS,
} from "../src/services/search/searchRegistry";
import { SearchDocument } from "../src/services/search/types";
import { Sparkle } from "../src/components/icons";

describe("Search Scorer & Ranking Algorithm", () => {
  const dummyDoc: SearchDocument = {
    id: "test-doc-1",
    title: "NVIDIA NIM Intelligence",
    subtitle: "Configure primary and fallback LLM models",
    category: "Setting",
    icon: Sparkle,
    keywords: ["nim", "nemotron", "llama", "llm provider"],
    target: { tab: "settings", sectionId: "setting-nim-intelligence" },
  };

  it("tokenizes search query into clean lowercase terms", () => {
    expect(tokenizeQuery("  NVIDIA   NIM  ")).toEqual(["nvidia", "nim"]);
    expect(tokenizeQuery("")).toEqual([]);
    expect(tokenizeQuery("   ")).toEqual([]);
  });

  it("scores exact title matches with the highest score", () => {
    const exact = scoreDocument(dummyDoc, "NVIDIA NIM Intelligence", ["nvidia", "nim", "intelligence"]);
    const partial = scoreDocument(dummyDoc, "NVIDIA", ["nvidia"]);

    expect(exact).not.toBeNull();
    expect(partial).not.toBeNull();
    expect(exact!.score).toBeGreaterThan(partial!.score);
  });

  it("requires all query tokens to match somewhere in document", () => {
    const mismatch = scoreDocument(dummyDoc, "NVIDIA Quantum", ["nvidia", "quantum"]);
    expect(mismatch).toBeNull();
  });

  it("matches keywords and subtitles effectively", () => {
    const keywordMatch = scoreDocument(dummyDoc, "nemotron", ["nemotron"]);
    expect(keywordMatch).not.toBeNull();
    expect(keywordMatch!.score).toBeGreaterThan(0);

    const subtitleMatch = scoreDocument(dummyDoc, "fallback models", ["fallback", "models"]);
    expect(subtitleMatch).not.toBeNull();
    expect(subtitleMatch!.score).toBeGreaterThan(0);
  });

  it("ranks exact title match higher than subtitle match", () => {
    const titleDoc: SearchDocument = {
      id: "title-match",
      title: "Playwright Headless",
      subtitle: "General browser configuration",
      category: "Setting",
      icon: Sparkle,
      keywords: [],
      target: { tab: "settings" },
    };

    const subtitleDoc: SearchDocument = {
      id: "subtitle-match",
      title: "System Execution",
      subtitle: "Run Playwright Headless in background",
      category: "Setting",
      icon: Sparkle,
      keywords: [],
      target: { tab: "settings" },
    };

    const results = searchAndRank([subtitleDoc, titleDoc], "Playwright Headless");
    expect(results[0].id).toBe("title-match");
  });

  it("returns documents up to limit when query is empty", () => {
    const results = searchAndRank(VIEW_SEARCH_DOCUMENTS, "", 5);
    expect(results.length).toBe(5);
    expect(results[0].category).toBe("Navigation");
  });
});

describe("Search Index Builder", () => {
  it("includes all static views and settings cards by default", () => {
    const index = buildSearchIndex({});
    const titles = index.map((d) => d.title);

    expect(titles).toContain("Approval Queue");
    expect(titles).toContain("LinkedIn Vault");
    expect(titles).toContain("Settings: NVIDIA NIM Intelligence");
    expect(titles).toContain("Settings: Safety Guardrails & Quotas");
    expect(titles).toContain("Settings: Cloudflare Edge Relay");
  });

  it("indexes pending approval queue items with target item IDs", () => {
    const mockPending = [
      {
        item_id: "act-101",
        author_name: "Satya Nadella",
        author_headline: "Chairman & CEO at Microsoft",
        draft_text: "Autonomous verification guardrails are critical for enterprise scale.",
        action_type: "approve_comment",
        confidence: 0.94,
      },
    ];

    const index = buildSearchIndex({ pendingItems: mockPending });
    const match = index.find((d) => d.id === "queue-act-101");

    expect(match).toBeDefined();
    expect(match!.title).toContain("Satya Nadella");
    expect(match!.subtitle).toContain("Autonomous verification guardrails");
    expect(match!.category).toBe("Queue");
    expect(match!.target).toEqual({ tab: "queue", itemId: "act-101" });
    expect(match!.badge).toBe("94% Match");
  });

  it("indexes outreach connection candidates with target item IDs", () => {
    const mockOutreach = [
      {
        id: "conn-202",
        profile_url: "https://linkedin.com/in/yann-lecun",
        target_name: "Yann LeCun",
        target_headline: "Chief AI Scientist at Meta",
        mutual_context: "Mutual interest in autonomous reasoning architectures",
        note_text: "Hi Yann, loved your recent keynote on World Models.",
        status: "pending" as const,
        created_at: new Date().toISOString(),
      },
    ];

    const index = buildSearchIndex({ connectionQueue: mockOutreach });
    const match = index.find((d) => d.id === "outreach-conn-202");

    expect(match).toBeDefined();
    expect(match!.title).toBe("Yann LeCun");
    expect(match!.subtitle).toContain("Hi Yann");
    expect(match!.category).toBe("Outreach");
    expect(match!.target).toEqual({ tab: "outreach", itemId: "conn-202" });
  });

  it("indexes scheduled posts and content roadmap", () => {
    const mockPosts = [
      {
        id: "post-303",
        headline: "Why Deterministic Agent Guardrails Prevent Catastrophic Loops",
        post_text: "In distributed agent systems, deterministic state machines must govern actions...",
        topic_pillar: "Agent Architecture",
        status: "scheduled" as const,
        media: [],
        created_at: new Date().toISOString(),
      },
    ];

    const index = buildSearchIndex({ scheduledPosts: mockPosts });
    const match = index.find((d) => d.id === "post-303");

    expect(match).toBeDefined();
    expect(match!.title).toContain("Deterministic Agent Guardrails");
    expect(match!.category).toBe("Post");
    expect(match!.target).toEqual({ tab: "calendar", itemId: "post-303" });
  });

  it("indexes quick actions with attached callbacks", () => {
    const triggerScoutMock = vi.fn();
    const togglePauseMock = vi.fn();

    const index = buildSearchIndex({
      onTriggerScout: triggerScoutMock,
      onTogglePause: togglePauseMock,
      isPaused: false,
    });

    const scoutAction = index.find((d) => d.id === "act-scout-now");
    expect(scoutAction).toBeDefined();
    expect(scoutAction!.title).toBe("Trigger Feed Scout Now");
    scoutAction!.action?.();
    expect(triggerScoutMock).toHaveBeenCalledTimes(1);

    const pauseAction = index.find((d) => d.id === "act-pause");
    expect(pauseAction).toBeDefined();
    expect(pauseAction!.title).toBe("Pause Agent Operations");
    pauseAction!.action?.();
    expect(togglePauseMock).toHaveBeenCalledTimes(1);
  });

  it("accurately finds and ranks target items through searchAndRank", () => {
    const mockPending = [
      {
        item_id: "act-satya",
        author_name: "Satya Nadella",
        draft_text: "Verification architectures for autonomous agents.",
      },
      {
        item_id: "act-sam",
        author_name: "Sam Altman",
        draft_text: "Scaling compute and frontier model intelligence.",
      },
    ];

    const index = buildSearchIndex({ pendingItems: mockPending });
    const satyaResults = searchAndRank(index, "Satya");

    expect(satyaResults.length).toBeGreaterThan(0);
    expect(satyaResults[0].id).toBe("queue-act-satya");
    expect(satyaResults[0].target.tab).toBe("queue");
    expect(satyaResults[0].target.itemId).toBe("act-satya");

    const nimResults = searchAndRank(index, "NIM Intelligence");
    expect(nimResults.length).toBeGreaterThan(0);
    expect(nimResults[0].id).toBe("setting-nim-intelligence");
    expect(nimResults[0].target.tab).toBe("settings");
    expect(nimResults[0].target.sectionId).toBe("setting-nim-intelligence");
  });
});
