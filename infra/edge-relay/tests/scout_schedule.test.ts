import { describe, it, expect, vi, beforeEach } from "vitest";
import worker, {
  Env,
  handleScoutSchedule,
  handleScoutScheduleCron,
  defaultScoutWindows,
} from "../src/index";

describe("Scout Schedule Handlers & Edge Cron", () => {
  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "my-secret-token-123",
    TELEGRAM_BOT_TOKEN: "123456:TEST_TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "987654321",
    GITHUB_DISPATCH_PAT: "ghp_mockpat1234567890",
    GITHUB_REPO_OWNER: "test-owner",
    GITHUB_REPO_NAME: "test-repo",
    DESKTOP_API_SECRET: "test-secret",
  };

  const createMockKv = (initialData: Record<string, string> = {}) => {
    const kvStore = new Map<string, string>(Object.entries(initialData));
    return {
      store: kvStore,
      kv: {
        get: vi.fn(async (key: string) => kvStore.get(key) ?? null),
        put: vi.fn(async (key: string, val: string) => {
          kvStore.set(key, val);
        }),
        delete: vi.fn(async (key: string) => {
          kvStore.delete(key);
        }),
        list: vi.fn(async (options?: { prefix?: string }) => {
          const prefix = options?.prefix || "";
          const keys = Array.from(kvStore.keys())
            .filter((k) => k.startsWith(prefix))
            .map((name) => ({ name }));
          return { keys, list_complete: true };
        }),
      },
    };
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("REST API /api/scout-schedule", () => {
    it("returns 500 when KV namespace is missing", async () => {
      const req = new Request("https://example.com/api/scout-schedule", {
        method: "GET",
      });
      const res = await handleScoutSchedule(req, mockEnv);
      expect(res.status).toBe(500);
      const data = await res.json();
      expect(data).toHaveProperty("error", "KV namespace not configured");
    });

    it("GET returns default scout windows when KV has no custom schedule", async () => {
      const { kv } = createMockKv();
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = new Request("https://example.com/api/scout-schedule", {
        method: "GET",
      });
      const res = await handleScoutSchedule(req, env);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.schedule).toEqual(defaultScoutWindows);
    });

    it("POST updates scout schedule and persists to KV", async () => {
      const { kv } = createMockKv();
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const newWindows = [
        {
          id: "custom-run-1",
          title: "Early Bird Scout",
          start_time: "07:00",
          end_time: "08:00",
          days: ["Mon", "Wed", "Fri"],
          status: "active",
          topic_filter: "AI Startups",
        },
      ];

      const postReq = new Request("https://example.com/api/scout-schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schedule: newWindows }),
      });

      const postRes = await handleScoutSchedule(postReq, env);
      expect(postRes.status).toBe(200);
      const postData = (await postRes.json()) as any;
      expect(postData.success).toBe(true);
      expect(postData.schedule).toHaveLength(1);
      expect(postData.schedule[0].title).toBe("Early Bird Scout");

      // Verify GET returns newly saved schedule
      const getReq = new Request("https://example.com/api/scout-schedule", {
        method: "GET",
      });
      const getRes = await handleScoutSchedule(getReq, env);
      const getData = (await getRes.json()) as any;
      expect(getData.schedule).toHaveLength(1);
      expect(getData.schedule[0].id).toBe("custom-run-1");
    });

    it("POST rejects invalid non-array payload", async () => {
      const { kv } = createMockKv();
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = new Request("https://example.com/api/scout-schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schedule: "invalid" }),
      });
      const res = await handleScoutSchedule(req, env);
      expect(res.status).toBe(400);
      const data = await res.json();
      expect(data).toHaveProperty("error");
    });

    it("GET /api/state includes scout_schedule", async () => {
      const customWindows = [
        {
          id: "win-test",
          title: "Test Window",
          start_time: "10:00",
          end_time: "11:00",
          days: ["Tue"],
          status: "active",
          topic_filter: "Robotics",
        },
      ];
      const { kv } = createMockKv({
        scout_schedule: JSON.stringify(customWindows),
      });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const req = new Request("https://example.com/api/state", {
        method: "GET",
        headers: {
          Authorization: "Bearer test-secret",
        },
      });
      const res = await worker.fetch(req, env, {} as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.state).toHaveProperty("scout_schedule");
      expect(data.state.scout_schedule[0].title).toBe("Test Window");
    });
  });

  describe("Edge Cron handleScoutScheduleCron", () => {
    it("handles missing KV namespace gracefully", async () => {
      const res = await handleScoutScheduleCron(mockEnv);
      expect(res.checked).toBe(0);
      expect(res.dispatched).toBe(0);
      expect(res.errors).toContain("No KV binding");
    });

    it("skips execution when agent is paused", async () => {
      const { kv } = createMockKv({ paused: "true" });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const res = await handleScoutScheduleCron(env);
      expect(res.checked).toBe(0);
      expect(res.dispatched).toBe(0);
      expect(res.errors).toHaveLength(0);
    });

    it("skips execution when circuit breaker incident is active", async () => {
      const { kv } = createMockKv({ incident: JSON.stringify({ reason: "Bot challenge" }) });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const res = await handleScoutScheduleCron(env);
      expect(res.checked).toBe(0);
      expect(res.dispatched).toBe(0);
      expect(res.errors).toContain("Circuit breaker tripped");
    });

    it("skips inactive windows or windows for a different day", async () => {
      // 2026-10-05 is a Monday
      const testDate = new Date("2026-10-05T08:05:00Z");
      const windows = [
        {
          id: "win-paused",
          title: "Paused Window",
          start_time: "08:00",
          end_time: "09:00",
          days: ["Mon"],
          status: "paused",
          topic_filter: "AI",
        },
        {
          id: "win-wrong-day",
          title: "Sunday Window",
          start_time: "08:00",
          end_time: "09:00",
          days: ["Sun"],
          status: "active",
          topic_filter: "AI",
        },
      ];
      const { kv } = createMockKv({ scout_schedule: JSON.stringify(windows) });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const res = await handleScoutScheduleCron(env, testDate);
      expect(res.checked).toBe(2);
      expect(res.dispatched).toBe(0);
      expect(res.errors).toHaveLength(0);
    });

    it("skips windows that are not due", async () => {
      // Current time 08:05 UTC, window starts at 14:00 UTC
      const testDate = new Date("2026-10-05T08:05:00Z");
      const windows = [
        {
          id: "win-afternoon",
          title: "Afternoon Window",
          start_time: "14:00",
          end_time: "15:00",
          days: ["Mon"],
          status: "active",
          topic_filter: "AI",
        },
      ];
      const { kv } = createMockKv({ scout_schedule: JSON.stringify(windows) });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const res = await handleScoutScheduleCron(env, testDate);
      expect(res.checked).toBe(1);
      expect(res.dispatched).toBe(0);
    });

    it("skips windows already dispatched recently", async () => {
      // Current time 08:05 UTC, window dispatched at 08:00 UTC
      const testDate = new Date("2026-10-05T08:05:00Z");
      const windows = [
        {
          id: "win-morning",
          title: "Morning Window",
          start_time: "08:00",
          end_time: "09:00",
          days: ["Mon"],
          status: "active",
          topic_filter: "AI",
          last_dispatched_at: "2026-10-05T08:01:00Z",
        },
      ];
      const { kv } = createMockKv({ scout_schedule: JSON.stringify(windows) });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const res = await handleScoutScheduleCron(env, testDate);
      expect(res.checked).toBe(1);
      expect(res.dispatched).toBe(0);
    });

    it("dispatches due window via GitHub Actions workflow dispatch", async () => {
      // Current time Monday 08:05 UTC, window starts at 08:00 UTC
      const testDate = new Date("2026-10-05T08:05:00Z");
      const windows = [
        {
          id: "win-due",
          title: "Due Morning Window",
          start_time: "08:00",
          end_time: "09:30",
          days: ["Mon"],
          status: "active",
          topic_filter: "AI Systems",
        },
      ];
      const { kv, store } = createMockKv({ scout_schedule: JSON.stringify(windows) });
      const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      // Mock global fetch for GitHub Actions dispatch
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        text: async () => "",
      });
      globalThis.fetch = fetchMock;

      const res = await handleScoutScheduleCron(env, testDate);
      expect(res.checked).toBe(1);
      expect(res.dispatched).toBe(1);
      expect(res.errors).toHaveLength(0);

      // Verify GitHub dispatch URL called
      expect(fetchMock).toHaveBeenCalledWith(
        "https://api.github.com/repos/test-owner/test-repo/actions/workflows/scout.yml/dispatches",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer ghp_mockpat1234567890",
          }),
        })
      );

      // Verify KV was updated with last_dispatched_at
      const updatedKvSchedule = JSON.parse(store.get("scout_schedule") || "[]");
      expect(updatedKvSchedule[0].last_dispatched_at).toBe(testDate.toISOString());
    });
  });
});
