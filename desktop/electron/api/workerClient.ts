/**
 * Strongly-typed Cloudflare Worker API Client
 *
 * Communicates with the Cloudflare Worker unified API using
 * Bearer <DESKTOP_API_SECRET> authentication.
 */

import type {
  ActionResult,
  AgentState,
  Incident,
  ScheduledPost,
  ConnectionRequestAction,
  AutomatedCommentWindow,
} from "../types";

export interface WorkerClientConfig {
  baseUrl: string;
  apiSecret: string;
}

export interface CloudDispatchConfig {
  repo_owner?: string;
  repo_name?: string;
  github_pat?: string;
}

export class WorkerClient {
  private baseUrl: string;
  private apiSecret: string;

  constructor(config?: Partial<WorkerClientConfig>) {
    this.baseUrl = this.normalizeUrl(config?.baseUrl || "");
    this.apiSecret = (config?.apiSecret || "").trim();
  }

  /**
   * Normalizes Worker URL by trimming whitespace, trailing slashes,
   * and any accidentally appended API subpaths like /api or /api/state.
   */
  public normalizeUrl(url: string): string {
    return (url || "")
      .trim()
      .replace(/\/+$/, "")
      .replace(/\/api\/state\/?$/, "")
      .replace(/\/api\/?$/, "");
  }

  /**
   * Updates client connection settings dynamically.
   */
  public updateConfig(config: Partial<WorkerClientConfig>): void {
    if (config.baseUrl !== undefined) {
      this.baseUrl = this.normalizeUrl(config.baseUrl);
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
   * Tests connection to Cloudflare Worker API with current or provided credentials.
   * Can accept ad-hoc credentials to verify inputs prior to saving.
   */
  public async testConnection(
    credentials?: Partial<WorkerClientConfig>
  ): Promise<{ success: boolean; latencyMs: number }> {
    const targetUrl = this.normalizeUrl(
      credentials?.baseUrl !== undefined ? credentials.baseUrl : this.baseUrl
    );
    const targetSecret = (
      credentials?.apiSecret !== undefined
        ? credentials.apiSecret
        : this.apiSecret
    ).trim();

    if (!targetUrl) {
      throw new Error(
        "Worker URL is not configured. Please enter the Worker URL in Settings."
      );
    }
    if (!targetSecret) {
      throw new Error(
        "Desktop API Secret is not configured. Please enter the API Secret in Settings."
      );
    }

    const cleanEndpoint = `${targetUrl}/api/state`;
    const start = performance.now();

    let response: Response;
    try {
      response = await fetch(cleanEndpoint, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${targetSecret}`,
          Accept: "application/json",
          "User-Agent": "LinkedInHITL-Desktop/1.0.0",
        },
      });
    } catch (networkError) {
      const msg =
        networkError instanceof Error
          ? networkError.message
          : String(networkError);
      throw new Error(`Worker connection failed: ${msg}`);
    }

    const latencyMs = Math.round(performance.now() - start);

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

      if (response.status === 401) {
        throw new Error(
          "Authentication failed (401 Unauthorized): Invalid Desktop API Secret."
        );
      }
      if (response.status === 404) {
        throw new Error(
          "Endpoint not found (404): The Worker URL appears to be incorrect or /api/state is not routed."
        );
      }
      throw new Error(
        `Worker API Error (${response.status} ${response.statusText}): ${errorDetails || "Request failed"}`
      );
    }

    // Update active credentials on successful test
    if (credentials?.baseUrl !== undefined) {
      this.baseUrl = targetUrl;
    }
    if (credentials?.apiSecret !== undefined) {
      this.apiSecret = targetSecret;
    }

    return {
      success: true,
      latencyMs,
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
        const mainMsg = (errorJson.error as string) || (errorJson.message as string);
        const extraDetails = errorJson.details
          ? typeof errorJson.details === "string"
            ? errorJson.details
            : JSON.stringify(errorJson.details)
          : "";
        errorDetails = mainMsg && extraDetails
          ? `${mainMsg} - ${extraDetails}`
          : mainMsg || extraDetails || JSON.stringify(errorJson);
      } catch {
        errorDetails = await response.text().catch(() => response.statusText);
      }
      if (errorDetails.includes("Resource not accessible by personal access token")) {
        errorDetails += " -> GitHub PAT lacks workflow dispatch permission. For Classic PATs (ghp_...), check the 'workflow' scope. For Fine-grained PATs (github_pat_...), set Repository Permissions -> 'Actions' to 'Read and write'.";
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

    const pendingActions = (
      Array.isArray(stateObj.pending_actions)
        ? stateObj.pending_actions
        : Array.isArray(stateObj.pendingActions)
          ? stateObj.pendingActions
          : Array.isArray(stateObj.pending)
            ? stateObj.pending
            : []
    ) as AgentState["pending_actions"];

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
      pending: pendingActions,
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
    itemId: string,
    cloudDispatchConfig?: CloudDispatchConfig,
    note?: string,
    draftText?: string
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
      const body: Record<string, unknown> = {
        action,
        itemId: itemId.trim(),
        item_id: itemId.trim(),
      };
      if (draftText) {
        body.draft_text = draftText;
        body.draftText = draftText;
      }
      if (note) {
        body.note = note;
        body.note_text = note;
      }
      if (cloudDispatchConfig?.repo_owner) {
        body.repo_owner = cloudDispatchConfig.repo_owner;
      }
      if (cloudDispatchConfig?.repo_name) {
        body.repo_name = cloudDispatchConfig.repo_name;
      }
      if (cloudDispatchConfig?.github_pat) {
        body.github_pat = cloudDispatchConfig.github_pat;
      }

      const response = await this.request<Record<string, unknown>>(
        "/api/action",
        {
          method: "POST",
          body,
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
  public async triggerScout(
    cloudDispatchConfig?: CloudDispatchConfig & { ref?: string }
  ): Promise<boolean> {
    const body: Record<string, unknown> = {};
    if (cloudDispatchConfig?.repo_owner) {
      body.repo_owner = cloudDispatchConfig.repo_owner;
    }
    if (cloudDispatchConfig?.repo_name) {
      body.repo_name = cloudDispatchConfig.repo_name;
    }
    if (cloudDispatchConfig?.github_pat) {
      body.github_pat = cloudDispatchConfig.github_pat;
    }
    if (cloudDispatchConfig?.ref) {
      body.ref = cloudDispatchConfig.ref;
    }

    try {
      const res = await this.request<{ success?: boolean }>("/api/scout", {
        method: "POST",
        body,
      });
      return res.success !== false;
    } catch (err) {
      // Fallback try /api/trigger-scout if /api/scout returned 404
      if (err instanceof Error && err.message.includes("404")) {
        const res = await this.request<{ success?: boolean }>(
          "/api/trigger-scout",
          {
            method: "POST",
            body,
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

    const dataObj =
      res && typeof res === "object" && "data" in res && res.data && typeof res.data === "object"
        ? (res.data as Record<string, unknown>)
        : res;

    const rewritten =
      (dataObj.rewritten_text as string) ||
      (dataObj.rewrittenText as string) ||
      (dataObj.draft as string) ||
      (dataObj.draft_text as string) ||
      (dataObj.draftText as string) ||
      (dataObj.text as string);

    if (rewritten && typeof rewritten === "string") {
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

  /**
   * Fetches all scheduled posts from Worker KV.
   */
  public async fetchScheduledPosts(): Promise<ScheduledPost[]> {
    const res = await this.request<{ success?: boolean; posts?: ScheduledPost[] }>(
      "/api/scheduled-posts",
      { method: "GET" }
    );
    return Array.isArray(res?.posts) ? res.posts : [];
  }

  /**
   * Creates or updates a scheduled post in Worker KV.
   */
  public async saveScheduledPost(post: ScheduledPost): Promise<ScheduledPost> {
    const res = await this.request<{ success?: boolean; post?: ScheduledPost }>(
      "/api/scheduled-posts",
      {
        method: "POST",
        body: { post },
      }
    );
    return res?.post || post;
  }

  /**
   * Deletes a scheduled post from Worker KV.
   */
  public async deleteScheduledPost(id: string): Promise<boolean> {
    const res = await this.request<{ success?: boolean }>(
      `/api/scheduled-posts/${id}`,
      { method: "DELETE" }
    );
    return res?.success !== false;
  }

  /**
   * Fetches current scout schedule from Worker KV.
   */
  public async fetchScoutSchedule(): Promise<AutomatedCommentWindow[]> {
    const res = await this.request<{ success?: boolean; schedule?: AutomatedCommentWindow[] }>(
      "/api/scout-schedule",
      { method: "GET" }
    );
    return Array.isArray(res?.schedule) ? res.schedule : [];
  }

  /**
   * Persists configured scout schedule to Worker KV.
   */
  public async saveScoutSchedule(schedule: AutomatedCommentWindow[]): Promise<boolean> {
    const res = await this.request<{ success?: boolean; schedule?: AutomatedCommentWindow[] }>(
      "/api/scout-schedule",
      {
        method: "POST",
        body: { schedule },
      }
    );
    return res?.success !== false;
  }

  /**
   * Fetches outreach connection queue from Worker KV.
   */
  public async fetchConnectionQueue(): Promise<ConnectionRequestAction[]> {
    const res = await this.request<{ success?: boolean; queue?: ConnectionRequestAction[] }>(
      "/api/connection-queue",
      { method: "GET" }
    );
    return Array.isArray(res?.queue) ? res.queue : [];
  }

  /**
   * Adds or updates a candidate in the outreach connection queue.
   */
  public async saveConnectionCandidate(candidate: ConnectionRequestAction): Promise<boolean> {
    const res = await this.request<{ success?: boolean }>(
      "/api/connection-queue",
      {
        method: "POST",
        body: candidate,
      }
    );
    return res?.success !== false;
  }

  /**
   * Uploads binary media to Cloudflare R2 media vault via Worker API.
   */
  public async uploadMedia(
    key: string,
    data: ArrayBuffer | Uint8Array,
    contentType?: string
  ): Promise<{ success: boolean; key: string; url: string }> {
    const cleanKey = key.replace(/^\/+/, "");
    const targetUrl = `${this.baseUrl}/api/media/${cleanKey}`;

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.apiSecret}`,
    };
    if (contentType) {
      headers["Content-Type"] = contentType;
    }

    const response = await fetch(targetUrl, {
      method: "PUT",
      headers,
      body: data as any,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Media upload failed (${response.status}): ${errText}`);
    }

    const res = (await response.json()) as { success?: boolean; key?: string };
    const durableKey = res.key || cleanKey;
    const mediaUrl = `${this.baseUrl}/api/media/${durableKey}?token=${this.apiSecret}`;

    return {
      success: true,
      key: durableKey,
      url: mediaUrl,
    };
  }
}
