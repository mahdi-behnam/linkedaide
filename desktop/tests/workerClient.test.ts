import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkerClient } from "../electron/api/workerClient";

describe("WorkerClient", () => {
  const baseUrl = "https://worker.example.workers.dev";
  const apiSecret = "super-secret-key-12345";
  let client: WorkerClient;

  beforeEach(() => {
    client = new WorkerClient({ baseUrl, apiSecret });
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("Configuration & Headers", () => {
    it("throws error when baseUrl is missing", async () => {
      const emptyClient = new WorkerClient({ baseUrl: "", apiSecret: "secret" });
      await expect(emptyClient.fetchState()).rejects.toThrow(
        "Worker URL is not configured"
      );
    });

    it("throws error when apiSecret is missing", async () => {
      const emptyClient = new WorkerClient({ baseUrl: "https://example.com", apiSecret: "" });
      await expect(emptyClient.fetchState()).rejects.toThrow(
        "Desktop API Secret is not configured"
      );
    });

    it("updates configuration dynamically with updateConfig", async () => {
      const c = new WorkerClient({ baseUrl: "https://initial.com", apiSecret: "init" });
      c.updateConfig({ baseUrl: "https://updated.com/", apiSecret: "new-secret" });

      const cfg = c.getConfig();
      expect(cfg.baseUrl).toBe("https://updated.com");
      expect(cfg.apiSecret).toBe("new-secret");
    });
  });

  describe("fetchState", () => {
    it("sends GET to /api/state with Bearer authorization and returns AgentState", async () => {
      const mockState = {
        pending_actions: [
          {
            item_id: "item-1",
            action_type: "approve_comment",
            created_at: "2026-09-29T12:00:00Z",
            draft_text: "Great insights on AI agents!",
          },
        ],
        daily_counters: {
          date: "2026-09-29",
          comments_executed: 2,
          posts_executed: 0,
          suggestions_sent: 5,
        },
        history: [],
        incident: null,
        paused: false,
        seen_posts_count: 42,
      };

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(mockState),
      });
      vi.stubGlobal("fetch", fetchMock);

      const state = await client.fetchState();

      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/state",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Authorization: `Bearer ${apiSecret}`,
            "Content-Type": "application/json",
          }),
        })
      );

      expect(state.pending_actions).toHaveLength(1);
      expect(state.pending_actions[0].item_id).toBe("item-1");
      expect(state.pendingActions).toEqual(state.pending_actions);
      expect(state.daily_counters.comments_executed).toBe(2);
      expect(state.paused).toBe(false);
      expect(state.seen_posts_count).toBe(42);
    });
  });

  describe("executeAction", () => {
    it("sends POST to /api/action with approve action and item_id", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ success: true, message: "Action dispatched" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.executeAction("approve", "act-123");

      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/action",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            action: "approve",
            itemId: "act-123",
            item_id: "act-123",
          }),
        })
      );

      expect(result.success).toBe(true);
      expect(result.action).toBe("approve");
      expect(result.itemId).toBe("act-123");
    });

    it("returns failure result when API responds with error", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ error: "KV store write failed" }),
        text: async () => JSON.stringify({ error: "KV store write failed" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.executeAction("reject", "act-456");

      expect(result.success).toBe(false);
      expect(result.error).toContain("KV store write failed");
      expect(result.itemId).toBe("act-456");
    });
  });

  describe("triggerScout", () => {
    it("sends POST to /api/scout and returns true on success", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const success = await client.triggerScout();
      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/scout",
        expect.objectContaining({ method: "POST" })
      );
      expect(success).toBe(true);
    });
  });

  describe("togglePause", () => {
    it("sends POST to /api/pause with paused state", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true, paused: true }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.togglePause(true);
      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/pause",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ paused: true }),
        })
      );
      expect(result).toBe(true);
    });
  });

  describe("clearIncident", () => {
    it("sends POST to /api/incident/clear", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.clearIncident();
      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/incident/clear",
        expect.objectContaining({ method: "POST" })
      );
      expect(result).toBe(true);
    });
  });

  describe("rewriteDraft", () => {
    it("sends draft and tone to /api/rewrite and returns rewritten draft", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ draft: "This is a polished and insightful perspective." }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.rewriteDraft("Good point", "thought_leader");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/rewrite",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            draftText: "Good point",
            draft_text: "Good point",
            tone: "thought_leader",
          }),
        })
      );
      expect(result).toBe("This is a polished and insightful perspective.");
    });
  });

  describe("saveSession", () => {
    it("sends session data to /api/session", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await client.saveSession("encrypted-session-token");
      expect(fetchMock).toHaveBeenCalledWith(
        "https://worker.example.workers.dev/api/session",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            sessionData: "encrypted-session-token",
            session_data: "encrypted-session-token",
          }),
        })
      );
      expect(result).toBe(true);
    });
  });
});
