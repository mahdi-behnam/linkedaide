import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, {
  escapeHtml,
  formatTelegramErrorMessage,
  notifyTelegramFailure,
  Env,
} from "../src/index";

describe("Telegram Relay Worker", () => {
  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "my-secret-token-123",
    TELEGRAM_BOT_TOKEN: "123456:TEST_TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "987654321",
    GITHUB_DISPATCH_PAT: "ghp_mockpat1234567890",
    GITHUB_REPO_OWNER: "test-owner",
    GITHUB_REPO_NAME: "test-repo",
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

  describe("Utility Functions", () => {
    describe("escapeHtml", () => {
      it("escapes all HTML special characters: &, <, >, \", '", () => {
        const input = `<script>alert("xss" & 'test')</script>`;
        const output = escapeHtml(input);
        expect(output).toBe(
          "&lt;script&gt;alert(&quot;xss&quot; &amp; &#039;test&#039;)&lt;/script&gt;"
        );
      });

      it("returns plain text unchanged when no special characters exist", () => {
        expect(escapeHtml("plain text 123")).toBe("plain text 123");
      });

      it("escapes multiple occurrences of special characters", () => {
        expect(escapeHtml("a < b && c > d")).toBe("a &lt; b &amp;&amp; c &gt; d");
      });
    });

    describe("formatTelegramErrorMessage", () => {
      it("formats error message with action, itemId, summary, and details", () => {
        const msg = formatTelegramErrorMessage(
          "approve",
          "item-123",
          "401 Unauthorized",
          "Bad credentials"
        );
        expect(msg).toContain("⚠️ <b>GitHub Dispatch Failed</b>");
        expect(msg).toContain("<b>Action:</b> approve");
        expect(msg).toContain("<b>Item ID:</b> <code>item-123</code>");
        expect(msg).toContain("<b>Error:</b> <code>401 Unauthorized</code>");
        expect(msg).toContain("<b>Details:</b> <code>Bad credentials</code>");
      });

      it("escapes special characters in error details and parameters", () => {
        const msg = formatTelegramErrorMessage(
          "<approve>",
          "item&1",
          "500 <Internal>",
          'Error: "Invalid <tag>"'
        );
        expect(msg).toContain("<b>Action:</b> &lt;approve&gt;");
        expect(msg).toContain("<b>Item ID:</b> <code>item&amp;1</code>");
        expect(msg).toContain("<b>Error:</b> <code>500 &lt;Internal&gt;</code>");
        expect(msg).toContain(
          "<b>Details:</b> <code>Error: &quot;Invalid &lt;tag&gt;&quot;</code>"
        );
      });

      it("truncates error details if longer than 500 characters", () => {
        const longDetail = "x".repeat(600);
        const msg = formatTelegramErrorMessage("approve", "item-1", "Error", longDetail);
        expect(msg).toContain(`<code>${"x".repeat(500)}</code>`);
        expect(msg).not.toContain("x".repeat(501));
      });

      it("omits details line when errorDetails is omitted or empty", () => {
        const msg = formatTelegramErrorMessage("reject", "item-456", "404 Not Found");
        expect(msg).not.toContain("<b>Details:</b>");
      });
    });

    describe("notifyTelegramFailure", () => {
      it("calls editMessageText when messageId is provided and strips keyboard", async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
        globalThis.fetch = fetchMock;

        await notifyTelegramFailure(mockEnv, 987654321, 12345, "Error text");

        expect(fetchMock).toHaveBeenCalledTimes(1);
        const [url, options] = fetchMock.mock.calls[0];
        expect(url).toBe(
          `https://api.telegram.org/bot${mockEnv.TELEGRAM_BOT_TOKEN}/editMessageText`
        );
        expect(options.method).toBe("POST");
        const body = JSON.parse(options.body);
        expect(body).toEqual({
          chat_id: 987654321,
          message_id: 12345,
          text: "Error text",
          parse_mode: "HTML",
          link_preview_options: { is_disabled: true },
          reply_markup: { inline_keyboard: [] },
        });
      });

      it("calls sendMessage when messageId is null", async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
        globalThis.fetch = fetchMock;

        await notifyTelegramFailure(mockEnv, 987654321, null, "Error text");

        expect(fetchMock).toHaveBeenCalledTimes(1);
        const [url, options] = fetchMock.mock.calls[0];
        expect(url).toBe(
          `https://api.telegram.org/bot${mockEnv.TELEGRAM_BOT_TOKEN}/sendMessage`
        );
        const body = JSON.parse(options.body);
        expect(body).toEqual({
          chat_id: 987654321,
          text: "Error text",
          parse_mode: "HTML",
          link_preview_options: { is_disabled: true },
        });
      });

      it("swallows Telegram API exceptions without throwing", async () => {
        const fetchMock = vi.fn().mockRejectedValue(new Error("Telegram network failure"));
        globalThis.fetch = fetchMock;

        await expect(
          notifyTelegramFailure(mockEnv, 987654321, 12345, "Error text")
        ).resolves.toBeUndefined();
      });
    });
  });

  describe("Worker Fetch Handler", () => {
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

    describe("HTTP Method & Secret Validation", () => {
      it("returns 405 when HTTP method is not POST", async () => {
        const req = new Request("https://worker.local/webhook", { method: "GET" });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(405);
        expect(await res.text()).toBe("Method Not Allowed");
      });

      it("returns 401 when X-Telegram-Bot-Api-Secret-Token header is missing", async () => {
        const req = new Request("https://worker.local/webhook", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(401);
        expect(await res.text()).toBe("Unauthorized Webhook Secret");
      });

      it("returns 401 when X-Telegram-Bot-Api-Secret-Token header is invalid", async () => {
        const req = makeRequest({}, { "X-Telegram-Bot-Api-Secret-Token": "wrong-secret" });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(401);
        expect(await res.text()).toBe("Unauthorized Webhook Secret");
      });
    });

    describe("Payload & Sender Validation", () => {
      it("returns 400 when request payload is not valid JSON", async () => {
        const req = makeRequest("invalid-json{");
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(400);
        expect(await res.text()).toBe("Invalid JSON Payload");
      });

      it("returns 200 when update contains no callback_query", async () => {
        const req = makeRequest({ update_id: 1, message: { text: "hello" } });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        expect(await res.text()).toBe("Ignored non-callback update");
      });

      it("returns 200 when callback_query has no data", async () => {
        const req = makeRequest({
          update_id: 1,
          callback_query: { id: "cb1", from: { id: 987654321 } },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        expect(await res.text()).toBe("Ignored non-callback update");
      });

      it("returns 403 when sender ID is not the authorized chat ID", async () => {
        const req = makeRequest({
          update_id: 1,
          callback_query: {
            id: "cb1",
            from: { id: 111222333, is_bot: false, first_name: "Attacker" },
            data: "ac:item1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(403);
        expect(await res.text()).toBe("Unauthorized Sender ID");
      });
    });

    describe("Callback Data Parsing", () => {
      it("returns 400 when callback_data is not colon-delimited", async () => {
        const req = makeRequest({
          update_id: 1,
          callback_query: {
            id: "cb1",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            data: "approve_no_colon",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(400);
        expect(await res.text()).toBe("Invalid callback_data format");
      });

      it("returns 400 when action code is unknown", async () => {
        const req = makeRequest({
          update_id: 1,
          callback_query: {
            id: "cb1",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            data: "unknown_code:item123",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(400);
        expect(await res.text()).toBe("Unknown action code");
      });
    });

    describe("Successful Dispatch Paths", () => {
      it.each([
        ["ac", "approve"],
        ["ap", "approve"],
        ["ar", "approve"],
        ["apv", "approve"],
      ])("handles approval action prefix '%s' -> '%s'", async (prefix, expectedAction) => {
        const fetchMock = vi.fn().mockImplementation(async (url: string) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            return new Response(null, { status: 204 });
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 1,
          callback_query: {
            id: "cb_approval",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 555, chat: { id: 987654321 } },
            data: `${prefix}:post_xyz_123`,
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        const data = await res.json();
        expect(data).toEqual({
          status: "dispatched",
          action: expectedAction,
          item_id: "post_xyz_123",
        });

        // Verify GitHub dispatch payload
        const dispatchCall = fetchMock.mock.calls.find(([url]) => url.includes("/dispatches"));
        expect(dispatchCall).toBeDefined();
        const [dispatchUrl, dispatchOptions] = dispatchCall!;
        expect(dispatchUrl).toBe(
          `https://api.github.com/repos/${mockEnv.GITHUB_REPO_OWNER}/${mockEnv.GITHUB_REPO_NAME}/dispatches`
        );
        expect(dispatchOptions.headers["Authorization"]).toBe(
          `Bearer ${mockEnv.GITHUB_DISPATCH_PAT}`
        );
        const body = JSON.parse(dispatchOptions.body);
        expect(body).toEqual({
          event_type: "telegram-approval-action",
          client_payload: {
            action: expectedAction,
            item_id: "post_xyz_123",
            telegram_chat_id: 987654321,
            telegram_message_id: 555,
            telegram_callback_query_id: "cb_approval",
          },
        });
      });

      it.each([
        ["rc", "reject"],
        ["rp", "reject"],
        ["rej", "reject"],
      ])("handles rejection action prefix '%s' -> '%s'", async (prefix, expectedAction) => {
        const fetchMock = vi.fn().mockImplementation(async (url: string) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            return new Response(null, { status: 204 });
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 2,
          callback_query: {
            id: "cb_rejection",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 556, chat: { id: 987654321 } },
            data: `${prefix}:post_abc_456`,
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        const data = await res.json();
        expect(data).toEqual({
          status: "dispatched",
          action: expectedAction,
          item_id: "post_abc_456",
        });

        // Verify GitHub dispatch payload
        const dispatchCall = fetchMock.mock.calls.find(([url]) => url.includes("/dispatches"));
        expect(dispatchCall).toBeDefined();
        const [, dispatchOptions] = dispatchCall!;
        const body = JSON.parse(dispatchOptions.body);
        expect(body.client_payload.action).toBe("reject");
      });
    });

    describe("GitHub Dispatch Failure & Telegram Error Notification", () => {
      it.each([
        [401, "Unauthorized", '{"message":"Bad credentials"}'],
        [403, "Forbidden", '{"message":"Resource not accessible by personal access token"}'],
        [404, "Not Found", '{"message":"Not Found"}'],
        [422, "Unprocessable Entity", '{"message":"Validation Failed"}'],
        [500, "Internal Server Error", "Internal Server Error"],
      ])(
        "catches GitHub %i %s, edits Telegram message with error, and returns 502",
        async (statusCode, statusText, responseBody) => {
          let editMessageCalled = false;
          let editMessageBody: any = null;

          const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
            if (url.includes("answerCallbackQuery")) {
              return new Response("{}", { status: 200 });
            }
            if (url.includes("/dispatches")) {
              return new Response(responseBody, {
                status: statusCode,
                statusText,
              });
            }
            if (url.includes("editMessageText")) {
              editMessageCalled = true;
              editMessageBody = JSON.parse(opts.body);
              return new Response("{}", { status: 200 });
            }
            return new Response("Not found", { status: 404 });
          });
          globalThis.fetch = fetchMock;

          const req = makeRequest({
            update_id: 3,
            callback_query: {
              id: "cb_err",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 777, chat: { id: 987654321 } },
              data: "ac:item_err_1",
            },
          });
          const ctx = createMockContext();
          const res = await worker.fetch(req, mockEnv, ctx as any);

          // Assert 502 Bad Gateway response
          expect(res.status).toBe(502);
          const resJson = await res.json();
          expect(resJson).toEqual({
            error: "GitHub dispatch failed",
            status_code: statusCode,
            status_text: statusText,
            details: responseBody,
            action: "approve",
            item_id: "item_err_1",
          });

          // Assert ctx.waitUntil called with notifyTelegramFailure
          expect(ctx.waitUntil).toHaveBeenCalled();

          // Wait for any pending async operations passed to ctx.waitUntil
          await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));

          // Assert Telegram editMessageText was called
          expect(editMessageCalled).toBe(true);
          expect(editMessageBody).toEqual({
            chat_id: 987654321,
            message_id: 777,
            text: expect.stringContaining("⚠️ <b>GitHub Dispatch Failed</b>"),
            parse_mode: "HTML",
            link_preview_options: { is_disabled: true },
            reply_markup: { inline_keyboard: [] },
          });
          expect(editMessageBody.text).toContain(`<b>Item ID:</b> <code>item_err_1</code>`);
          expect(editMessageBody.text).toContain(`<b>Error:</b> <code>${statusCode} ${statusText}</code>`);
        }
      );

      it("catches network / DNS / fetch exception, edits Telegram message, and returns 502", async () => {
        let editMessageCalled = false;
        let editMessageBody: any = null;

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            throw new TypeError("fetch failed: connection refused");
          }
          if (url.includes("editMessageText")) {
            editMessageCalled = true;
            editMessageBody = JSON.parse(opts.body);
            return new Response("{}", { status: 200 });
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 4,
          callback_query: {
            id: "cb_net_err",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 888, chat: { id: 987654321 } },
            data: "ac:net_fail_item",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(502);
        const resJson = await res.json();
        expect(resJson).toEqual({
          error: "GitHub dispatch network failure",
          details: "fetch failed: connection refused",
          action: "approve",
          item_id: "net_fail_item",
        });

        // Wait for waitUntil promises
        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));

        expect(editMessageCalled).toBe(true);
        expect(editMessageBody.text).toContain("Network/Fetch Error");
        expect(editMessageBody.text).toContain("fetch failed: connection refused");
        expect(editMessageBody.reply_markup).toEqual({ inline_keyboard: [] });
      });

      it("handles fallback to sendMessage when message_id is not present", async () => {
        let sendMessageCalled = false;
        let sendMessageBody: any = null;

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            return new Response("Unauthorized", { status: 401, statusText: "Unauthorized" });
          }
          if (url.includes("sendMessage")) {
            sendMessageCalled = true;
            sendMessageBody = JSON.parse(opts.body);
            return new Response("{}", { status: 200 });
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        // Note: callback_query has no message object
        const req = makeRequest({
          update_id: 5,
          callback_query: {
            id: "cb_no_msg",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            data: "ac:item_no_msg",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(502);
        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));

        expect(sendMessageCalled).toBe(true);
        expect(sendMessageBody.chat_id).toBe(987654321);
        expect(sendMessageBody.text).toContain("GitHub Dispatch Failed");
      });

      it("returns 502 cleanly even if Telegram notification itself throws an error", async () => {
        const fetchMock = vi.fn().mockImplementation(async (url: string) => {
          if (url.includes("answerCallbackQuery")) {
            return new Response("{}", { status: 200 });
          }
          if (url.includes("/dispatches")) {
            return new Response("Server error", { status: 500, statusText: "Internal Server Error" });
          }
          if (url.includes("editMessageText")) {
            throw new Error("Telegram API outage");
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 6,
          callback_query: {
            id: "cb_tg_fail",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 999, chat: { id: 987654321 } },
            data: "ac:item_double_fail",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(502);
        const resJson = (await res.json()) as any;
        expect(resJson.error).toBe("GitHub dispatch failed");
        expect(resJson.status_code).toBe(500);

        // Ensure waitUntil promise doesn't throw unhandled rejection
        await expect(
          Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p))
        ).resolves.toBeDefined();
      });
    });

    describe("Direct Cloudflare KV Rejection Handling", () => {
      it("handles rejection directly in Worker via KV without GitHub Actions dispatch", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_kv_rej",
          JSON.stringify({ item_id: "item_kv_rej", action_type: "approve_comment" })
        );
        kvStore.set("history", JSON.stringify([{ item_id: "old_item", final_status: "expired" }]));

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) ?? null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
        };

        const envWithKv: Env = {
          ...mockEnv,
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 10,
          callback_query: {
            id: "cb_kv_rej_1",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 555, chat: { id: 987654321 } },
            data: "rej:item_kv_rej",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const resJson = (await res.json()) as any;
        expect(resJson.status).toBe("rejected_via_kv");
        expect(resJson.action).toBe("reject");
        expect(resJson.item_id).toBe("item_kv_rej");

        // Verify KV operations
        expect(mockKv.delete).toHaveBeenCalledWith("pending:item_kv_rej");
        expect(kvStore.has("pending:item_kv_rej")).toBe(false);
        expect(mockKv.put).toHaveBeenCalledWith("history", expect.any(String));

        const updatedHistory = JSON.parse(kvStore.get("history")!);
        expect(updatedHistory).toHaveLength(2);
        expect(updatedHistory[1].item_id).toBe("item_kv_rej");
        expect(updatedHistory[1].final_status).toBe("rejected");
        expect(updatedHistory[1].action_type).toBe("approve_comment");

        // Verify Telegram message was edited to "❌ Suggestion rejected"
        expect(fetchMock).toHaveBeenCalledWith(
          `https://api.telegram.org/bot${mockEnv.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`,
          expect.objectContaining({
            method: "POST",
            body: expect.stringContaining("❌ Suggestion rejected"),
          })
        );
        expect(fetchMock).toHaveBeenCalledWith(
          `https://api.telegram.org/bot${mockEnv.TELEGRAM_BOT_TOKEN}/editMessageText`,
          expect.objectContaining({
            method: "POST",
            body: expect.stringContaining("❌ Suggestion rejected"),
          })
        );

        // Verify NO call was made to GitHub Actions API
        const githubCalls = fetchMock.mock.calls.filter(([url]: [string]) =>
          url.includes("api.github.com")
        );
        expect(githubCalls).toHaveLength(0);
      });

      it("still dispatches approvals to GitHub Actions even when KV is configured", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const mockKv = {
          get: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        };

        const envWithKv: Env = {
          ...mockEnv,
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 11,
          callback_query: {
            id: "cb_kv_app_1",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 556, chat: { id: 987654321 } },
            data: "ac:item_kv_app",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const resJson = (await res.json()) as any;
        expect(resJson.status).toBe("dispatched");

        // GitHub Actions API WAS called
        const githubCalls = fetchMock.mock.calls.filter(([url]: [string]) =>
          url.includes("api.github.com")
        );
        expect(githubCalls).toHaveLength(1);
      });

      it("handles 'rr' fast-path rejection via KV with approve_reply fallback action_type", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
          list: vi.fn(async () => ({ keys: [] })),
        };
        const envWithKv = {
          ...mockEnv,
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 12,
          callback_query: {
            id: "cb_kv_rr_1",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 557, chat: { id: 987654321 } },
            data: "rr:reply_item_123",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const resJson = (await res.json()) as any;
        expect(resJson.status).toBe("rejected_via_kv");
        expect(resJson.item_id).toBe("reply_item_123");

        const updatedHistory = JSON.parse(kvStore.get("history")!);
        expect(updatedHistory[0].action_type).toBe("approve_reply");
        expect(updatedHistory[0].final_status).toBe("rejected");
      });
    });

    describe("Operator Commands", () => {
      it("rejects commands from unauthorized senders with 403", async () => {
        const req = makeRequest({
          update_id: 100,
          message: {
            message_id: 1,
            from: { id: 111111111 },
            chat: { id: 111111111 },
            text: "/status",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(403);
      });

      it("handles /status command from authorized operator", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set("daily_counters", JSON.stringify({ comments_executed: 3, posts_executed: 1 }));
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
          list: vi.fn(async () => ({ keys: [{ name: "pending:item1" }] })),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 101,
          message: {
            message_id: 200,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/status",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("status");

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const payload = JSON.parse(sendCall![1].body);
        expect(payload.text).toContain("Agent Status Report");
        expect(payload.text).toContain("Comments Executed:</b> 3");
      });

      it("handles /pause command and sets paused in KV", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 102,
          message: {
            message_id: 201,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/pause",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("pause");
        expect(kvStore.has("paused")).toBe(true);
      });

      it("handles /resume command and deletes paused in KV", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set("paused", JSON.stringify({ paused_at: new Date().toISOString() }));
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 103,
          message: {
            message_id: 202,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/resume",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("resume");
        expect(kvStore.has("paused")).toBe(false);
      });

      it("handles /clear_incident command and clears incident in KV", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set("incident", JSON.stringify({ reason: "Bot challenge" }));
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          delete: vi.fn(async (key: string) => {
            kvStore.delete(key);
          }),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 104,
          message: {
            message_id: 203,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/clear_incident",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("clear_incident");
        expect(kvStore.has("incident")).toBe(false);
      });
    });
  });
});
