/**
 * Scout Schedule Handlers for Cloudflare Worker:
 * - REST API endpoints: GET and POST /api/scout-schedule
 * - Edge Cron Dispatcher: handleScoutScheduleCron
 */

import { Env, AutomatedCommentWindow } from "../types";
import { jsonResponse } from "../utils";
import { broadcastEvent } from "./ws";
import { ScheduledCronResult } from "./scheduled";

export const defaultScoutWindows: AutomatedCommentWindow[] = [
  {
    id: "scout-win-morning",
    title: "Morning Feed Scout Window",
    start_time: "08:00",
    end_time: "09:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Engineering Leadership & AI Systems",
  },
  {
    id: "scout-win-midday",
    title: "Midday Feed Scout Window",
    start_time: "13:00",
    end_time: "14:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Distributed Systems & Cloud Architecture",
  },
  {
    id: "scout-win-evening",
    title: "Evening Feed Scout Window",
    start_time: "18:00",
    end_time: "19:30",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    status: "active",
    topic_filter: "Technical Architecture & High Impact Engineering",
  },
];

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * REST API handler for /api/scout-schedule:
 * GET: Retrieves the persisted scout schedule (or default windows).
 * POST: Updates and persists the scout schedule to KV, broadcasting realtime event.
 */
export async function handleScoutSchedule(
  request: Request,
  env: Env
): Promise<Response> {
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  const method = request.method;

  // GET /api/scout-schedule
  if (method === "GET") {
    try {
      const raw = await env.LINKEDIN_AGENT_KV.get("scout_schedule");
      let schedule: AutomatedCommentWindow[] = defaultScoutWindows;
      if (raw) {
        try {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed) && parsed.length > 0) {
            schedule = parsed;
          }
        } catch {
          schedule = defaultScoutWindows;
        }
      }
      return jsonResponse({
        success: true,
        schedule,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse(
        { error: "Failed to load scout schedule", details: msg },
        500
      );
    }
  }

  // POST /api/scout-schedule
  if (method === "POST") {
    let body: any;
    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const rawSchedule = body?.schedule || body?.commentWindows || body;
    if (!Array.isArray(rawSchedule)) {
      return jsonResponse(
        { error: "Invalid payload: schedule must be an array" },
        400
      );
    }

    // Validate and sanitize each window
    const sanitized: AutomatedCommentWindow[] = rawSchedule.map(
      (item: any, idx: number) => {
        const id =
          typeof item?.id === "string" && item.id.trim()
            ? item.id.trim()
            : `scout-win-${Date.now()}-${idx}`;
        const title =
          typeof item?.title === "string" && item.title.trim()
            ? item.title.trim()
            : `Scout Window ${idx + 1}`;
        const startTime =
          typeof item?.start_time === "string" && item.start_time.trim()
            ? item.start_time.trim()
            : "09:00";
        const endTime =
          typeof item?.end_time === "string" && item.end_time.trim()
            ? item.end_time.trim()
            : "10:30";
        const days =
          Array.isArray(item?.days) && item.days.length > 0
            ? item.days
            : ["Mon", "Tue", "Wed", "Thu", "Fri"];
        const status =
          item?.status === "active" ||
          item?.status === "standby" ||
          item?.status === "paused"
            ? item.status
            : "active";
        const topicFilter =
          typeof item?.topic_filter === "string" ? item.topic_filter : "";

        return {
          id,
          title,
          start_time: startTime,
          end_time: endTime,
          days,
          status,
          topic_filter: topicFilter,
          local_start_time: item?.local_start_time,
          local_end_time: item?.local_end_time,
          timezone: item?.timezone,
          last_dispatched_at: item?.last_dispatched_at || null,
        };
      }
    );

    try {
      await env.LINKEDIN_AGENT_KV.put(
        "scout_schedule",
        JSON.stringify(sanitized)
      );

      broadcastEvent({
        type: "scout_schedule_updated",
        schedule: sanitized,
      });

      return jsonResponse({
        success: true,
        schedule: sanitized,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse(
        { error: "Failed to persist scout schedule", details: msg },
        500
      );
    }
  }

  return jsonResponse({ error: "Method Not Allowed" }, 405);
}

/**
 * Edge cron dispatcher for scout runs:
 * Evaluates active windows against current time and dispatches scout.yml if due.
 */
export async function handleScoutScheduleCron(
  env: Env,
  now: Date = new Date()
): Promise<ScheduledCronResult> {
  if (!env.LINKEDIN_AGENT_KV) {
    return { checked: 0, dispatched: 0, errors: ["No KV binding"] };
  }

  // 1. Safety check: circuit breaker and remote paused state
  const rawPaused = await env.LINKEDIN_AGENT_KV.get("paused");
  if (rawPaused !== null) {
    return { checked: 0, dispatched: 0, errors: [] }; // Intentionally silent when paused
  }

  const rawIncident = await env.LINKEDIN_AGENT_KV.get("incident");
  if (rawIncident !== null) {
    return { checked: 0, dispatched: 0, errors: ["Circuit breaker tripped"] };
  }

  // 2. Load schedule
  let schedule: AutomatedCommentWindow[] = defaultScoutWindows;
  const rawSchedule = await env.LINKEDIN_AGENT_KV.get("scout_schedule");
  if (rawSchedule) {
    try {
      const parsed = JSON.parse(rawSchedule);
      if (Array.isArray(parsed) && parsed.length > 0) {
        schedule = parsed;
      }
    } catch {
      schedule = defaultScoutWindows;
    }
  }

  const repoOwner = env.GITHUB_REPO_OWNER;
  const repoName = env.GITHUB_REPO_NAME;
  const pat = env.GITHUB_DISPATCH_PAT;

  if (!repoOwner || !repoName || !pat) {
    return {
      checked: schedule.length,
      dispatched: 0,
      errors: ["GitHub credentials not configured on worker"],
    };
  }

  const currentDay = DAY_NAMES[now.getUTCDay()];
  const nowHours = now.getUTCHours();
  const nowMinutes = now.getUTCMinutes();
  const nowTotalMinutes = nowHours * 60 + nowMinutes;

  const errors: string[] = [];
  let dispatchedCount = 0;
  const updatedSchedule: AutomatedCommentWindow[] = [];

  for (const win of schedule) {
    if (win.status !== "active") {
      updatedSchedule.push(win);
      continue;
    }

    if (!win.days.includes(currentDay)) {
      updatedSchedule.push(win);
      continue;
    }

    // Parse start_time (HH:MM in UTC)
    const [startHStr, startMStr] = (win.start_time || "").split(":");
    const startH = parseInt(startHStr, 10);
    const startM = parseInt(startMStr, 10);
    if (isNaN(startH) || isNaN(startM)) {
      updatedSchedule.push(win);
      continue;
    }

    const startTotalMinutes = startH * 60 + startM;
    // Window is due if current time is within [start_time, start_time + 19 minutes]
    // (covers 15-minute cron resolution plus minor edge drift)
    const diff = nowTotalMinutes - startTotalMinutes;
    const isDue = diff >= 0 && diff < 20;

    if (!isDue) {
      updatedSchedule.push(win);
      continue;
    }

    // Check duplicate dispatch within the last 3 hours
    if (win.last_dispatched_at) {
      const lastTime = new Date(win.last_dispatched_at).getTime();
      if (!isNaN(lastTime) && now.getTime() - lastTime < 3 * 3600 * 1000) {
        updatedSchedule.push(win);
        continue;
      }
    }

    // Dispatch scout.yml workflow
    try {
      const dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/workflows/scout.yml/dispatches`;
      const res = await fetch(dispatchUrl, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${pat}`,
          "User-Agent": "Edge-Relay",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ ref: "main" }),
      });

      if (!res.ok) {
        const text = await res.text();
        errors.push(`Failed dispatching scout window ${win.id}: ${res.status} ${text}`);
        updatedSchedule.push(win);
      } else {
        dispatchedCount++;
        const markedWin: AutomatedCommentWindow = {
          ...win,
          last_dispatched_at: now.toISOString(),
        };
        updatedSchedule.push(markedWin);

        broadcastEvent({
          type: "scout_dispatched",
          window_id: win.id,
          window_title: win.title,
          dispatched_at: now.toISOString(),
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`Error dispatching scout window ${win.id}: ${msg}`);
      updatedSchedule.push(win);
    }
  }

  // Update KV with any new last_dispatched_at timestamps
  if (dispatchedCount > 0) {
    try {
      await env.LINKEDIN_AGENT_KV.put(
        "scout_schedule",
        JSON.stringify(updatedSchedule)
      );
    } catch {
      // Non-fatal if metadata update fails
    }
  }

  return {
    checked: schedule.length,
    dispatched: dispatchedCount,
    errors,
  };
}
