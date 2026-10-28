import { describe, it, expect, vi, beforeEach } from "vitest";
import worker, { Env, handleScheduledPostsCron } from "../src/index";

describe("Scheduled Posts Cron Handler", () => {
  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "my-secret-token-123",
    TELEGRAM_BOT_TOKEN: "123456:TEST_TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "987654321",
    GITHUB_DISPATCH_PAT: "ghp_mockpat1234567890",
    GITHUB_REPO_OWNER: "test-owner",
    GITHUB_REPO_NAME: "test-repo",
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

  it("handles missing KV namespace gracefully", async () => {
    const res = await handleScheduledPostsCron(mockEnv);
    expect(res.checked).toBe(0);
    expect(res.dispatched).toBe(0);
    expect(res.errors).toContain("No KV binding");
  });

  it("handles empty scheduled_posts key gracefully", async () => {
    const { kv } = createMockKv();
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
    const res = await handleScheduledPostsCron(env);
    expect(res.checked).toBe(0);
    expect(res.dispatched).toBe(0);
    expect(res.errors).toHaveLength(0);
  });

  it("skips draft and future scheduled posts", async () => {
    const now = new Date("2026-10-04T12:00:00Z");
    const futureTime = new Date("2026-10-04T14:00:00Z").toISOString();
    const { kv } = createMockKv({
      scheduled_posts: JSON.stringify([
        { id: "draft_1", post_text: "Draft text", status: "draft" },
        { id: "future_1", post_text: "Future text", status: "scheduled", scheduled_time: futureTime },
      ]),
    });
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const res = await handleScheduledPostsCron(env, now);
    expect(res.checked).toBe(2);
    expect(res.dispatched).toBe(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("dispatches due scheduled posts and records dispatched_at timestamp", async () => {
    const now = new Date("2026-10-04T12:00:00Z");
    const dueTime = new Date("2026-10-04T11:45:00Z").toISOString();
    const { kv, store } = createMockKv({
      scheduled_posts: JSON.stringify([
        { id: "post_due_1", post_text: "Ready to publish!", status: "scheduled", scheduled_time: dueTime },
      ]),
    });
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    const res = await handleScheduledPostsCron(env, now);
    expect(res.checked).toBe(1);
    expect(res.dispatched).toBe(1);
    expect(res.errors).toHaveLength(0);

    // Verify fetch call to GitHub
    expect(fetchSpy).toHaveBeenCalledWith(
      `https://api.github.com/repos/test-owner/test-repo/dispatches`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${mockEnv.GITHUB_DISPATCH_PAT}`,
        }),
        body: JSON.stringify({
          event_type: "telegram-approval-action",
          client_payload: {
            action: "approve",
            item_id: "post_due_1",
          },
        }),
      })
    );

    // Verify updated post in KV
    const updatedList = JSON.parse(store.get("scheduled_posts")!);
    expect(updatedList[0].dispatched_at).toBe(now.toISOString());
    const individual = JSON.parse(store.get("scheduled:post_due_1")!);
    expect(individual.dispatched_at).toBe(now.toISOString());
  });

  it("skips posts already dispatched within the last hour", async () => {
    const now = new Date("2026-10-04T12:00:00Z");
    const dueTime = new Date("2026-10-04T11:00:00Z").toISOString();
    const recentDispatch = new Date("2026-10-04T11:45:00Z").toISOString(); // 15 mins ago
    const { kv } = createMockKv({
      scheduled_posts: JSON.stringify([
        {
          id: "post_recent",
          post_text: "Already dispatched",
          status: "scheduled",
          scheduled_time: dueTime,
          dispatched_at: recentDispatch,
        },
      ]),
    });
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const res = await handleScheduledPostsCron(env, now);
    expect(res.checked).toBe(1);
    expect(res.dispatched).toBe(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("handles GitHub dispatch API errors gracefully", async () => {
    const now = new Date("2026-10-04T12:00:00Z");
    const dueTime = new Date("2026-10-04T11:45:00Z").toISOString();
    const { kv } = createMockKv({
      scheduled_posts: JSON.stringify([
        { id: "post_err_1", post_text: "Text", status: "scheduled", scheduled_time: dueTime },
      ]),
    });
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ message: "Bad credentials" }), { status: 401 })
    );

    const res = await handleScheduledPostsCron(env, now);
    expect(res.checked).toBe(1);
    expect(res.dispatched).toBe(0);
    expect(res.errors).toHaveLength(1);
    expect(res.errors[0]).toContain("401");
  });

  it("triggers scheduled method on default worker export", async () => {
    const { kv } = createMockKv();
    const env: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
    const ctx = {
      waitUntil: vi.fn(),
      passThroughOnException: vi.fn(),
    };

    await worker.scheduled({}, env, ctx as any);
    expect(ctx.waitUntil).toHaveBeenCalledTimes(1);
  });
});
