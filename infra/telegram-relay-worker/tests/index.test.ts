import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, {
  escapeHtml,
  formatTelegramErrorMessage,
  notifyTelegramFailure,
  getSuggestionKeyboard,
  getEditingKeyboard,
  getRegeneratingKeyboard,
  getPendingListKeyboard,
  getStatusKeyboard,
  getHomeKeyboard,
  getStatsKeyboard,
  getHelpKeyboard,
  formatHomeHub,
  formatRejectionCard,
  getDockedReplyKeyboard,
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
        ["acon", "approve"],
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
        ["rr", "reject"],
        ["rej", "reject"],
        ["rcon", "reject"],
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

      it.each([
        ["reg", "tone_menu_displayed", "draft tone style"],
        ["ed", "edit_prompted", "revised draft text"],
        ["edit", "edit_prompted", "revised draft text"],
      ])("handles '%s' callback by answering callback query with guidance", async (code, expectedStatus, expectedTextMatch) => {
        let answeredQuery = false;
        let answeredText = "";

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            answeredQuery = true;
            const parsed = JSON.parse(opts.body);
            answeredText = parsed.text;
            return new Response("{}", { status: 200 });
          }
          return new Response("Not found", { status: 404 });
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 3,
          callback_query: {
            id: "cb_tone",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 678, chat: { id: 987654321 } },
            data: `${code}:item_xyz_789`,
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        const data = await res.json() as any;
        expect(data.status).toBe(expectedStatus);
        expect(data.item_id).toBe("item_xyz_789");
        expect(answeredQuery).toBe(true);
        expect(answeredText).toContain(expectedTextMatch);
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

      it("handles /help and /start commands returning operator command reference", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const req = makeRequest({
          update_id: 105,
          message: {
            message_id: 204,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/help",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("help");

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const payload = JSON.parse(sendCall![1].body);
        expect(payload.text).toContain("LinkedAide - Operator Commands");
        expect(payload.text).toContain("/status");
        expect(payload.text).toContain("/pending");
        expect(payload.text).toContain("/stats");
        expect(payload.text).toContain("/tone");
      });

      it("handles /stats command displaying daily counts and historical success metrics", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "daily_counters",
          JSON.stringify({
            date: "2026-10-05",
            comments_executed: 4,
            posts_executed: 2,
            connections_sent: 5,
            suggestions_sent: 12,
          })
        );
        kvStore.set(
          "history",
          JSON.stringify([
            { item_id: "h1", final_status: "executed_success" },
            { item_id: "h2", final_status: "executed_success" },
            { item_id: "h3", final_status: "rejected" },
            { item_id: "h4", final_status: "expired" },
          ])
        );

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 106,
          message: {
            message_id: 205,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/stats",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("stats");

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const payload = JSON.parse(sendCall![1].body);
        expect(payload.text).toContain("Agent Performance &amp; Execution Stats");
        expect(payload.text).toContain("Comments Published:</b> 4");
        expect(payload.text).toContain("Connections Sent:</b> 5");
        expect(payload.text).toContain("Executed Actions:</b> 2");
        expect(payload.text).toContain("Operator Rejections:</b> 1");
        expect(payload.text).toContain("66.7%"); // 2 / (2 + 1)
      });

      it("handles /pending command when queue is empty", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const mockKv = {
          list: vi.fn(async () => ({ keys: [] })),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 107,
          message: {
            message_id: 206,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/pending",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("pending");
        expect(data.count).toBe(0);

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const payload = JSON.parse(sendCall![1].body);
        expect(payload.text).toContain("No Pending Actions");
      });

      it("handles /pending command when items are awaiting review in KV", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_c1",
          JSON.stringify({
            item_id: "item_c1",
            action_type: "comment",
            author: "Alice Researcher",
            draft_text: "Deterministic state machines avoid unbounded agent execution loops.",
          })
        );
        kvStore.set(
          "pending:item_conn1",
          JSON.stringify({
            item_id: "item_conn1",
            action_type: "connect",
            recipient_name: "Bob Founder",
            note: "Loved your recent deep dive on LLM safety guardrails.",
          })
        );

        const mockKv = {
          list: vi.fn(async () => ({
            keys: [{ name: "pending:item_c1" }, { name: "pending:item_conn1" }],
          })),
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 108,
          message: {
            message_id: 207,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/pending",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("command_handled");
        expect(data.command).toBe("pending");
        expect(data.count).toBe(2);

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const payload = JSON.parse(sendCall![1].body);
        expect(payload.text).toContain("Pending Approval Queue (2)");
        expect(payload.text).toContain("Alice Researcher");
        expect(payload.text).toContain("Bob Founder");
        expect(payload.text).toContain("item_c1");
        expect(payload.text).toContain("item_conn1");
      });
    });

    describe("Interactive Draft Edits & Tone Regenerations", () => {
      it("handles operator reply to suggestion card with manual draft text", async () => {
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_msg_101",
          JSON.stringify({
            item_id: "item_msg_101",
            telegram_message_id: 555,
            telegram_chat_id: 987654321,
            draft_text: "Original AI draft before manual adjustment.",
            author_name: "Tech Leader",
            action_type: "approve_comment",
          })
        );

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          list: vi.fn(async () => ({ keys: [{ name: "pending:item_msg_101" }] })),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 110,
          message: {
            message_id: 999,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            reply_to_message: {
              message_id: 555,
              text: "Original suggestion message",
            },
            text: "Operator polished replacement comment for the thread.",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data).toEqual({
          status: "draft_updated",
          item_id: "item_msg_101",
          mode: "manual_edit",
          tone: null,
        });

        // Verify KV was updated with operator draft
        const updated = JSON.parse(kvStore.get("pending:item_msg_101")!);
        expect(updated.draft_text).toBe("Operator polished replacement comment for the thread.");

        // Verify editMessageText and confirmation reply
        const editCall = fetchMock.mock.calls.find(([url]) => url.includes("/editMessageText"));
        expect(editCall).toBeDefined();
        const editPayload = JSON.parse(editCall![1].body);
        expect(editPayload.message_id).toBe(555);
        expect(editPayload.text).toContain("Operator polished replacement comment");

        const sendCall = fetchMock.mock.calls.find(([url]) => url.includes("/sendMessage"));
        expect(sendCall).toBeDefined();
        const sendPayload = JSON.parse(sendCall![1].body);
        expect(sendPayload.text).toContain("Draft Updated");
      });

      it("handles operator reply to suggestion card with tone rewrite command", async () => {
        const mockRewritten = "A concise, punchy distillation of verification guardrails.";
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("/chat/completions")) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  choices: [{ message: { content: mockRewritten } }],
                }),
                { status: 200 }
              )
            );
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_msg_102",
          JSON.stringify({
            item_id: "item_msg_102",
            telegram_message_id: 556,
            telegram_chat_id: 987654321,
            draft_text: "A longer conversational paragraph explaining agent pipelines.",
            author_name: "AI Researcher",
            action_type: "approve_comment",
          })
        );

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
          list: vi.fn(async () => ({ keys: [{ name: "pending:item_msg_102" }] })),
        };
        const envWithKv = {
          ...mockEnv,
          NVIDIA_NIM_API_KEY: "test-nim-key",
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 111,
          message: {
            message_id: 1000,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            reply_to_message: {
              message_id: 556,
              text: "Original card text",
            },
            text: "/tone concise",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data).toEqual({
          status: "draft_updated",
          item_id: "item_msg_102",
          mode: "regenerate",
          tone: "concise",
        });

        // Verify KV was updated with LLM rewritten text
        const updated = JSON.parse(kvStore.get("pending:item_msg_102")!);
        expect(updated.draft_text).toBe(mockRewritten);
      });

      it("handles direct /edit command with item_id and draft text", async () => {
        const fetchMock = vi.fn().mockImplementation(() => {
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_msg_103",
          JSON.stringify({
            item_id: "item_msg_103",
            telegram_message_id: 557,
            draft_text: "Old text",
          })
        );

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
        };
        const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

        const req = makeRequest({
          update_id: 112,
          message: {
            message_id: 1001,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/edit item_msg_103 Completely replaced comment draft.",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("draft_updated");
        expect(data.item_id).toBe("item_msg_103");

        const updated = JSON.parse(kvStore.get("pending:item_msg_103")!);
        expect(updated.draft_text).toBe("Completely replaced comment draft.");
      });

      it("handles direct /tone command with item_id and tone", async () => {
        const mockRewritten = "Technical breakdown of distributed execution guarantees.";
        const fetchMock = vi.fn().mockImplementation((url: string) => {
          if (url.includes("/chat/completions")) {
            return Promise.resolve(
              new Response(
                JSON.stringify({
                  choices: [{ message: { content: mockRewritten } }],
                }),
                { status: 200 }
              )
            );
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_msg_104",
          JSON.stringify({
            item_id: "item_msg_104",
            telegram_message_id: 558,
            draft_text: "General discussion about architectures.",
          })
        );

        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) || null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
        };
        const envWithKv = {
          ...mockEnv,
          NVIDIA_NIM_API_KEY: "test-nim-key",
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 113,
          message: {
            message_id: 1002,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/tone item_msg_104 technical",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const data = (await res.json()) as any;
        expect(data.status).toBe("draft_updated");
        expect(data.item_id).toBe("item_msg_104");
        expect(data.tone).toBe("technical");

        const updated = JSON.parse(kvStore.get("pending:item_msg_104")!);
        expect(updated.draft_text).toBe(mockRewritten);
      });
    });

    describe("Phase 1 Interactive Rejection Confirmation & Dynamic Tone Menus", () => {
      it("handles 'ask_rej' by prompting for rejection confirmation without deleting state", async () => {
        let editedMarkup: any = null;
        let answeredText = "";
        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            answeredText = JSON.parse(opts.body).text;
            return new Response("{}", { status: 200 });
          }
          if (url.includes("editMessageReplyMarkup")) {
            editedMarkup = JSON.parse(opts.body).reply_markup;
            return new Response("{}", { status: 200 });
          }
          return new Response("{}", { status: 200 });
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_confirm_1",
          JSON.stringify({ item_id: "item_confirm_1", action_type: "approve_comment" })
        );

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
          update_id: 120,
          callback_query: {
            id: "cb_ask_rej_1",
            from: { id: 987654321 },
            message: { message_id: 777, chat: { id: 987654321 } },
            data: "ask_rej:item_confirm_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("reject_confirmation_prompted");
        expect(json.item_id).toBe("item_confirm_1");

        // Pending item is NOT deleted
        expect(kvStore.has("pending:item_confirm_1")).toBe(true);

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(answeredText).toContain("Confirm rejection");
        expect(editedMarkup).toBeDefined();
        expect(editedMarkup.inline_keyboard[0][0].callback_data).toBe("cf_rej:item_confirm_1");
        expect(editedMarkup.inline_keyboard[0][1].callback_data).toBe("cx_rej:item_confirm_1");
      });

      it("handles 'cx_rej' by cancelling rejection and restoring suggestion keyboard", async () => {
        let editedMarkup: any = null;
        let answeredText = "";
        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            answeredText = JSON.parse(opts.body).text;
            return new Response("{}", { status: 200 });
          }
          if (url.includes("editMessageReplyMarkup")) {
            editedMarkup = JSON.parse(opts.body).reply_markup;
            return new Response("{}", { status: 200 });
          }
          return new Response("{}", { status: 200 });
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_cancel_1",
          JSON.stringify({ item_id: "item_cancel_1", action_type: "approve_comment" })
        );

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
          update_id: 121,
          callback_query: {
            id: "cb_cx_rej_1",
            from: { id: 987654321 },
            message: { message_id: 778, chat: { id: 987654321 } },
            data: "cx_rej:item_cancel_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("reject_cancelled");

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(answeredText).toContain("Rejection cancelled");
        expect(editedMarkup).toBeDefined();
        expect(editedMarkup.inline_keyboard[0][0].callback_data).toBe("ac:item_cancel_1");
        expect(editedMarkup.inline_keyboard[0][1].callback_data).toBe("ask_rej:item_cancel_1");
      });

      it("handles 'cf_rej' by deleting KV item and presenting feedback buttons", async () => {
        let editedBody: any = null;
        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("editMessageText")) {
            editedBody = JSON.parse(opts.body);
            return new Response("{}", { status: 200 });
          }
          return new Response("{}", { status: 200 });
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_cf_1",
          JSON.stringify({ item_id: "item_cf_1", action_type: "approve_comment" })
        );

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
          update_id: 122,
          callback_query: {
            id: "cb_cf_rej_1",
            from: { id: 987654321 },
            message: { message_id: 779, chat: { id: 987654321 } },
            data: "cf_rej:item_cf_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("rejected_via_kv");
        expect(kvStore.has("pending:item_cf_1")).toBe(false);

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(editedBody).toBeDefined();
        expect(editedBody.text).toContain("Why was this suggestion rejected?");
        expect(editedBody.reply_markup.inline_keyboard[0][0].callback_data).toBe("fb:generic:item_cf_1");
        expect(editedBody.reply_markup.inline_keyboard[2][0].callback_data).toBe("fb:skip:item_cf_1");
      });

      it("handles 'fb:generic' by saving feedback in KV and clearing keyboard", async () => {
        let editedBody: any = null;
        let answeredText = "";
        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("answerCallbackQuery")) {
            answeredText = JSON.parse(opts.body).text;
            return new Response("{}", { status: 200 });
          }
          if (url.includes("editMessageText")) {
            editedBody = JSON.parse(opts.body);
            return new Response("{}", { status: 200 });
          }
          return new Response("{}", { status: 200 });
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
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
          update_id: 123,
          callback_query: {
            id: "cb_fb_1",
            from: { id: 987654321 },
            message: { message_id: 780, chat: { id: 987654321 } },
            data: "fb:generic:item_fb_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("feedback_recorded");
        expect(json.reason).toBe("generic");

        // Verify stored in KV
        const savedFb = JSON.parse(kvStore.get("rejection_feedback")!);
        expect(savedFb).toHaveLength(1);
        expect(savedFb[0].reason).toBe("generic");

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(answeredText).toContain("Feedback saved (generic)");
        expect(editedBody.reply_markup.inline_keyboard).toEqual([]);
      });

      it("handles 'tone:contrarian' callback by rewriting draft with LLM and updating card", async () => {
        let editedBody: any = null;
        let answeredText = "";
        const mockRewritten = "Actually, multi-agent frameworks introduce unbounded token loops unless constrained.";

        const fetchMock = vi.fn().mockImplementation(async (url: string, opts: any) => {
          if (url.includes("/chat/completions")) {
            return new Response(
              JSON.stringify({
                choices: [{ message: { content: mockRewritten } }],
              }),
              { status: 200 }
            );
          }
          if (url.includes("answerCallbackQuery")) {
            answeredText = JSON.parse(opts.body).text;
            return new Response("{}", { status: 200 });
          }
          if (url.includes("editMessageText")) {
            editedBody = JSON.parse(opts.body);
            return new Response("{}", { status: 200 });
          }
          return new Response("{}", { status: 200 });
        });
        globalThis.fetch = fetchMock;

        const kvStore = new Map<string, string>();
        kvStore.set(
          "pending:item_tone_cb_1",
          JSON.stringify({
            item_id: "item_tone_cb_1",
            action_type: "approve_comment",
            draft_text: "Original draft",
            author_name: "Tech Leader",
          })
        );

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
          NVIDIA_NIM_API_KEY: "test-nim-key",
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        const req = makeRequest({
          update_id: 124,
          callback_query: {
            id: "cb_tone_sel_1",
            from: { id: 987654321 },
            message: { message_id: 781, chat: { id: 987654321 } },
            data: "tone:contrarian:item_tone_cb_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);

        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("draft_updated");
        expect(json.tone).toBe("contrarian");

        const updatedPending = JSON.parse(kvStore.get("pending:item_tone_cb_1")!);
        expect(updatedPending.draft_text).toBe(mockRewritten);

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(answeredText).toContain("contrarian");
        expect(editedBody.text).toContain(mockRewritten);
        expect(editedBody.reply_markup.inline_keyboard[0][0].callback_data).toBe("ac:item_tone_cb_1");
      });
    });

    describe("Phase 2 Persistent Docked Reply Keyboard Navigation", () => {
      it("routes '📊 Status' docked button tap to status command", async () => {
        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 130,
          message: {
            message_id: 801,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "📊 Status",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("status");

        expect(sentPayload).not.toBeNull();
        expect(sentPayload.text).toContain("Agent Status Report");
        expect(sentPayload.reply_markup).toBeDefined();
        expect(sentPayload.reply_markup.keyboard[0][0].text).toBe("📊 Status");
      });

      it("routes '⏸️ Pause' docked button tap to pause command", async () => {
        const kvStore = new Map<string, string>();
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

        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 131,
          message: {
            message_id: 802,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "⏸️ Pause",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("pause");

        expect(sentPayload.text).toContain("Agent Paused");
        expect(sentPayload.reply_markup.keyboard[1][0].text).toBe("▶️ Resume");
      });
    });

    describe("Phase 5 On-Demand Mobile Creation & Voice Notes", () => {
      it("handles /post with idea: generates draft, saves to KV, and delivers approval card", async () => {
        const kvStore = new Map<string, string>();
        const mockKv = {
          get: vi.fn(async (key: string) => kvStore.get(key) ?? null),
          put: vi.fn(async (key: string, val: string) => {
            kvStore.set(key, val);
          }),
        };

        const envWithKv: Env = {
          ...mockEnv,
          LINKEDIN_AGENT_KV: mockKv as any,
        };

        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(
              new Response(JSON.stringify({ ok: true, result: { message_id: 888 } }), { status: 200 })
            );
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 140,
          message: {
            message_id: 810,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/post 3 subtle pitfalls when building production agentic loops",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);
        const json = (await res.json()) as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("post");
        expect(json.item_id).toBeDefined();

        expect(sentPayload).not.toBeNull();
        expect(sentPayload.text).toContain("Original Post");
        expect(sentPayload.reply_markup.inline_keyboard[0][0].text).toBe("✅ Approve");
        expect(sentPayload.reply_markup.inline_keyboard[0][0].callback_data).toBe(`ap:${json.item_id}`);

        const savedPending = JSON.parse(kvStore.get(`pending:${json.item_id}`)!);
        expect(savedPending.action_type).toBe("approve_post");
        expect(savedPending.telegram_message_id).toBe(888);
      });

      it("handles /post with empty prompt: sends guidance message", async () => {
        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 141,
          message: {
            message_id: 811,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/post",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = (await res.json()) as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("post");
        expect(json.prompt).toBe(true);

        expect(sentPayload.text).toContain("Draft an Original Post");
        expect(sentPayload.text).toContain("Provide an idea or topic");
      });

      it("handles /scout with target url: confirms and triggers GitHub repository_dispatch", async () => {
        let sentPayload: any = null;
        let dispatchCalled = false;
        let dispatchBody: any = null;

        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          if (url.includes("dispatches")) {
            dispatchCalled = true;
            dispatchBody = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 204 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const envWithGh: Env = {
          ...mockEnv,
          GITHUB_DISPATCH_PAT: "ghp_mock_token_123",
          GITHUB_REPO_OWNER: "test-owner",
          GITHUB_REPO_NAME: "test-repo",
        };

        const targetUrl = "https://www.linkedin.com/feed/update/urn:li:activity:9988776655/";
        const req = makeRequest({
          update_id: 142,
          message: {
            message_id: 812,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: `/scout ${targetUrl}`,
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithGh, ctx as any);
        expect(res.status).toBe(200);
        const json = (await res.json()) as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("scout");
        expect(json.target_url).toBe(targetUrl);

        expect(sentPayload.text).toContain("Target Received");
        expect(sentPayload.text).toContain(targetUrl);

        await Promise.all(ctx.waitUntil.mock.calls.map(([p]) => p));
        expect(dispatchCalled).toBe(true);
        expect(dispatchBody.event_type).toBe("scout-target");
        expect(dispatchBody.client_payload.target_url).toBe(targetUrl);
      });

      it("handles /scout with empty prompt: sends guidance message", async () => {
        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 143,
          message: {
            message_id: 813,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            text: "/scout",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = (await res.json()) as any;
        expect(json.status).toBe("command_handled");
        expect(json.command).toBe("scout");
        expect(json.prompt).toBe(true);

        expect(sentPayload.text).toContain("On-Demand Target Scouting");
      });

      it("acknowledges incoming voice note update", async () => {
        let sentPayload: any = null;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("sendMessage")) {
            sentPayload = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
        });

        const req = makeRequest({
          update_id: 144,
          message: {
            message_id: 814,
            from: { id: 987654321 },
            chat: { id: 987654321 },
            voice: { file_id: "voice_file_abc", duration: 15 },
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = (await res.json()) as any;
        expect(json.status).toBe("voice_acknowledged");

        expect(sentPayload.text).toContain("Voice Note Received");
        expect(sentPayload.text).toContain("/post");
      });
    });

    describe("Keyboard UX & Callback Enhancements", () => {
      it("constructs suggestion keyboard with one-tap LinkedIn URL button", () => {
        const kbWithUrl = getSuggestionKeyboard(
          "item_123",
          "approve_comment",
          "https://linkedin.com/feed/update/urn:li:activity:123"
        );
        expect(kbWithUrl.inline_keyboard[0][0]).toEqual({
          text: "🔗 View Post on LinkedIn",
          url: "https://linkedin.com/feed/update/urn:li:activity:123",
        });
        expect(kbWithUrl.inline_keyboard[1][0].text).toBe("✅ Approve");

        const kbWithoutUrl = getSuggestionKeyboard("item_123", "approve_comment");
        expect(kbWithoutUrl.inline_keyboard[0][0].text).toBe("✅ Approve");
      });

      it("constructs editing keyboard with cancel edit and home buttons", () => {
        const kb = getEditingKeyboard("item_123");
        expect(kb.inline_keyboard).toEqual([
          [
            { text: "❌ Cancel Edit", callback_data: "cx_ed:item_123" },
            { text: "🏠 Home Menu", callback_data: "home:menu" },
          ],
        ]);
      });

      it("constructs regenerating keyboard with loading indicator", () => {
        const kb = getRegeneratingKeyboard("item_123");
        expect(kb.inline_keyboard).toEqual([
          [{ text: "⏳ Generating with AI...", callback_data: "noop:item_123" }],
        ]);
      });

      it("constructs pending list keyboard with review buttons up to limit and nav footer", () => {
        const items = [
          { item_id: "act_111", action_type: "approve_comment" },
          { item_id: "act_222", action_type: "approve_post" },
        ];
        const kb = getPendingListKeyboard(items);
        expect(kb.inline_keyboard).toHaveLength(3);
        expect(kb.inline_keyboard[0][0].text).toContain("💬 Review #1 (act_11)");
        expect(kb.inline_keyboard[0][0].callback_data).toBe("rev:act_111");
        expect(kb.inline_keyboard[1][0].text).toContain("📝 Review #2 (act_22)");
        expect(kb.inline_keyboard[1][0].callback_data).toBe("rev:act_222");
        expect(kb.inline_keyboard[2][0].callback_data).toBe("refresh:pending");
        expect(kb.inline_keyboard[2][1].callback_data).toBe("home:menu");

        const kbWithoutNav = getPendingListKeyboard(items, 5, false);
        expect(kbWithoutNav.inline_keyboard).toHaveLength(2);
      });

      it("constructs status keyboard with reset cb, pending count, and nav footer", () => {
        const trippedKb = getStatusKeyboard(true, 3);
        expect(trippedKb.inline_keyboard).toHaveLength(3);
        expect(trippedKb.inline_keyboard[0][0].callback_data).toBe("reset_cb:global");
        expect(trippedKb.inline_keyboard[1][0].text).toContain("Review Pending (3)");
        expect(trippedKb.inline_keyboard[2][0].callback_data).toBe("refresh:status");
        expect(trippedKb.inline_keyboard[2][1].callback_data).toBe("home:menu");

        const normalKb = getStatusKeyboard(false, 0, false);
        expect(normalKb.inline_keyboard).toHaveLength(0);

        const normalKbWithNav = getStatusKeyboard(false, 0, true);
        expect(normalKbWithNav.inline_keyboard).toHaveLength(1);
        expect(normalKbWithNav.inline_keyboard[0][1].callback_data).toBe("home:menu");
      });

      it("includes input_field_placeholder on docked reply keyboard", () => {
        const kb = getDockedReplyKeyboard(false);
        expect(kb.input_field_placeholder).toBe("Tap a button or type /help...");
      });

      it("formats rejection card preserving post context and author", () => {
        const card = formatRejectionCard(
          {
            item_id: "item_999",
            action_type: "approve_comment",
            author_name: "Alice Engineer",
            post_url: "https://linkedin.com/posts/alice",
            draft_text: "Insightful perspectives on scalable systems.",
          },
          "Too generic"
        );
        expect(card).toContain("❌ Suggestion rejected by operator");
        expect(card).toContain("Alice Engineer");
        expect(card).toContain("https://linkedin.com/posts/alice");
        expect(card).toContain("Insightful perspectives on scalable systems.");
        expect(card).toContain("Too generic");
      });

      it("handles cx_ed callback by cancelling edit and restoring suggestion markup", async () => {
        let editedMarkup: any = null;
        let answeredQuery = false;
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("editMessageReplyMarkup")) {
            editedMarkup = JSON.parse(init?.body as string);
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          if (url.includes("answerCallbackQuery")) {
            answeredQuery = true;
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response("Not found", { status: 404 }));
        });

        const req = makeRequest({
          update_id: 150,
          callback_query: {
            id: "cb_cx_ed",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 991, chat: { id: 987654321 } },
            data: "cx_ed:item_cancel_1",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("edit_cancelled");
        expect(answeredQuery).toBe(true);
        expect(editedMarkup).toBeDefined();
        expect(editedMarkup.reply_markup.inline_keyboard[0][0].text).toBe("✅ Approve");
      });

      it("handles reset_cb callback by deleting incident and editing message", async () => {
        let deletedKey = "";
        const kvMock: any = {
          delete: vi.fn(async (key: string) => {
            deletedKey = key;
          }),
        };
        const envWithKv: Env = { ...mockEnv, LINKEDIN_AGENT_KV: kvMock };

        let editedText = "";
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("editMessageText")) {
            const body = JSON.parse(init?.body as string);
            editedText = body.text;
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          if (url.includes("answerCallbackQuery")) {
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response("Not found", { status: 404 }));
        });

        const req = makeRequest({
          update_id: 151,
          callback_query: {
            id: "cb_reset_cb",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 992, chat: { id: 987654321 } },
            data: "reset_cb:global",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, envWithKv, ctx as any);
        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("circuit_breaker_reset");
        expect(deletedKey).toBe("incident");
        expect(editedText).toContain("Circuit Breaker Reset");
      });

      it("handles noop callback with loading guidance", async () => {
        let toastText = "";
        globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
          if (url.includes("answerCallbackQuery")) {
            const body = JSON.parse(init?.body as string);
            toastText = body.text;
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          }
          return Promise.resolve(new Response("Not found", { status: 404 }));
        });

        const req = makeRequest({
          update_id: 152,
          callback_query: {
            id: "cb_noop",
            from: { id: 987654321, is_bot: false, first_name: "Operator" },
            message: { message_id: 993, chat: { id: 987654321 } },
            data: "noop:item_123",
          },
        });
        const ctx = createMockContext();
        const res = await worker.fetch(req, mockEnv, ctx as any);
        expect(res.status).toBe(200);
        const json = await res.json() as any;
        expect(json.status).toBe("noop_acknowledged");
        expect(toastText).toContain("Generating draft with AI");
      });

      describe("Universal Home Menu, Back/Cancel, and Refresh Navigation", () => {
        it("constructs home, stats, and help keyboards and formats hub html", () => {
          const homeKb = getHomeKeyboard(false, 3, false);
          expect(homeKb.inline_keyboard).toHaveLength(3);
          expect(homeKb.inline_keyboard[0][0].callback_data).toBe("rev:list");
          expect(homeKb.inline_keyboard[0][1].callback_data).toBe("refresh:status");
          expect(homeKb.inline_keyboard[1][0].callback_data).toBe("refresh:stats");
          expect(homeKb.inline_keyboard[1][1].text).toContain("Pause Agent");
          expect(homeKb.inline_keyboard[1][1].callback_data).toBe("home:pause");
          expect(homeKb.inline_keyboard[2][0].callback_data).toBe("refresh:home");
          expect(homeKb.inline_keyboard[2][1].callback_data).toBe("close:menu");

          const homeKbPaused = getHomeKeyboard(true, 0, true);
          expect(homeKbPaused.inline_keyboard).toHaveLength(4);
          expect(homeKbPaused.inline_keyboard[0][0].callback_data).toBe("reset_cb:global");
          expect(homeKbPaused.inline_keyboard[2][1].text).toContain("Resume Agent");
          expect(homeKbPaused.inline_keyboard[2][1].callback_data).toBe("home:resume");

          const statsKb = getStatsKeyboard();
          expect(statsKb.inline_keyboard[0][0].callback_data).toBe("refresh:stats");
          expect(statsKb.inline_keyboard[0][1].callback_data).toBe("home:menu");

          const helpKb = getHelpKeyboard();
          expect(helpKb.inline_keyboard[0][0].callback_data).toBe("home:menu");
          expect(helpKb.inline_keyboard[0][1].callback_data).toBe("refresh:status");

          const hubHtml = formatHomeHub(
            "🟢 Operational",
            "🟢 Normal",
            2,
            { comments_executed: 5, posts_executed: 1, suggestions_sent: 8, date: "2026-10-07" },
            ["AI Agents", "Autonomous Systems"]
          );
          expect(hubHtml).toContain("Command &amp; Control Hub");
          expect(hubHtml).toContain("Operational");
          expect(hubHtml).toContain("Comments:</b> 5");
          expect(hubHtml).toContain("AI Agents, Autonomous Systems");
        });

        it("routes '🏠 Home Menu' docked button tap to home command", async () => {
          let sentPayload: any = null;
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes("sendMessage")) {
              sentPayload = JSON.parse(init?.body as string);
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          });

          const req = makeRequest({
            update_id: 160,
            message: {
              message_id: 850,
              from: { id: 987654321 },
              chat: { id: 987654321 },
              text: "🏠 Home Menu",
            },
          });
          const ctx = createMockContext();
          const res = await worker.fetch(req, mockEnv, ctx as any);
          expect(res.status).toBe(200);
          const json = (await res.json()) as any;
          expect(json.status).toBe("command_handled");
          expect(json.command).toBe("home");

          expect(sentPayload).not.toBeNull();
          expect(sentPayload.text).toContain("Command &amp; Control Hub");
          expect(sentPayload.reply_markup).toBeDefined();
          expect(sentPayload.reply_markup.inline_keyboard[2][1].callback_data).toBe("close:menu");
        });

        it("handles /home command returning Command & Control hub with interactive keyboard", async () => {
          let sentPayload: any = null;
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes("sendMessage")) {
              sentPayload = JSON.parse(init?.body as string);
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
          });

          const req = makeRequest({
            update_id: 161,
            message: {
              message_id: 851,
              from: { id: 987654321 },
              chat: { id: 987654321 },
              text: "/home",
            },
          });
          const ctx = createMockContext();
          const res = await worker.fetch(req, mockEnv, ctx as any);
          expect(res.status).toBe(200);
          const json = (await res.json()) as any;
          expect(json.status).toBe("command_handled");
          expect(json.command).toBe("home");

          expect(sentPayload.text).toContain("Command &amp; Control Hub");
          expect(sentPayload.reply_markup.inline_keyboard).toBeDefined();
        });

        it("handles home:pause and home:resume callbacks toggling agent pause state", async () => {
          const kvStore = new Map<string, string>();
          const mockKv = {
            get: vi.fn(async (key: string) => kvStore.get(key) ?? null),
            put: vi.fn(async (key: string, val: string) => {
              kvStore.set(key, val);
            }),
            delete: vi.fn(async (key: string) => {
              kvStore.delete(key);
            }),
            list: vi.fn(async () => ({ keys: [] })),
          };
          const envWithKv = { ...mockEnv, LINKEDIN_AGENT_KV: mockKv as any };

          let answeredToast = "";
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes("answerCallbackQuery")) {
              const body = JSON.parse(init?.body as string);
              answeredToast = body.text;
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            if (url.includes("editMessageText")) {
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            return Promise.resolve(new Response("Not found", { status: 404 }));
          });

          // 1. Pause
          const reqPause = makeRequest({
            update_id: 162,
            callback_query: {
              id: "cb_pause",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 852, chat: { id: 987654321 } },
              data: "home:pause",
            },
          });
          const resPause = await worker.fetch(reqPause, envWithKv, createMockContext() as any);
          expect(resPause.status).toBe(200);
          const jsonPause = (await resPause.json()) as any;
          expect(jsonPause.status).toBe("home_displayed");
          expect(jsonPause.sub_action).toBe("pause");
          expect(kvStore.has("paused")).toBe(true);
          expect(answeredToast).toContain("Agent paused");

          // 2. Resume
          const reqResume = makeRequest({
            update_id: 163,
            callback_query: {
              id: "cb_resume",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 853, chat: { id: 987654321 } },
              data: "home:resume",
            },
          });
          const resResume = await worker.fetch(reqResume, envWithKv, createMockContext() as any);
          expect(resResume.status).toBe(200);
          const jsonResume = (await resResume.json()) as any;
          expect(jsonResume.status).toBe("home_displayed");
          expect(jsonResume.sub_action).toBe("resume");
          expect(kvStore.has("paused")).toBe(false);
          expect(answeredToast).toContain("Agent resumed");
        });

        it("handles close:menu callback by deleting message", async () => {
          let deletedMsgId: number | null = null;
          let answeredClose = false;
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes("deleteMessage")) {
              const body = JSON.parse(init?.body as string);
              deletedMsgId = body.message_id;
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            if (url.includes("answerCallbackQuery")) {
              answeredClose = true;
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            return Promise.resolve(new Response("Not found", { status: 404 }));
          });

          const req = makeRequest({
            update_id: 164,
            callback_query: {
              id: "cb_close",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 854, chat: { id: 987654321 } },
              data: "close:menu",
            },
          });
          const res = await worker.fetch(req, mockEnv, createMockContext() as any);
          expect(res.status).toBe(200);
          const json = (await res.json()) as any;
          expect(json.status).toBe("menu_closed");
          expect(deletedMsgId).toBe(854);
          expect(answeredClose).toBe(true);
        });

        it("handles refresh callbacks for status, stats, pending, and home", async () => {
          let editedText = "";
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes("editMessageText")) {
              const body = JSON.parse(init?.body as string);
              editedText = body.text;
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            if (url.includes("answerCallbackQuery")) {
              return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
            }
            return Promise.resolve(new Response("Not found", { status: 404 }));
          });

          // Refresh status
          const reqStatus = makeRequest({
            update_id: 165,
            callback_query: {
              id: "cb_ref_status",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 855, chat: { id: 987654321 } },
              data: "refresh:status",
            },
          });
          const resStatus = await worker.fetch(reqStatus, mockEnv, createMockContext() as any);
          expect(resStatus.status).toBe(200);
          const jsonStatus = (await resStatus.json()) as any;
          expect(jsonStatus.status).toBe("status_refreshed");
          expect(editedText).toContain("Agent Status Report");

          // Refresh stats
          const reqStats = makeRequest({
            update_id: 166,
            callback_query: {
              id: "cb_ref_stats",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 856, chat: { id: 987654321 } },
              data: "refresh:stats",
            },
          });
          const resStats = await worker.fetch(reqStats, mockEnv, createMockContext() as any);
          expect(resStats.status).toBe(200);
          const jsonStats = (await resStats.json()) as any;
          expect(jsonStats.status).toBe("stats_refreshed");
          expect(editedText).toContain("Agent Performance &amp; Execution Stats");

          // Refresh pending
          const reqPending = makeRequest({
            update_id: 167,
            callback_query: {
              id: "cb_ref_pending",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 857, chat: { id: 987654321 } },
              data: "refresh:pending",
            },
          });
          const resPending = await worker.fetch(reqPending, mockEnv, createMockContext() as any);
          expect(resPending.status).toBe(200);
          const jsonPending = (await resPending.json()) as any;
          expect(jsonPending.status).toBe("pending_refreshed");

          // Refresh home
          const reqHome = makeRequest({
            update_id: 168,
            callback_query: {
              id: "cb_ref_home",
              from: { id: 987654321, is_bot: false, first_name: "Operator" },
              message: { message_id: 858, chat: { id: 987654321 } },
              data: "refresh:home",
            },
          });
          const resHome = await worker.fetch(reqHome, mockEnv, createMockContext() as any);
          expect(resHome.status).toBe(200);
          const jsonHome = (await resHome.json()) as any;
          expect(jsonHome.status).toBe("home_refreshed");
          expect(editedText).toContain("Command &amp; Control Hub");
        });
      });
    });
  });
});
