import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, { Env } from "../src/index";

describe("Authenticated Worker REST API Suite", () => {
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

  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

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

  describe("Bearer Token Authentication", () => {
    it("returns 401 when Authorization header is missing", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/state", { token: null });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(401);
      const data = (await res.json()) as any;
      expect(data).toEqual({ error: "Unauthorized" });
    });

    it("returns 401 when token is invalid or malformed", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const badTokens = ["wrong-secret", "Bearer wrong", "Basic 12345", ""];
      for (const token of badTokens) {
        const req = new Request("https://worker.local/api/state", {
          headers: { Authorization: token },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(401);
        const data = (await res.json()) as any;
        expect(data).toEqual({ error: "Unauthorized" });
      }
    });

    it("returns 401 if DESKTOP_API_SECRET is unset in worker env", async () => {
      const { kv } = createMockKv();
      const envWithoutSecret: Env = { ...mockEnv, DESKTOP_API_SECRET: undefined, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/state");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithoutSecret, ctx as any);
      expect(res.status).toBe(401);
      const data = (await res.json()) as any;
      expect(data).toEqual({ error: "Unauthorized" });
    });

    it("returns 404 for unknown /api/* route with valid token", async () => {
      const req = makeApiRequest("/api/unknown_route");
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(404);
      const data = (await res.json()) as any;
      expect(data).toEqual({ error: "Not Found" });
    });
  });

  describe("GET /api/state", () => {
    it("returns 405 when called with POST", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/state", { method: "POST" });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(405);
      const data = (await res.json()) as any;
      expect(data).toEqual({ error: "Method Not Allowed" });
    });

    it("returns 500 when LINKEDIN_AGENT_KV is not configured", async () => {
      const envWithoutKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: undefined };
      const req = makeApiRequest("/api/state");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithoutKv, ctx as any);
      expect(res.status).toBe(500);
      const data = (await res.json()) as any;
      expect(data).toEqual({ error: "KV namespace not configured" });
    });

    it("returns empty default state when KV is clean", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/state");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);
      expect(data.state).toEqual({
        pending: [],
        daily_counters: null,
        history: [],
        incident: null,
        paused: false,
      });
    });

    it("returns all pending items, counters, history, incident, and paused state", async () => {
      const initialKv = {
        "pending:item_b": JSON.stringify({
          item_id: "item_b",
          created_at: "2026-09-29T12:00:00Z",
          draft_text: "Comment B",
        }),
        "pending:item_a": JSON.stringify({
          item_id: "item_a",
          created_at: "2026-09-29T10:00:00Z",
          draft_text: "Comment A",
        }),
        daily_counters: JSON.stringify({
          date: "2026-09-29",
          comments_executed: 3,
          posts_executed: 1,
          suggestions_sent: 5,
        }),
        history: JSON.stringify([
          { item_id: "hist_1", final_status: "executed_success" },
          { item_id: "hist_2", final_status: "rejected" },
        ]),
        incident: JSON.stringify({
          reason: "Rate limit detected",
          triggered_at: "2026-09-29T09:00:00Z",
        }),
        paused: JSON.stringify({
          paused_at: "2026-09-29T08:00:00Z",
        }),
      };

      const { kv } = createMockKv(initialKv);
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };
      const req = makeApiRequest("/api/state");
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.success).toBe(true);

      // Verify pending items are sorted by created_at ascending
      expect(data.state.pending).toHaveLength(2);
      expect(data.state.pending[0].item_id).toBe("item_a");
      expect(data.state.pending[1].item_id).toBe("item_b");

      expect(data.state.daily_counters).toEqual({
        date: "2026-09-29",
        comments_executed: 3,
        posts_executed: 1,
        suggestions_sent: 5,
      });

      expect(data.state.history).toHaveLength(2);
      expect(data.state.history[0].item_id).toBe("hist_1");

      expect(data.state.incident).toEqual({
        reason: "Rate limit detected",
        triggered_at: "2026-09-29T09:00:00Z",
      });

      expect(data.state.paused).toBe(true);
    });
  });

  describe("POST /api/action", () => {
    it("returns 400 for invalid action or missing item_id", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const invalidBodies = [
        {},
        { action: "approve" },
        { item_id: "123" },
        { action: "invalid_action", item_id: "123" },
      ];

      for (const body of invalidBodies) {
        const req = makeApiRequest("/api/action", { method: "POST", body });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(400);
      }
    });

    describe("reject action", () => {
      it("deletes pending item from KV, appends to history, edits TG message, and makes ZERO GitHub API calls", async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
        globalThis.fetch = fetchMock;

        const initialKv = {
          "pending:item_reject_1": JSON.stringify({
            item_id: "item_reject_1",
            action_type: "approve_comment",
            telegram_message_id: 8888,
            telegram_chat_id: 987654321,
            draft_text: "Interesting perspective!",
          }),
          history: JSON.stringify([
            { item_id: "prev_item", final_status: "executed_success" },
          ]),
        };

        const { kv, store } = createMockKv(initialKv);
        const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: { action: "reject", item_id: "item_reject_1" },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data).toEqual({
          success: true,
          status: "rejected",
          item_id: "item_reject_1",
        });

        // 1. Pending item deleted from KV
        expect(store.has("pending:item_reject_1")).toBe(false);

        // 2. Appended rejection history entry
        const historyJson = JSON.parse(store.get("history")!);
        expect(historyJson).toHaveLength(2);
        expect(historyJson[1]).toMatchObject({
          item_id: "item_reject_1",
          action_type: "approve_comment",
          final_status: "rejected",
        });

        // 3. Telegram message was edited to reject notification
        expect(fetchMock).toHaveBeenCalledWith(
          `https://api.telegram.org/bot${mockEnv.TELEGRAM_BOT_TOKEN}/editMessageText`,
          expect.objectContaining({
            method: "POST",
            body: expect.stringContaining("❌ Suggestion rejected"),
          })
        );

        // 4. ZERO calls to GitHub Actions API
        const githubCalls = fetchMock.mock.calls.filter(([url]: [string]) =>
          url.includes("api.github.com")
        );
        expect(githubCalls).toHaveLength(0);
      });
    });

    describe("approve action", () => {
      it("dispatches repository_dispatch to GitHub Actions and returns dispatched status", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("api.github.com")) {
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          return Promise.resolve(new Response("{}", { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const initialKv = {
          "pending:item_approve_1": JSON.stringify({
            item_id: "item_approve_1",
            action_type: "approve_comment",
            telegram_message_id: 9999,
          }),
        };

        const { kv } = createMockKv(initialKv);
        const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: { action: "approve", item_id: "item_approve_1" },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data).toEqual({
          success: true,
          status: "dispatched",
          action: "approve",
          item_id: "item_approve_1",
        });

        // Verify GitHub Actions dispatch request
        const githubCalls = fetchMock.mock.calls.filter(([url]: [string]) =>
          url.includes("api.github.com")
        );
        expect(githubCalls).toHaveLength(1);
        const [url, opts] = githubCalls[0];
        expect(url).toBe(
          `https://api.github.com/repos/${mockEnv.GITHUB_REPO_OWNER}/${mockEnv.GITHUB_REPO_NAME}/dispatches`
        );
        expect(opts.method).toBe("POST");
        const payload = JSON.parse(opts.body);
        expect(payload).toEqual({
          event_type: "telegram-approval-action",
          client_payload: {
            action: "approve",
            item_id: "item_approve_1",
            telegram_chat_id: 987654321,
            telegram_message_id: 9999,
            source: "desktop_api",
          },
        });
      });

      it("updates pending item draft_text in KV when provided on approval", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("api.github.com")) {
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          return Promise.resolve(new Response("{}", { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const initialKv = {
          "pending:item_with_draft": JSON.stringify({
            item_id: "item_with_draft",
            action_type: "approve_comment",
            draft_text: "Old unedited draft.",
            telegram_chat_id: 1111,
            telegram_message_id: 2222,
          }),
        };

        const { kv, store } = createMockKv(initialKv);
        const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: {
            action: "approve",
            item_id: "item_with_draft",
            draft_text: "New improved operator revised comment draft.",
          },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);

        // Verify KV was updated with new draft_text
        const updatedRaw = store.get("pending:item_with_draft");
        expect(updatedRaw).toBeTruthy();
        const updated = JSON.parse(updatedRaw!);
        expect(updated.draft_text).toBe("New improved operator revised comment draft.");
      });

      it("returns 502 when GitHub Actions dispatch fails", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("api.github.com")) {
            return Promise.resolve(
              new Response(JSON.stringify({ message: "Bad credentials" }), {
                status: 401,
                statusText: "Unauthorized",
              })
            );
          }
          return Promise.resolve(new Response("{}", { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: { action: "approve", item_id: "item_err_1" },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(502);
        const data = (await res.json()) as any;
        expect(data.error).toBe("GitHub dispatch failed");
      });

      it("uses body repo_owner, repo_name, and github_pat when env variables are not present", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("api.github.com")) {
            return Promise.resolve(new Response(null, { status: 204 }));
          }
          return Promise.resolve(new Response("{}", { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const envWithoutGithub: Env = {
          ...mockEnv,
          GITHUB_REPO_OWNER: "",
          GITHUB_REPO_NAME: "",
          GITHUB_DISPATCH_PAT: "",
        };

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: {
            action: "approve",
            item_id: "item_custom_cred",
            repo_owner: "custom-user",
            repo_name: "custom-repo",
            github_pat: "ghp_custom12345",
          },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, envWithoutGithub, ctx as any);
        expect(res.status).toBe(200);

        const githubCall = fetchMock.mock.calls.find(([url]: [string]) =>
          url.includes("api.github.com")
        );
        expect(githubCall).toBeDefined();
        expect(githubCall[0]).toBe("https://api.github.com/repos/custom-user/custom-repo/dispatches");
        expect(githubCall[1].headers.Authorization).toBe("Bearer ghp_custom12345");
      });

      it("returns 400 with details when GitHub dispatch config is missing in both env and body", async () => {
        const envWithoutGithub: Env = {
          ...mockEnv,
          GITHUB_REPO_OWNER: "",
          GITHUB_REPO_NAME: "",
          GITHUB_DISPATCH_PAT: "",
        };

        const req = makeApiRequest("/api/action", {
          method: "POST",
          body: { action: "approve", item_id: "item_missing_creds" },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, envWithoutGithub, ctx as any);
        expect(res.status).toBe(400);
        const data = (await res.json()) as any;
        expect(data.error).toContain("Missing configuration");
        expect(data.details).toContain("GITHUB_REPO_OWNER");
        expect(data.details).toContain("GITHUB_REPO_NAME");
        expect(data.details).toContain("GITHUB_DISPATCH_PAT");
      });
    });
  });

  describe("POST /api/scout", () => {
    it("triggers workflow_dispatch on scout.yml and returns scout_triggered", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url.includes("actions/workflows/scout.yml/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(new Response("{}", { status: 200 }));
      });
      globalThis.fetch = fetchMock;

      const req = makeApiRequest("/api/scout", { method: "POST" });
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({
        success: true,
        status: "scout_triggered",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        `https://api.github.com/repos/${mockEnv.GITHUB_REPO_OWNER}/${mockEnv.GITHUB_REPO_NAME}/actions/workflows/scout.yml/dispatches`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ ref: "main" }),
        })
      );
    });

    it("supports use_repository_dispatch flag", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url.endsWith("/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(new Response("{}", { status: 200 }));
      });
      globalThis.fetch = fetchMock;

      const req = makeApiRequest("/api/scout", {
        method: "POST",
        body: { use_repository_dispatch: true },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.status).toBe("scout_triggered");

      expect(fetchMock).toHaveBeenCalledWith(
        `https://api.github.com/repos/${mockEnv.GITHUB_REPO_OWNER}/${mockEnv.GITHUB_REPO_NAME}/dispatches`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            event_type: "linkedin_agent_action",
            client_payload: { action: "scout" },
          }),
        })
      );
    });

    it("returns 502 if GitHub dispatch fails", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response("Server Error", { status: 500, statusText: "Internal Server Error" })
      );
      globalThis.fetch = fetchMock;

      const req = makeApiRequest("/api/scout", { method: "POST" });
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(502);
      const data = (await res.json()) as any;
      expect(data.error).toBe("GitHub scout dispatch failed");
    });

    it("uses body credentials when env variables are missing", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url.includes("actions/workflows/scout.yml/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(new Response("{}", { status: 200 }));
      });
      globalThis.fetch = fetchMock;

      const envWithoutGithub: Env = {
        ...mockEnv,
        GITHUB_REPO_OWNER: "",
        GITHUB_REPO_NAME: "",
        GITHUB_DISPATCH_PAT: "",
      };

      const req = makeApiRequest("/api/scout", {
        method: "POST",
        body: {
          repo_owner: "custom-scout-owner",
          repo_name: "custom-scout-repo",
          github_pat: "ghp_scout123",
        },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithoutGithub, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data.status).toBe("scout_triggered");

      expect(fetchMock).toHaveBeenCalledWith(
        "https://api.github.com/repos/custom-scout-owner/custom-scout-repo/actions/workflows/scout.yml/dispatches",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer ghp_scout123",
          }),
        })
      );
    });

    it("returns 400 when scout dispatch config is missing in both env and body", async () => {
      const envWithoutGithub: Env = {
        ...mockEnv,
        GITHUB_REPO_OWNER: "",
        GITHUB_REPO_NAME: "",
        GITHUB_DISPATCH_PAT: "",
      };

      const req = makeApiRequest("/api/scout", { method: "POST" });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithoutGithub, ctx as any);
      expect(res.status).toBe(400);
      const data = (await res.json()) as any;
      expect(data.error).toContain("Missing configuration");
      expect(data.details).toContain("GITHUB_DISPATCH_PAT");
    });
  });

  describe("POST /api/pause", () => {
    it("returns 400 when paused is not a boolean", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const req = makeApiRequest("/api/pause", {
        method: "POST",
        body: { paused: "yes" },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(400);
      const data = (await res.json()) as any;
      expect(data.error).toContain("must be a boolean");
    });

    it("sets paused in KV when paused: true", async () => {
      const { kv, store } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const req = makeApiRequest("/api/pause", {
        method: "POST",
        body: { paused: true },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({ success: true, paused: true });

      expect(store.has("paused")).toBe(true);
      const pausedVal = JSON.parse(store.get("paused")!);
      expect(pausedVal.paused_at).toBeDefined();
    });

    it("deletes paused from KV when paused: false", async () => {
      const { kv, store } = createMockKv({
        paused: JSON.stringify({ paused_at: "2026-09-29T10:00:00Z" }),
      });
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const req = makeApiRequest("/api/pause", {
        method: "POST",
        body: { paused: false },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({ success: true, paused: false });

      expect(store.has("paused")).toBe(false);
    });
  });

  describe("POST /api/incident/clear", () => {
    it("deletes incident from KV and returns cleared: true", async () => {
      const { kv, store } = createMockKv({
        incident: JSON.stringify({ reason: "Bot challenge detected" }),
      });
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const req = makeApiRequest("/api/incident/clear", { method: "POST" });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({ success: true, cleared: true });

      expect(store.has("incident")).toBe(false);
    });
  });

  describe("POST /api/session", () => {
    it("returns 400 on missing or invalid session_data", async () => {
      const { kv } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const invalidBodies = [{}, { session_data: "" }, { session_data: 12345 }];
      for (const body of invalidBodies) {
        const req = makeApiRequest("/api/session", { method: "POST", body });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(400);
      }
    });

    it("stores encrypted session state in KV and returns stored: true", async () => {
      const { kv, store } = createMockKv();
      const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kv as any };

      const mockSessionEnc = "aes256gcm:encrypted_storage_state_payload_here";
      const req = makeApiRequest("/api/session", {
        method: "POST",
        body: { session_data: mockSessionEnc },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envWithKv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({ success: true, stored: true });

      expect(store.get("linkedin_session_state_enc")).toBe(mockSessionEnc);
    });
  });

  describe("POST /api/rewrite", () => {
    it("returns 400 on missing draft_text or invalid tone", async () => {
      const invalidBodies = [
        {},
        { draft_text: "Some draft" },
        { draft_text: "Some draft", tone: "humorous" },
        { tone: "technical" },
      ];

      for (const body of invalidBodies) {
        const req = makeApiRequest("/api/rewrite", { method: "POST", body });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(400);
      }
    });

    it("returns 500 if NVIDIA_NIM_API_KEY is not configured", async () => {
      const envNoNim = { ...mockEnv, NVIDIA_NIM_API_KEY: undefined };
      const req = makeApiRequest("/api/rewrite", {
        method: "POST",
        body: { draft_text: "My original comment", tone: "technical" },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, envNoNim, ctx as any);
      expect(res.status).toBe(500);
      const data = (await res.json()) as any;
      expect(data.error).toContain("NVIDIA_NIM_API_KEY");
    });

    it("calls LLM completions and returns rewritten draft for valid tone", async () => {
      const mockRewritten = "A technically rigorous analysis of the architecture.";
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            choices: [{ message: { content: mockRewritten } }],
          }),
          { status: 200 }
        )
      );
      globalThis.fetch = fetchMock;

      const req = makeApiRequest("/api/rewrite", {
        method: "POST",
        body: {
          draft_text: "This architecture looks good.",
          tone: "technical",
          post_excerpt: "Discussing distributed consensus in KV systems",
        },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(200);
      const data = (await res.json()) as any;
      expect(data).toEqual({
        success: true,
        rewritten_text: mockRewritten,
        rewrittenText: mockRewritten,
        draft: mockRewritten,
        tone: "technical",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: `Bearer ${mockEnv.NVIDIA_NIM_API_KEY}`,
          }),
        })
      );
    });

    it("supports tones: technical, inquisitive, contrarian, shorter, regenerate, casual, concise", async () => {
      const tones = [
        "technical",
        "inquisitive",
        "contrarian",
        "shorter",
        "regenerate",
        "casual",
        "concise",
      ] as const;

      for (const tone of tones) {
        const fetchMock = vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({
              choices: [{ message: { content: `Rewritten as ${tone}` } }],
            }),
            { status: 200 }
          )
        );
        globalThis.fetch = fetchMock;

        const req = makeApiRequest("/api/rewrite", {
          method: "POST",
          body: { draft_text: "Test draft comment", tone },
        });
        const ctx = createMockContext();

        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.success).toBe(true);
        expect(data.tone).toBe(tone);
        expect(data.rewritten_text).toBe(`Rewritten as ${tone}`);
        expect(data.rewrittenText).toBe(`Rewritten as ${tone}`);
        expect(data.draft).toBe(`Rewritten as ${tone}`);
      }
    });

    it("returns 502 if LLM completions request fails", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response("LLM Rate Limited", { status: 429, statusText: "Too Many Requests" })
      );
      globalThis.fetch = fetchMock;

      const req = makeApiRequest("/api/rewrite", {
        method: "POST",
        body: { draft_text: "Test draft comment", tone: "shorter" },
      });
      const ctx = createMockContext();

      const res = await worker.fetch(req, mockEnv, ctx as any);
      expect(res.status).toBe(502);
      const data = (await res.json()) as any;
      expect(data.error).toBe("LLM rewrite request failed");
    });
  });
});
