import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import worker, {
  Env,
  activeClientSockets,
  broadcastEvent,
  handleWebSocketUpgrade,
} from "../src/index";

class MockWebSocket {
  public accepted = false;
  public readyState = 1; // 1 = OPEN
  public sentMessages: string[] = [];
  public listeners: Record<string, Function[]> = {};

  accept() {
    this.accepted = true;
  }

  send(data: string) {
    if (this.readyState !== 1) {
      throw new Error("WebSocket is not open");
    }
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    this.emit("close");
  }

  addEventListener(event: string, callback: Function) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  emit(event: string, data?: any) {
    if (this.listeners[event]) {
      for (const cb of [...this.listeners[event]]) {
        cb(data);
      }
    }
  }
}

class MockWebSocketPair {
  0: MockWebSocket;
  1: MockWebSocket;
  constructor() {
    this[0] = new MockWebSocket();
    this[1] = new MockWebSocket();
  }
}

describe("Cloudflare Worker WebSocket Push Hub (/api/ws)", () => {
  const mockApiSecret = "ws-secret-desktop-test-key-123";

  const mockEnv: Env = {
    TELEGRAM_WEBHOOK_SECRET: "tg-webhook-secret-456",
    TELEGRAM_BOT_TOKEN: "123456:MOCK_TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "99887766",
    GITHUB_DISPATCH_PAT: "ghp_dispatchpat12345",
    GITHUB_REPO_OWNER: "test-owner",
    GITHUB_REPO_NAME: "test-repo",
    DESKTOP_API_SECRET: mockApiSecret,
  };

  const createMockContext = () =>
    ({
      waitUntil: vi.fn((promise: Promise<unknown>) => promise),
      passThroughOnException: vi.fn(),
      props: {},
    } as unknown as ExecutionContext);

  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    activeClientSockets.clear();
    (globalThis as any).WebSocketPair = MockWebSocketPair;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    activeClientSockets.clear();
    delete (globalThis as any).WebSocketPair;
  });

  describe("WebSocket Upgrade Handshake", () => {
    it("successfully upgrades WebSocket connection with valid token and Upgrade header", async () => {
      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());

      expect(response.status).toBe(101);
      expect((response as any).webSocket).toBeDefined();
      expect(activeClientSockets.size).toBe(1);

      const serverSocket = Array.from(activeClientSockets)[0] as unknown as MockWebSocket;
      expect(serverSocket.accepted).toBe(true);
    });

    it("rejects request if method is not GET", async () => {
      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "POST",
        headers: {
          Upgrade: "websocket",
        },
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());
      expect(response.status).toBe(405);
      expect(activeClientSockets.size).toBe(0);
    });

    it("rejects request if Upgrade header is missing or not 'websocket'", async () => {
      const requestWithoutHeader = new Request(
        `https://worker.local/api/ws?token=${mockApiSecret}`,
        {
          method: "GET",
        }
      );

      const res1 = await worker.fetch(requestWithoutHeader, mockEnv, createMockContext());
      expect(res1.status).toBe(426);
      expect(await res1.text()).toBe("Expected Upgrade: websocket");

      const requestWithWrongHeader = new Request(
        `https://worker.local/api/ws?token=${mockApiSecret}`,
        {
          method: "GET",
          headers: {
            Upgrade: "unknown-protocol",
          },
        }
      );

      const res2 = await worker.fetch(requestWithWrongHeader, mockEnv, createMockContext());
      expect(res2.status).toBe(426);
      expect(activeClientSockets.size).toBe(0);
    });
  });

  describe("Token Authentication", () => {
    it("returns 401 when token query param is missing", async () => {
      const request = new Request("https://worker.local/api/ws", {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());
      expect(response.status).toBe(401);
      const data = await response.json();
      expect(data).toEqual({ error: "Unauthorized" });
      expect(activeClientSockets.size).toBe(0);
    });

    it("returns 401 when token query param is incorrect", async () => {
      const request = new Request("https://worker.local/api/ws?token=invalid-secret-key", {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());
      expect(response.status).toBe(401);
      expect(activeClientSockets.size).toBe(0);
    });

    it("returns 401 when DESKTOP_API_SECRET is not configured on env", async () => {
      const envWithoutSecret: Env = {
        ...mockEnv,
        DESKTOP_API_SECRET: undefined,
      };

      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      const response = await worker.fetch(request, envWithoutSecret, createMockContext());
      expect(response.status).toBe(401);
      expect(activeClientSockets.size).toBe(0);
    });
  });

  describe("Heartbeat Ping/Pong & Socket Lifecycle", () => {
    it("responds with 'pong' when receiving 'ping' message", async () => {
      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      await worker.fetch(request, mockEnv, createMockContext());
      const serverSocket = Array.from(activeClientSockets)[0] as unknown as MockWebSocket;

      expect(serverSocket.sentMessages.length).toBe(0);

      // Client sends ping
      serverSocket.emit("message", { data: "ping" });
      expect(serverSocket.sentMessages).toEqual(["pong"]);

      // Unrelated message does not trigger pong
      serverSocket.emit("message", { data: "hello" });
      expect(serverSocket.sentMessages).toEqual(["pong"]);
    });

    it("prunes disconnected socket on 'close' event", async () => {
      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      await worker.fetch(request, mockEnv, createMockContext());
      expect(activeClientSockets.size).toBe(1);

      const serverSocket = Array.from(activeClientSockets)[0] as unknown as MockWebSocket;
      serverSocket.close();

      expect(activeClientSockets.size).toBe(0);
    });

    it("prunes disconnected socket on 'error' event", async () => {
      const request = new Request(`https://worker.local/api/ws?token=${mockApiSecret}`, {
        method: "GET",
        headers: {
          Upgrade: "websocket",
        },
      });

      await worker.fetch(request, mockEnv, createMockContext());
      expect(activeClientSockets.size).toBe(1);

      const serverSocket = Array.from(activeClientSockets)[0] as unknown as MockWebSocket;
      serverSocket.emit("error", new Error("Socket error"));

      expect(activeClientSockets.size).toBe(0);
    });
  });

  describe("Event Broadcast & State Mutation Hooks", () => {
    it("broadcasts event JSON to all connected clients", async () => {
      const sock1 = new MockWebSocket();
      const sock2 = new MockWebSocket();
      activeClientSockets.add(sock1 as unknown as WebSocket);
      activeClientSockets.add(sock2 as unknown as WebSocket);

      broadcastEvent({ type: "queue_updated" });

      expect(sock1.sentMessages).toEqual([JSON.stringify({ type: "queue_updated" })]);
      expect(sock2.sentMessages).toEqual([JSON.stringify({ type: "queue_updated" })]);
    });

    it("prunes throwing sockets during broadcast", async () => {
      const goodSock = new MockWebSocket();
      const deadSock = new MockWebSocket();
      deadSock.readyState = 3; // CLOSED -> throws on send

      activeClientSockets.add(goodSock as unknown as WebSocket);
      activeClientSockets.add(deadSock as unknown as WebSocket);

      broadcastEvent({ type: "test_event" });

      expect(goodSock.sentMessages).toEqual([JSON.stringify({ type: "test_event" })]);
      expect(activeClientSockets.has(deadSock as unknown as WebSocket)).toBe(false);
      expect(activeClientSockets.has(goodSock as unknown as WebSocket)).toBe(true);
    });

    it("broadcasts 'action_executed' when POST /api/action is approved", async () => {
      const clientSocket = new MockWebSocket();
      activeClientSockets.add(clientSocket as unknown as WebSocket);

      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
        })
      );

      const request = new Request("https://worker.local/api/action", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "approve",
          item_id: "item-approve-test-1",
        }),
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());
      expect(response.status).toBe(200);

      expect(clientSocket.sentMessages).toContain(
        JSON.stringify({
          type: "action_executed",
          item_id: "item-approve-test-1",
          action: "approve",
        })
      );
    });

    it("broadcasts 'action_executed' when POST /api/action is rejected", async () => {
      const clientSocket = new MockWebSocket();
      activeClientSockets.add(clientSocket as unknown as WebSocket);

      const mockKv = {
        get: vi.fn().mockResolvedValue(null),
        delete: vi.fn().mockResolvedValue(undefined),
        put: vi.fn().mockResolvedValue(undefined),
      };

      const envWithKv: Env = {
        ...mockEnv,
        LINKEDIN_AGENT_KV: mockKv as any,
      };

      const request = new Request("https://worker.local/api/action", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "reject",
          item_id: "item-reject-test-2",
        }),
      });

      const response = await worker.fetch(request, envWithKv, createMockContext());
      expect(response.status).toBe(200);

      expect(clientSocket.sentMessages).toContain(
        JSON.stringify({
          type: "action_executed",
          item_id: "item-reject-test-2",
          action: "reject",
        })
      );
    });

    it("broadcasts 'queue_updated' when POST /api/scout triggers scout run", async () => {
      const clientSocket = new MockWebSocket();
      activeClientSockets.add(clientSocket as unknown as WebSocket);

      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "dispatched" }), {
          status: 200,
        })
      );

      const request = new Request("https://worker.local/api/scout", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      });

      const response = await worker.fetch(request, mockEnv, createMockContext());
      expect(response.status).toBe(200);

      expect(clientSocket.sentMessages).toContain(
        JSON.stringify({
          type: "queue_updated",
        })
      );
    });
  });
});
