/**
 * Strongly-typed Cloudflare Worker API Client
 *
 * Communicates with the Cloudflare Worker unified API using
 * Bearer <DESKTOP_API_SECRET> authentication.
 */

import type {
  ActionResult,
  AgentState,
  DesktopSettings,
  Incident,
} from "../types";

export interface WorkerClientConfig {
  baseUrl: string;
  apiSecret: string;
}

export class WorkerClient {
  private baseUrl: string;
  private apiSecret: string;

  constructor(config?: Partial<WorkerClientConfig>) {
    this.baseUrl = (config?.baseUrl || "").trim().replace(/\/+$/, "");
    this.apiSecret = (config?.apiSecret || "").trim();
  }

  /**
   * Updates client connection settings dynamically.
   */
  public updateConfig(config: Partial<WorkerClientConfig>): void {
    if (config.baseUrl !== undefined) {
      this.baseUrl = config.baseUrl.trim().replace(/\/+$/, "");
    }
    if (config.apiSecret !== undefined) {
      this.apiSecret = config.apiSecret.trim();
    }
  }

  /**
   * Returns current client configuration.
   */
  public getConfig(): WorkerClientConfig {
    return {
      baseUrl: this.baseUrl,
      apiSecret: this.apiSecret,
    };
  }

  /**
   * Internal HTTP request helper.
   */
  private async request<T>(
    endpoint: string,
    options: {
      method?: string;
      body?: unknown;
      headers?: Record<string, string>;
    } = {}
  ): Promise<T> {
    if (!this.baseUrl) {
      throw new Error(
        "Worker URL is not configured. Please set the Worker URL in Settings."
      );
    }
    if (!this.apiSecret) {
      throw new Error(
        "Desktop API Secret is not configured. Please set the API Secret in Settings."
      );
    }

    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = `${this.baseUrl}${cleanEndpoint}`;

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiSecret}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      "User-Agent": "LinkedInHITL-Desktop/1.0.0",
      ...options.headers,
    };

    const fetchOptions: RequestInit = {
      method: options.method || "GET",
      headers,
    };

    if (options.body !== undefined) {
      fetchOptions.body = JSON.stringify(options.body);
    }

    let response: Response;
    try {
      response = await fetch(url, fetchOptions);
    } catch (networkError) {
      const msg =
        networkError instanceof Error
          ? networkError.message
          : String(networkError);
      throw new Error(`Worker connection failed: ${msg}`);
    }

    if (!response.ok) {
      let errorDetails = "";
      try {
        const errorJson = (await response.json()) as Record<string, unknown>;
        errorDetails =
          (errorJson.error as string) ||
          (errorJson.message as string) ||
          JSON.stringify(errorJson);
      } catch {
        errorDetails = await response.text().catch(() => response.statusText);
      }
      throw new Error(
        `Worker API Error (${response.status} ${response.statusText}): ${errorDetails || "Request failed"}`
      );
    }

    // Try parsing JSON; if empty 204 response or non-json, return empty object as T
    const text = await response.text();
    if (!text.trim()) {
      return {} as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      return text as unknown as T;
    }
  }

  /**
   * Fetches full agent state from Cloudflare Worker KV.
   */
  public async fetchState(): Promise<AgentState> {
    const raw = await this.request<Record<string, unknown>>("/api/state", {
      method: "GET",
    });

    // Worker may return { state: ... } or { success: true, data: ... } or raw state directly
    const stateObj = (raw.state || raw.data || raw) as Record<string, unknown>;

    const pendingActions = Array.isArray(stateObj.pending_actions)
      ? stateObj.pending_actions
      : Array.isArray(stateObj.pendingActions)
        ? stateObj.pendingActions
        : [];

    const dailyCounters = (stateObj.daily_counters ||
      stateObj.dailyCounters || {
        date: new Date().toISOString().split("T")[0],
        comments_executed: 0,
        posts_executed: 0,
        suggestions_sent: 0,
      }) as AgentState["daily_counters"];

    const history = Array.isArray(stateObj.history) ? stateObj.history : [];

    const incident = (stateObj.incident as Incident | null) || null;
    const paused = Boolean(stateObj.paused);
    const seenPostsCount =
      typeof stateObj.seen_posts_count === "number"
        ? stateObj.seen_posts_count
        : typeof stateObj.seenPostsCount === "number"
          ? stateObj.seenPostsCount
          : undefined;

    return {
      pending_actions: pendingActions,
      pendingActions,
      daily_counters: dailyCounters,
      dailyCounters,
      history,
      incident,
      paused,
      seen_posts_count: seenPostsCount,
      seenPostsCount,
      last_updated: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
    };
  }

  /**
   * Executes human approval or rejection on a pending action item.
   */
  public async executeAction(
    action: "approve" | "reject",
    itemId: string
  ): Promise<ActionResult> {
    if (!itemId || !itemId.trim()) {
      return {
        success: false,
        error: "Item ID must not be empty",
        itemId,
        action,
      };
    }

    try {
      const response = await this.request<Record<string, unknown>>(
        "/api/action",
        {
          method: "POST",
          body: {
            action,
            itemId: itemId.trim(),
            item_id: itemId.trim(),
          },
        }
      );

      const success = response.success !== false;
      const message =
        (response.message as string) ||
        (response.status as string) ||
        `Action '${action}' dispatched successfully`;

      return {
        success,
        message,
        itemId: itemId.trim(),
        action,
      };
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err.message : String(err),
        itemId: itemId.trim(),
        action,
      };
    }
  }

  /**
   * Triggers an immediate scout run in GitHub Actions / Worker.
   */
  public async triggerScout(): Promise<boolean> {
    try {
      const res = await this.request<{ success?: boolean }>("/api/scout", {
        method: "POST",
        body: {},
      });
      return res.success !== false;
    } catch (err) {
      // Fallback try /api/trigger-scout if /api/scout returned 404
      if (err instanceof Error && err.message.includes("404")) {
        const res = await this.request<{ success?: boolean }>(
          "/api/trigger-scout",
          {
            method: "POST",
            body: {},
          }
        );
        return res.success !== false;
      }
      throw err;
    }
  }

  /**
   * Toggles the remote agent pause state.
   */
  public async togglePause(paused: boolean): Promise<boolean> {
    const res = await this.request<{ success?: boolean }>("/api/pause", {
      method: "POST",
      body: { paused },
    });
    return res.success !== false;
  }

  /**
   * Clears an active circuit breaker incident.
   */
  public async clearIncident(): Promise<boolean> {
    try {
      const res = await this.request<{ success?: boolean }>(
        "/api/incident/clear",
        {
          method: "POST",
          body: {},
        }
      );
      return res.success !== false;
    } catch (err) {
      // Fallback try /api/clear-incident if /api/incident/clear returned 404
      if (err instanceof Error && err.message.includes("404")) {
        const res = await this.request<{ success?: boolean }>(
          "/api/clear-incident",
          {
            method: "POST",
            body: {},
          }
        );
        return res.success !== false;
      }
      throw err;
    }
  }

  /**
   * Requests LLM to rewrite a draft comment with a specified tone.
   */
  public async rewriteDraft(draftText: string, tone: string): Promise<string> {
    if (!draftText || !draftText.trim()) {
      throw new Error("Draft text to rewrite must not be empty");
    }

    const res = await this.request<Record<string, unknown>>("/api/rewrite", {
      method: "POST",
      body: {
        draftText: draftText.trim(),
        draft_text: draftText.trim(),
        tone: (tone || "professional").trim(),
      },
    });

    if (typeof res === "string") {
      return res;
    }

    const rewritten =
      (res.draft as string) ||
      (res.rewrittenText as string) ||
      (res.draftText as string) ||
      (res.text as string);

    if (rewritten) {
      return rewritten;
    }

    throw new Error("Worker returned an unexpected rewrite payload format");
  }

  /**
   * Uploads and persists encrypted LinkedIn session data in Worker KV.
   */
  public async saveSession(sessionData: string): Promise<boolean> {
    if (!sessionData || !sessionData.trim()) {
      throw new Error("Session data must not be empty");
    }

    const res = await this.request<{ success?: boolean }>("/api/session", {
      method: "POST",
      body: {
        sessionData: sessionData.trim(),
        session_data: sessionData.trim(),
      },
    });

    return res.success !== false;
  }
}
