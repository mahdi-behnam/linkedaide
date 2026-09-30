/**
 * Realtime Push Client for Desktop Electron Main Process
 *
 * Establishes durable WebSocket connection with Cloudflare Worker WebSocket Push Hub.
 * Dispatches realtime state events to renderer process via IPC.
 * Supports exponential backoff reconnection (1s, 2s, 4s, ..., max 30s) and 30s ping heartbeats.
 */

import type { BrowserWindow } from "electron";

export interface RealtimePushClientOptions {
  WebSocketClass?: any;
  pingIntervalMs?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
}

export class RealtimePushClient {
  private mainWindow: BrowserWindow | null = null;
  private workerUrl: string = "";
  private apiSecret: string = "";
  private socket: any = null;
  private isExplicitDisconnect: boolean = false;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingTimer: NodeJS.Timeout | null = null;
  private backoffMs: number = 1000;
  private readonly initialBackoffMs: number = 1000;
  private readonly maxBackoffMs: number = 30000;
  private readonly pingIntervalMs: number = 30000;
  private readonly WebSocketClass: any;

  constructor(
    mainWindow?: BrowserWindow | null,
    workerUrl?: string,
    apiSecret?: string,
    options?: RealtimePushClientOptions
  ) {
    this.mainWindow = mainWindow ?? null;
    this.workerUrl = workerUrl ?? "";
    this.apiSecret = apiSecret ?? "";
    this.WebSocketClass =
      options?.WebSocketClass ??
      (typeof globalThis !== "undefined" ? (globalThis as any).WebSocket : undefined);

    if (options?.initialBackoffMs) {
      this.initialBackoffMs = options.initialBackoffMs;
      this.backoffMs = options.initialBackoffMs;
    }
    if (options?.maxBackoffMs) {
      this.maxBackoffMs = options.maxBackoffMs;
    }
    if (options?.pingIntervalMs) {
      this.pingIntervalMs = options.pingIntervalMs;
    }
  }

  public setMainWindow(window: BrowserWindow | null): void {
    this.mainWindow = window;
  }

  public getSocket(): any {
    return this.socket;
  }

  public isConnected(): boolean {
    const OPEN_STATE = this.WebSocketClass?.OPEN ?? 1;
    return Boolean(this.socket && this.socket.readyState === OPEN_STATE);
  }

  public getCurrentBackoffMs(): number {
    return this.backoffMs;
  }

  /**
   * Builds the WebSocket URL from worker base URL and desktop API secret.
   * Converts http/https to ws/wss: ws://${workerUrl.replace(/^http/, "ws")}/api/ws?token=${secret}
   */
  public getWebSocketUrl(): string {
    const cleanUrl = this.workerUrl.trim().replace(/\/+$/, "");
    if (!cleanUrl) return "";

    let wsBase: string;
    if (cleanUrl.startsWith("ws://") || cleanUrl.startsWith("wss://")) {
      wsBase = cleanUrl;
    } else if (cleanUrl.startsWith("http")) {
      wsBase = cleanUrl.replace(/^http/, "ws");
    } else {
      wsBase = `ws://${cleanUrl}`;
    }

    return `${wsBase}/api/ws?token=${encodeURIComponent(this.apiSecret)}`;
  }

  /**
   * Connects to the Worker WebSocket Push Hub.
   */
  public connect(): void {
    this.isExplicitDisconnect = false;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (!this.workerUrl || !this.apiSecret) {
      return;
    }

    if (!this.WebSocketClass) {
      console.warn("[RealtimePushClient] WebSocket class is not available in environment");
      return;
    }

    const OPEN_STATE = this.WebSocketClass?.OPEN ?? 1;
    if (this.socket && this.socket.readyState === OPEN_STATE) {
      return;
    }

    const wsUrl = this.getWebSocketUrl();
    if (!wsUrl) return;

    try {
      const socket = new this.WebSocketClass(wsUrl);
      this.socket = socket;

      const onOpen = () => {
        if (this.socket !== socket) return;
        this.backoffMs = this.initialBackoffMs;
        this.startPing();
      };

      const onMessage = (event: any) => {
        if (this.socket !== socket) return;
        const rawData = typeof event?.data === "string" ? event.data : event?.data?.toString();
        if (!rawData || rawData === "pong") {
          return;
        }

        try {
          const parsed = JSON.parse(rawData);
          if (
            this.mainWindow &&
            !this.mainWindow.isDestroyed() &&
            this.mainWindow.webContents
          ) {
            this.mainWindow.webContents.send("realtime:event", parsed);
          }
        } catch {
          // Ignore invalid JSON payloads
        }
      };

      const onClose = () => {
        if (this.socket !== socket) return;
        this.stopPing();
        this.socket = null;
        if (!this.isExplicitDisconnect) {
          this.scheduleReconnect();
        }
      };

      const onError = () => {
        if (this.socket !== socket) return;
        this.stopPing();
        this.socket = null;
        if (!this.isExplicitDisconnect) {
          this.scheduleReconnect();
        }
      };

      if (typeof socket.addEventListener === "function") {
        socket.addEventListener("open", onOpen);
        socket.addEventListener("message", onMessage);
        socket.addEventListener("close", onClose);
        socket.addEventListener("error", onError);
      } else {
        socket.onopen = onOpen;
        socket.onmessage = onMessage;
        socket.onclose = onClose;
        socket.onerror = onError;
      }
    } catch {
      if (!this.isExplicitDisconnect) {
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Disconnects active WebSocket connection and cancels any reconnect timers.
   */
  public disconnect(): void {
    this.isExplicitDisconnect = true;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopPing();

    if (this.socket) {
      try {
        this.socket.close();
      } catch {
        // Ignore close errors
      }
      this.socket = null;
    }
  }

  /**
   * Updates worker URL and API secret credentials, reconnecting if credentials changed.
   */
  public updateCredentials(url: string, secret: string): void {
    const cleanUrl = url.trim();
    const cleanSecret = secret.trim();

    const changed = this.workerUrl !== cleanUrl || this.apiSecret !== cleanSecret;
    this.workerUrl = cleanUrl;
    this.apiSecret = cleanSecret;

    if (changed) {
      this.disconnect();
      this.backoffMs = this.initialBackoffMs;
      if (this.workerUrl && this.apiSecret) {
        this.connect();
      }
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      const OPEN_STATE = this.WebSocketClass?.OPEN ?? 1;
      if (this.socket && this.socket.readyState === OPEN_STATE) {
        try {
          this.socket.send("ping");
        } catch {
          // If ping send fails, let onclose/onerror handle reconnect
        }
      }
    }, this.pingIntervalMs);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.isExplicitDisconnect || this.reconnectTimer) {
      return;
    }

    const delay = this.backoffMs;
    this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}
