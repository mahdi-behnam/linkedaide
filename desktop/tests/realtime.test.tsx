import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { RealtimePushClient } from "../electron/api/realtimeHub";
import { AppProvider, useApp } from "../src/context/AppContext";

class MockWebSocketInstance {
  public static instances: MockWebSocketInstance[] = [];
  public static OPEN = 1;
  public static CLOSED = 3;

  public url: string;
  public readyState: number = 0; // CONNECTING
  public sentMessages: string[] = [];
  public listeners: Record<string, Function[]> = {};

  public onopen: (() => void) | null = null;
  public onmessage: ((event: any) => void) | null = null;
  public onclose: (() => void) | null = null;
  public onerror: ((error: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    this.readyState = 0;
    MockWebSocketInstance.instances.push(this);
  }

  public addEventListener(event: string, callback: Function) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  public send(data: string) {
    if (this.readyState !== MockWebSocketInstance.OPEN) {
      throw new Error("WebSocket is not open");
    }
    this.sentMessages.push(data);
  }

  public close() {
    this.readyState = MockWebSocketInstance.CLOSED;
    this.trigger("close");
  }

  public simulateOpen() {
    this.readyState = MockWebSocketInstance.OPEN;
    this.trigger("open");
  }

  public simulateMessage(data: string) {
    this.trigger("message", { data });
  }

  public simulateClose() {
    this.readyState = MockWebSocketInstance.CLOSED;
    this.trigger("close");
  }

  public simulateError(error: any = new Error("Connection failed")) {
    this.readyState = MockWebSocketInstance.CLOSED;
    this.trigger("error", error);
  }

  private trigger(event: string, data?: any) {
    if (this.listeners[event]) {
      for (const cb of [...this.listeners[event]]) {
        cb(data);
      }
    }
    if (event === "open" && this.onopen) this.onopen();
    if (event === "message" && this.onmessage) this.onmessage(data);
    if (event === "close" && this.onclose) this.onclose();
    if (event === "error" && this.onerror) this.onerror(data);
  }
}

describe("RealtimePushClient & Instant Desktop Sync", () => {
  let mockBrowserWindow: any;
  let mockWebContents: any;

  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocketInstance.instances = [];

    mockWebContents = {
      send: vi.fn(),
      isDestroyed: vi.fn().mockReturnValue(false),
    };

    mockBrowserWindow = {
      webContents: mockWebContents,
      isDestroyed: vi.fn().mockReturnValue(false),
    };
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe("URL Resolution & Connection", () => {
    it("converts http to ws and formats /api/ws?token=<secret>", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "http://127.0.0.1:8787",
        "secret-desktop-123",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();

      expect(MockWebSocketInstance.instances.length).toBe(1);
      const ws = MockWebSocketInstance.instances[0];
      expect(ws.url).toBe("ws://127.0.0.1:8787/api/ws?token=secret-desktop-123");
    });

    it("converts https to wss and trims trailing slashes", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://relay.hitl-agent.workers.dev/",
        "key-456",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();

      const ws = MockWebSocketInstance.instances[0];
      expect(ws.url).toBe("wss://relay.hitl-agent.workers.dev/api/ws?token=key-456");
    });

    it("does not connect if workerUrl or apiSecret is missing", () => {
      const client1 = new RealtimePushClient(mockBrowserWindow, "", "secret", {
        WebSocketClass: MockWebSocketInstance,
      });
      client1.connect();
      expect(MockWebSocketInstance.instances.length).toBe(0);

      const client2 = new RealtimePushClient(mockBrowserWindow, "https://worker.dev", "", {
        WebSocketClass: MockWebSocketInstance,
      });
      client2.connect();
      expect(MockWebSocketInstance.instances.length).toBe(0);
    });

    it("reports connected status accurately based on socket readyState", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      expect(client.isConnected()).toBe(false);

      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();
      expect(client.isConnected()).toBe(true);

      ws.simulateClose();
      expect(client.isConnected()).toBe(false);
    });

    it("falls back to ws library when WebSocketClass option is not passed and global WebSocket is unavailable", () => {
      const origWs = (globalThis as any).WebSocket;
      delete (globalThis as any).WebSocket;
      try {
        const client = new RealtimePushClient(
          mockBrowserWindow,
          "https://worker.dev",
          "secret"
        );
        expect((client as any).WebSocketClass).toBeDefined();
        expect((client as any).WebSocketClass.OPEN).toBe(1);
      } finally {
        if (origWs) {
          (globalThis as any).WebSocket = origWs;
        }
      }
    });
  });

  describe("Exponential Backoff Reconnection (1s, 2s, 4s, ..., max 30s)", () => {
    it("schedules reconnection with exponential backoff on close", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        {
          WebSocketClass: MockWebSocketInstance,
          initialBackoffMs: 1000,
          maxBackoffMs: 30000,
        }
      );

      client.connect();
      expect(MockWebSocketInstance.instances.length).toBe(1);
      const ws1 = MockWebSocketInstance.instances[0];

      // Simulate connection drop
      ws1.simulateClose();
      expect(client.getCurrentBackoffMs()).toBe(2000); // Next backoff is 2000ms

      // Advancing 500ms shouldn't reconnect yet
      vi.advanceTimersByTime(500);
      expect(MockWebSocketInstance.instances.length).toBe(1);

      // Advancing another 500ms (1000ms total) triggers first reconnect
      vi.advanceTimersByTime(500);
      expect(MockWebSocketInstance.instances.length).toBe(2);

      // Second failure backs off by 2000ms
      const ws2 = MockWebSocketInstance.instances[1];
      ws2.simulateClose();
      expect(client.getCurrentBackoffMs()).toBe(4000); // Next backoff is 4000ms

      vi.advanceTimersByTime(1999);
      expect(MockWebSocketInstance.instances.length).toBe(2);
      vi.advanceTimersByTime(1);
      expect(MockWebSocketInstance.instances.length).toBe(3);

      // Third failure backs off by 4000ms
      const ws3 = MockWebSocketInstance.instances[2];
      ws3.simulateClose();
      expect(client.getCurrentBackoffMs()).toBe(8000);

      vi.advanceTimersByTime(4000);
      expect(MockWebSocketInstance.instances.length).toBe(4);
    });

    it("caps exponential backoff delay at maxBackoffMs (30s)", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        {
          WebSocketClass: MockWebSocketInstance,
          initialBackoffMs: 16000,
          maxBackoffMs: 30000,
        }
      );

      client.connect();
      const ws1 = MockWebSocketInstance.instances[0];
      ws1.simulateClose(); // 16s -> next 30s (capped from 32s)
      expect(client.getCurrentBackoffMs()).toBe(30000);

      vi.advanceTimersByTime(16000);
      const ws2 = MockWebSocketInstance.instances[1];
      ws2.simulateClose();
      expect(client.getCurrentBackoffMs()).toBe(30000);
    });

    it("resets backoff to initial backoff (1s) upon successful open", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        {
          WebSocketClass: MockWebSocketInstance,
          initialBackoffMs: 1000,
        }
      );

      client.connect();
      const ws1 = MockWebSocketInstance.instances[0];
      ws1.simulateClose();
      expect(client.getCurrentBackoffMs()).toBe(2000);

      vi.advanceTimersByTime(1000);
      const ws2 = MockWebSocketInstance.instances[1];

      // Successful connection
      ws2.simulateOpen();
      expect(client.getCurrentBackoffMs()).toBe(1000);
    });

    it("cancels reconnection timers and prevents reconnect on explicit disconnect()", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      const ws1 = MockWebSocketInstance.instances[0];
      ws1.simulateClose();

      client.disconnect();

      // Advancing time should not trigger any reconnect
      vi.advanceTimersByTime(60000);
      expect(MockWebSocketInstance.instances.length).toBe(1);
    });
  });

  describe("30-Second Ping Heartbeat", () => {
    it("sends 'ping' every 30 seconds while connected", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        {
          WebSocketClass: MockWebSocketInstance,
          pingIntervalMs: 30000,
        }
      );

      client.connect();
      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();

      expect(ws.sentMessages).toEqual([]);

      vi.advanceTimersByTime(30000);
      expect(ws.sentMessages).toEqual(["ping"]);

      vi.advanceTimersByTime(30000);
      expect(ws.sentMessages).toEqual(["ping", "ping"]);
    });

    it("stops sending ping heartbeat when socket closes or disconnects", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        {
          WebSocketClass: MockWebSocketInstance,
          pingIntervalMs: 30000,
        }
      );

      client.connect();
      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();

      client.disconnect();
      vi.advanceTimersByTime(60000);

      expect(ws.sentMessages).toEqual([]);
    });
  });

  describe("IPC Event Forwarding to Renderer", () => {
    it("forwards valid JSON events to renderer via webContents.send('realtime:event')", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();

      const eventPayload = {
        type: "action_executed",
        item_id: "act-123",
        action: "approve",
      };

      ws.simulateMessage(JSON.stringify(eventPayload));

      expect(mockWebContents.send).toHaveBeenCalledTimes(1);
      expect(mockWebContents.send).toHaveBeenCalledWith("realtime:event", eventPayload);
    });

    it("ignores 'pong' heartbeat responses without emitting IPC event", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();

      ws.simulateMessage("pong");

      expect(mockWebContents.send).not.toHaveBeenCalled();
    });

    it("handles non-JSON or malformed messages gracefully", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://worker.dev",
        "secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      const ws = MockWebSocketInstance.instances[0];
      ws.simulateOpen();

      expect(() => {
        ws.simulateMessage("invalid-json-content{{{");
      }).not.toThrow();

      expect(mockWebContents.send).not.toHaveBeenCalled();
    });
  });

  describe("updateCredentials", () => {
    it("reconnects with updated workerUrl and apiSecret", () => {
      const client = new RealtimePushClient(
        mockBrowserWindow,
        "https://old-worker.dev",
        "old-secret",
        { WebSocketClass: MockWebSocketInstance }
      );

      client.connect();
      expect(MockWebSocketInstance.instances.length).toBe(1);
      expect(MockWebSocketInstance.instances[0].url).toContain("old-worker.dev");

      client.updateCredentials("https://new-worker.dev", "new-secret");

      expect(MockWebSocketInstance.instances.length).toBe(2);
      expect(MockWebSocketInstance.instances[1].url).toContain("new-worker.dev");
      expect(MockWebSocketInstance.instances[1].url).toContain("new-secret");
    });
  });

  describe("Renderer AppContext Instant Sync (<50ms Latency)", () => {
    it("subscribes to realtime:event, updates pending count, and shows toast notification", async () => {
      let realtimeCallback: ((event: any) => void) | null = null;

      const mockApi = {
        onRealtimeEvent: vi.fn((cb: (event: any) => void) => {
          realtimeCallback = cb;
          return () => {
            realtimeCallback = null;
          };
        }),
        fetchState: vi.fn().mockResolvedValue({
          pending_actions: [
            { item_id: "act-1", draft_text: "1", action_type: "comment", created_at: "" },
            { item_id: "act-2", draft_text: "2", action_type: "comment", created_at: "" },
            { item_id: "act-3", draft_text: "3", action_type: "comment", created_at: "" },
            { item_id: "act-4", draft_text: "4", action_type: "comment", created_at: "" },
            { item_id: "act-5", draft_text: "5", action_type: "comment", created_at: "" },
          ],
          daily_counters: { comments_executed: 1, posts_executed: 0, suggestions_sent: 5, date: "2026-09-30", connections_sent: 0 },
          history: [],
          incident: null,
          paused: false,
        }),
      };

      (window as any).api = mockApi;

      const TestConsumer = () => {
        const { pendingCount, lastTriggerMessage } = useApp();
        return (
          <div>
            <div data-testid="count">{pendingCount}</div>
            <div data-testid="toast">{lastTriggerMessage || "no-toast"}</div>
          </div>
        );
      };

      render(
        <AppProvider>
          <TestConsumer />
        </AppProvider>
      );

      expect(mockApi.onRealtimeEvent).toHaveBeenCalled();
      expect(typeof realtimeCallback).toBe("function");

      // Verify latency from event trigger to refreshState execution (<50ms requirement)
      const startTime = performance.now();

      await act(async () => {
        realtimeCallback!({
          type: "queue_updated",
        });
      });

      const elapsed = performance.now() - startTime;
      expect(elapsed).toBeLessThan(50); // Under 50ms latency

      expect(mockApi.fetchState).toHaveBeenCalled();
      expect(screen.getByTestId("count").textContent).toBe("5");
      expect(screen.getByTestId("toast").textContent).toContain("Realtime");
    });
  });
});
