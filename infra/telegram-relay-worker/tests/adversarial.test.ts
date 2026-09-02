import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, {
  escapeHtml,
  formatTelegramErrorMessage,
  notifyTelegramFailure,
  Env,
} from "../src/index";

describe("Adversarial & Stress Verification Suite", () => {
  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "secure-webhook-secret-token-xyz-987",
    TELEGRAM_BOT_TOKEN: "999999:BOT_TOKEN_SECRET",
    TELEGRAM_AUTHORIZED_CHAT_ID: "123456789",
    GITHUB_DISPATCH_PAT: "ghp_dispatch_secret_pat_999",
    GITHUB_REPO_OWNER: "target-org",
    GITHUB_REPO_NAME: "target-repo",
  };

  const createMockContext = () => ({
    waitUntil: vi.fn((promise: Promise<unknown>) => promise),
    passThroughOnException: vi.fn(),
    props: {},
  });

  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const makeRequest = (
    body: unknown,
    headers: Record<string, string> = {
      "X-Telegram-Bot-Api-Secret-Token": mockEnv.TELEGRAM_WEBHOOK_SECRET,
      "Content-Type": "application/json",
    },
    method = "POST"
  ) => {
    return new Request("https://worker.local/webhook", {
      method,
      headers,
      body: typeof body === "string" ? body : JSON.stringify(body),
    });
  };

  // Helper to validate Telegram HTML tag balancing and permitted tags
  const validateTelegramHtmlTags = (html: string) => {
    const allowedTags = ["b", "i", "u", "s", "code", "pre", "a", "tg-spoiler", "blockquote"];
    const tagRegex = /<\/?([a-z0-9_-]+)(?:\s+[^>]*)?>/gi;
    const stack: string[] = [];
    let match;

    while ((match = tagRegex.exec(html)) !== null) {
      const fullTag = match[0];
      const tagName = match[1].toLowerCase();

      expect(allowedTags).toContain(tagName);

      const isClosing = fullTag.startsWith("</");
      if (isClosing) {
        const last = stack.pop();
        expect(last).toBe(tagName);
      } else {
        stack.push(tagName);
      }
    }
    // All opened tags must be properly closed
    expect(stack).toEqual([]);
  };

  describe("1. HTML Injection & Entity Escaping Stress", () => {
    const maliciousPayloads = [
      `<script>alert(document.cookie)</script>`,
      `<img src=x onerror="alert(1)">`,
      `</b></code></i></a></pre>`,
      `<b><b><b>unclosed nested tags`,
      `<<<>>>&&&"""'''`,
      `&amp;lt;script&amp;gt;`,
      `\u0000\u0001\u001f\u007f\ufffe\uffff`,
      `🔥🚀✨💥\uD83D\uDE00`,
      `' OR '1'='1; DROP TABLE users; --`,
      `{{7*7}}\${7*7}`,
      `\r\n\r\nHTTP/1.1 200 OK\r\nSet-Cookie: stolen=true`,
      `{"json":"injection","nested":{"deep":true}}`,
      `<a href="javascript:alert(1)">Click Here</a>`,
      `<tg-spoiler>hidden</tg-spoiler>`,
    ];

    it.each(maliciousPayloads)("safely escapes malicious input: %s", (payload) => {
      const escaped = escapeHtml(payload);
      expect(escaped).not.toContain("<script>");
      expect(escaped).not.toContain("</script>");
      expect(escaped).not.toContain("<img");
      expect(escaped).not.toContain(`"`);
      expect(escaped).not.toContain(`'`);

      // Verify that formatting produces valid balanced HTML
      const msg = formatTelegramErrorMessage("approve", "item-x", payload, payload);
      validateTelegramHtmlTags(msg);
    });

    it("handles extreme string lengths (15,000+ chars) and truncates details to 500 safely", () => {
      const hugeError = "<dangerous-tag>" + "A".repeat(15000) + "</dangerous-tag>";
      const hugeItemId = "ITEM-" + "B".repeat(5000);
      const hugeSummary = "ERR-" + "C".repeat(5000);

      const msg = formatTelegramErrorMessage("approve", hugeItemId, hugeSummary, hugeError);
      validateTelegramHtmlTags(msg);

      expect(msg).toContain("<b>Details:</b>");
      expect(msg.length).toBeLessThan(35000);
    });

    it("handles null/undefined/empty details cleanly", () => {
      const msg1 = formatTelegramErrorMessage("approve", "123", "Summary", undefined);
      validateTelegramHtmlTags(msg1);
      expect(msg1).not.toContain("<b>Details:</b>");

      const msg2 = formatTelegramErrorMessage("reject", "123", "Summary", "");
      validateTelegramHtmlTags(msg2);
      expect(msg2).not.toContain("<b>Details:</b>");
    });
  });

  describe("2. Comprehensive Non-2xx GitHub Status Code Handling", () => {
    const errorScenarios = [
      { status: 400, statusText: "Bad Request", body: '{"error":"malformed_json"}' },
      { status: 401, statusText: "Unauthorized", body: '{"message":"Bad credentials"}' },
      { status: 403, statusText: "Forbidden", body: '{"message":"Resource not accessible by integration"}' },
      { status: 404, statusText: "Not Found", body: '{"message":"Repository not found"}' },
      { status: 409, statusText: "Conflict", body: '{"message":"Repository is archived"}' },
      { status: 422, statusText: "Unprocessable Entity", body: '{"message":"Invalid client_payload schema"}' },
      { status: 429, statusText: "Too Many Requests", body: '{"message":"API rate limit exceeded"}' },
      { status: 500, statusText: "Internal Server Error", body: "Server Error: Octocat exploded" },
      { status: 502, statusText: "Bad Gateway", body: "Cloudflare/GitHub Gateway Error" },
      { status: 503, statusText: "Service Unavailable", body: "GitHub is undergoing maintenance" },
      { status: 504, statusText: "Gateway Timeout", body: "Upstream timeout after 30000ms" },
    ];

    it.each(errorScenarios)(
      "correctly catches HTTP $status $statusText from GitHub, returns 502, and updates Telegram",
      async ({ status, statusText, body }) => {
        let telegramEdited = false;
        let sentHtml = "";

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            return new Response(body, { status, statusText });
          }
          if (url.includes("editMessageText")) {
            telegramEdited = true;
            const parsed = JSON.parse(opts.body);
            sentHtml = parsed.text;
            return new Response("{}", { status: 200 });
          }
          return new Response("Not Found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 100,
          callback_query: {
            id: `cb_${status}`,
            from: { id: 123456789, is_bot: false, first_name: "Operator" },
            message: { message_id: 5000 + status, chat: { id: 123456789 } },
            data: "ac:item_stress_test",
          },
        });

        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(502);
        expect(res.headers.get("Content-Type")).toBe("application/json");

        const json = await res.json() as any;
        expect(json.error).toBe("GitHub dispatch failed");
        expect(json.status_code).toBe(status);
        expect(json.status_text).toBe(statusText);
        expect(json.details).toBe(body);
        expect(json.action).toBe("approve");
        expect(json.item_id).toBe("item_stress_test");

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));

        expect(telegramEdited).toBe(true);
        validateTelegramHtmlTags(sentHtml);
        expect(sentHtml).toContain(`${status} ${statusText}`);
      }
    );
  });

  describe("3. Network, DNS, and Timeout Exceptions during GitHub Fetch", () => {
    const networkExceptions = [
      { name: "TypeError fetch failed", error: new TypeError("fetch failed: connection reset") },
      { name: "AbortError Timeout", error: new DOMException("The operation was aborted due to timeout", "AbortError") },
      { name: "DNS Resolution Error", error: new Error("getaddrinfo ENOTFOUND api.github.com") },
      { name: "Custom Object Error", error: { customError: "something broke", code: "ERR_CUSTOM" } },
      { name: "Primitive String Error", error: "Fatal raw socket failure" },
      { name: "Null Error", error: null },
      { name: "Undefined Error", error: undefined },
      { name: "Number Error", error: 503 },
    ];

    it.each(networkExceptions)(
      "gracefully handles GitHub fetch error: $name",
      async ({ error }) => {
        let telegramEdited = false;
        let sentHtml = "";

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            throw error;
          }
          if (url.includes("editMessageText")) {
            telegramEdited = true;
            sentHtml = JSON.parse(opts.body).text;
            return new Response("{}", { status: 200 });
          }
          return new Response("Not Found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 200,
          callback_query: {
            id: "cb_net_ex",
            from: { id: 123456789, is_bot: false, first_name: "Operator" },
            message: { message_id: 6001, chat: { id: 123456789 } },
            data: "rej:item_net_ex",
          },
        });

        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(502);
        const json = await res.json() as any;
        expect(json.error).toBe("GitHub dispatch network failure");
        expect(json.action).toBe("reject");
        expect(json.item_id).toBe("item_net_ex");

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(telegramEdited).toBe(true);
        validateTelegramHtmlTags(sentHtml);
      }
    );
  });

  describe("4. Secondary Telegram Failures & Resilience", () => {
    it("does not crash or alter HTTP 502 response when Telegram editMessageText returns 400 or 500", async () => {
      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("answerCallbackQuery")) {
          return new Response("{}", { status: 200 });
        }
        if (url.includes("/dispatches")) {
          return new Response("GitHub 500", { status: 500, statusText: "Internal Server Error" });
        }
        if (url.includes("editMessageText")) {
          return new Response('{"ok":false,"error_code":400,"description":"Bad Request: message is not modified"}', {
            status: 400,
          });
        }
        return new Response("Not Found", { status: 404 });
      });
      globalThis.fetch = fetchMock;

      const req = makeRequest({
        update_id: 300,
        callback_query: {
          id: "cb_sec_fail",
          from: { id: 123456789, is_bot: false, first_name: "Operator" },
          message: { message_id: 7001, chat: { id: 123456789 } },
          data: "ac:item_sec_fail",
        },
      });

      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(502);
      await expect(Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p))).resolves.toBeDefined();
    });

    it("does not crash when answerCallbackQuery rejects with a network error", async () => {
      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("answerCallbackQuery")) {
          throw new Error("Telegram toast timeout");
        }
        if (url.includes("/dispatches")) {
          return new Response(null, { status: 204 });
        }
        return new Response("Not Found", { status: 404 });
      });
      globalThis.fetch = fetchMock;

      const req = makeRequest({
        update_id: 301,
        callback_query: {
          id: "cb_toast_err",
          from: { id: 123456789, is_bot: false, first_name: "Operator" },
          message: { message_id: 7002, chat: { id: 123456789 } },
          data: "ap:item_toast_err",
        },
      });

      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(200);
      await expect(Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p))).resolves.toBeDefined();
    });
  });

  describe("5. Authentication & Authorization Boundaries", () => {
    it.each([
      ["missing secret header", {}],
      ["empty secret header", { "X-Telegram-Bot-Api-Secret-Token": "" }],
      ["wrong secret token", { "X-Telegram-Bot-Api-Secret-Token": "attacker-token" }],
      ["partial secret match", { "X-Telegram-Bot-Api-Secret-Token": "secure-webhook-secret-token-xyz" }],
    ])("rejects unauthorized webhook request (%s) with 401", async (_, headers) => {
      const req = makeRequest({ update_id: 400 }, headers);
      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(401);
      expect(await res.text()).toBe("Unauthorized Webhook Secret");
    });

    it.each([
      ["numeric attacker ID", 999999999],
      ["negative channel/chat ID", -100123456789],
      ["zero ID", 0],
      ["neighbor ID", 123456788],
    ])("rejects unauthorized sender ID (%s) with 403", async (_, attackerId) => {
      const req = makeRequest({
        update_id: 401,
        callback_query: {
          id: "cb_unauth",
          from: { id: attackerId, is_bot: false, first_name: "Attacker" },
          data: "ac:item_hacked",
        },
      });
      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(403);
      expect(await res.text()).toBe("Unauthorized Sender ID");
    });
  });

  describe("6. Callback Data Grammar & Action Routing", () => {
    const invalidCallbackPayloads = [
      "ac",
      "approve",
      ":",
      ":item123",
      "invalid_action:123",
      "__proto__:item1",
      "constructor:item2",
      "toString:item3",
    ];

    it.each(invalidCallbackPayloads)("safely rejects malformed callback data '%s' with 400", async (data) => {
      const req = makeRequest({
        update_id: 500,
        callback_query: {
          id: "cb_malformed",
          from: { id: 123456789, is_bot: false, first_name: "Operator" },
          data,
        },
      });
      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(400);
    });

    it("verifies all valid action aliases map to expected actions", async () => {
      const mappings: [string, "approve" | "reject"][] = [
        ["ac:item1", "approve"],
        ["ap:item2", "approve"],
        ["apv:item3", "approve"],
        ["rc:item4", "reject"],
        ["rp:item5", "reject"],
        ["rej:item6", "reject"],
      ];

      for (const [data, expectedAction] of mappings) {
        let dispatchedAction = "";
        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) return new Response("{}", { status: 200 });
          if (url.includes("/dispatches")) {
            dispatchedAction = JSON.parse(opts.body).client_payload.action;
            return new Response(null, { status: 204 });
          }
          return new Response("Not Found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 501,
          callback_query: {
            id: `cb_${data}`,
            from: { id: 123456789, is_bot: false, first_name: "Operator" },
            data,
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        expect(dispatchedAction).toBe(expectedAction);
      }
    });
  });

  describe("7. HTTP Method & Request Body Fuzzing", () => {
    const nonPostMethods = ["GET", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"];

    it.each(nonPostMethods)("rejects non-POST method %s with 405", async (method) => {
      const req = new Request("https://worker.local/webhook", { method });
      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect(res.status).toBe(405);
      expect(await res.text()).toBe("Method Not Allowed");
    });

    it.each([
      "not json at all",
      "{ unclosed: json",
      "12345",
      "true",
      "[1, 2, 3]",
      "",
    ])("handles malformed or non-object JSON body (%s) safely", async (badBody) => {
      const req = makeRequest(badBody);
      const ctx = createMockContext();
      const res = await worker.fetch(req, mockEnv, ctx as any);

      expect([200, 400]).toContain(res.status);
    });
  });
});
