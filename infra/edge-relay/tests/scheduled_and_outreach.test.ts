import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, { Env } from "../src/index";

describe("Scheduled Posts and Outreach Queue API", () => {
  const mockApiSecret = "super-secret-desktop-token-456";

  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "my-secret-token-123",
    TELEGRAM_BOT_TOKEN: "123456:TEST_TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "987654321",
    GITHUB_DISPATCH_PAT: "ghp_mockpat1234567890",
    GITHUB_REPO_OWNER: "test-owner",
    GITHUB_REPO_NAME: "test-repo",
    DESKTOP_API_SECRET: mockApiSecret,
    NVIDIA_NIM_API_KEY: "nvapi-test-key-789",
  };

  const createMockContext = () => ({
    waitUntil: vi.fn((promise: Promise<unknown>) => promise),
    passThroughOnException: vi.fn(),
    props: {},
  });

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
        list: vi.fn(async (options?: { prefix?: string; cursor?: string }) => {
          const prefix = options?.prefix || "";
          const keys = Array.from(kvStore.keys())
            .filter((k) => k.startsWith(prefix))
            .map((name) => ({ name }));
          return {
            keys,
            list_complete: true,
          };
        }),
      },
    };
  };

  const makeApiRequest = (
    path: string,
    options: {
      method?: string;
      token?: string | null;
      body?: unknown;
      headers?: Record<string, string>;
    } = {}
  ) => {
    const { method = "GET", token = mockApiSecret, body, headers = {} } = options;
    const reqHeaders: Record<string, string> = { ...headers };
    if (token !== null) {
      reqHeaders["Authorization"] = `Bearer ${token}`;
    }
    if (body !== undefined && !reqHeaders["Content-Type"]) {
      reqHeaders["Content-Type"] = "application/json";
    }
    return new Request(`https://worker.local${path}`, {
      method,
      headers: reqHeaders,
      body: body !== undefined ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined,
    });
  };

  describe("Scheduled Posts API", () => {
    it("handles listing scheduled posts", async () => {
      const { kv } = createMockKv({
        scheduled_posts: JSON.stringify([
          { id: "post_1", post_text: "Hello world", headline: "Headline 1", status: "draft" },
        ]),
      });
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/scheduled-posts");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.posts).toHaveLength(1);
      expect(data.posts[0].id).toBe("post_1");
    });

    it("handles creating and saving a scheduled post", async () => {
      const { kv, store } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/scheduled-posts", {
        method: "POST",
        body: {
          id: "post_custom_1",
          post_text: "Automated insight about LLMs",
          headline: "LLM Orchestration",
          status: "scheduled",
        },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.post.id).toBe("post_custom_1");

      expect(store.has("scheduled:post_custom_1")).toBe(true);
      const listInKv = JSON.parse(store.get("scheduled_posts")!);
      expect(listInKv).toHaveLength(1);
      expect(listInKv[0].id).toBe("post_custom_1");
    });

    it("handles deleting a scheduled post", async () => {
      const { kv, store } = createMockKv({
        "scheduled:post_del": JSON.stringify({ id: "post_del", post_text: "To delete" }),
        scheduled_posts: JSON.stringify([{ id: "post_del", post_text: "To delete" }]),
      });
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/scheduled-posts/post_del", {
        method: "DELETE",
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.id).toBe("post_del");

      expect(store.has("scheduled:post_del")).toBe(false);
      const remaining = JSON.parse(store.get("scheduled_posts")!);
      expect(remaining).toHaveLength(0);
    });
  });

  describe("Connection Queue API", () => {
    it("handles listing connection queue", async () => {
      const { kv } = createMockKv({
        connection_queue: JSON.stringify([
          { id: "cand_1", profile_url: "https://linkedin.com/in/alice", target_name: "Alice", status: "pending" },
        ]),
      });
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/connection-queue");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.queue).toHaveLength(1);
      expect(data.queue[0].target_name).toBe("Alice");
    });

    it("handles adding and updating a connection candidate", async () => {
      const { kv, store } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      // Add
      const addReq = makeApiRequest("/api/connection-queue", {
        method: "POST",
        body: {
          id: "cand_new",
          profile_url: "https://linkedin.com/in/bob",
          target_name: "Bob",
        },
      });
      const ctx = createMockContext();
      const addRes = await worker.fetch(addReq, envWithKv, ctx as any);
      expect(addRes.status).toBe(200);

      // Update status
      const updateReq = makeApiRequest("/api/connection-queue", {
        method: "POST",
        body: {
          id: "cand_new",
          status: "approved",
          note_text: "Hi Bob, let's connect!",
        },
      });
      const updateRes = await worker.fetch(updateReq, envWithKv, ctx as any);
      expect(updateRes.status).toBe(200);

      const queueInKv = JSON.parse(store.get("connection_queue")!);
      expect(queueInKv).toHaveLength(1);
      expect(queueInKv[0].status).toBe("approved");
      expect(queueInKv[0].note_text).toBe("Hi Bob, let's connect!");
    });
  });
});
