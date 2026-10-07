/**
 * Global Datetime & Timezone Utilities.
 * Ensures consistent timezone-aware time and date rendering throughout LinkedAide.
 */

import type { AutomatedCommentWindow } from "../types";

export interface TimezoneOption {
  value: string;
  label: string;
  offset: string;
  region: string;
}

/**
 * Returns the host operating system's default timezone, fallback to "UTC".
 */
export function getDefaultTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Validates whether a given timezone string is recognized by the runtime Intl engine.
 */
export function isValidTimezone(tz: string): boolean {
  if (!tz || typeof tz !== "string") return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/**
 * Computes the formatted UTC offset string (e.g. "UTC+00:00", "UTC-04:00", "UTC+05:30") for a timezone.
 */
export function getTimezoneOffsetString(tz: string, date: Date = new Date()): string {
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      timeZoneName: "longOffset",
    }).formatToParts(date);
    const tzPart = parts.find((p) => p.type === "timeZoneName");
    if (tzPart?.value) {
      return tzPart.value.replace("GMT", "UTC");
    }
  } catch {
    // fallback below
  }
  return "UTC+00:00";
}

/**
 * Curated list of popular global business and tech timezones.
 */
export const POPULAR_TIMEZONES = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)", region: "Global" },
  { value: "America/New_York", label: "New York (Eastern Time)", region: "Americas" },
  { value: "America/Chicago", label: "Chicago (Central Time)", region: "Americas" },
  { value: "America/Denver", label: "Denver (Mountain Time)", region: "Americas" },
  { value: "America/Los_Angeles", label: "San Francisco / LA (Pacific Time)", region: "Americas" },
  { value: "America/Toronto", label: "Toronto (Eastern Time)", region: "Americas" },
  { value: "America/Sao_Paulo", label: "São Paulo (Brasília Time)", region: "Americas" },
  { value: "Europe/London", label: "London (GMT / BST)", region: "Europe" },
  { value: "Europe/Paris", label: "Paris (Central European Time)", region: "Europe" },
  { value: "Europe/Berlin", label: "Berlin (Central European Time)", region: "Europe" },
  { value: "Europe/Amsterdam", label: "Amsterdam (CET / CEST)", region: "Europe" },
  { value: "Europe/Madrid", label: "Madrid (Central European Time)", region: "Europe" },
  { value: "Asia/Dubai", label: "Dubai (Gulf Standard Time)", region: "Middle East" },
  { value: "Asia/Jerusalem", label: "Jerusalem (IST)", region: "Middle East" },
  { value: "Asia/Kolkata", label: "India / Mumbai (IST)", region: "Asia" },
  { value: "Asia/Bangkok", label: "Bangkok / Jakarta (ICT)", region: "Asia" },
  { value: "Asia/Singapore", label: "Singapore (SGT)", region: "Asia" },
  { value: "Asia/Hong_Kong", label: "Hong Kong (HKT)", region: "Asia" },
  { value: "Asia/Tokyo", label: "Tokyo (Japan Standard Time)", region: "Asia" },
  { value: "Asia/Seoul", label: "Seoul (Korea Standard Time)", region: "Asia" },
  { value: "Australia/Sydney", label: "Sydney (AEST / AEDT)", region: "Oceania" },
  { value: "Pacific/Auckland", label: "Auckland (NZST / NZDT)", region: "Oceania" },
  { value: "Pacific/Honolulu", label: "Honolulu (Hawaii Time)", region: "Pacific" },
];

/**
 * Returns a full list of timezone options, combining curated entries with native Intl timezones.
 */
export function getTimezoneOptions(): TimezoneOption[] {
  const result: TimezoneOption[] = [];
  const seen = new Set<string>();

  // 1. Add popular timezones first
  for (const item of POPULAR_TIMEZONES) {
    seen.add(item.value);
    result.push({
      value: item.value,
      label: item.label,
      offset: getTimezoneOffsetString(item.value),
      region: item.region,
    });
  }

  // 2. Add remaining IANA timezones supported by native runtime
  try {
    if (typeof Intl !== "undefined" && typeof (Intl as any).supportedValuesOf === "function") {
      const allZones: string[] = (Intl as any).supportedValuesOf("timeZone");
      for (const zone of allZones) {
        if (!seen.has(zone)) {
          seen.add(zone);
          const slashIdx = zone.indexOf("/");
          const region = slashIdx > 0 ? zone.substring(0, slashIdx).replace(/_/g, " ") : "Other";
          result.push({
            value: zone,
            label: zone.replace(/_/g, " "),
            offset: getTimezoneOffsetString(zone),
            region,
          });
        }
      }
    }
  } catch {
    // Ignore if supportedValuesOf is unavailable
  }

  return result;
}

/**
 * Parses any date-like value into a valid Date instance, or null if invalid.
 */
function toDate(date: Date | string | number | null | undefined): Date | null {
  if (date === null || date === undefined || date === "") return null;
  const d = date instanceof Date ? date : new Date(date);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Formats time in the given timezone (e.g. "14:30:00" or "02:30 PM").
 */
export function formatTime(
  date: Date | string | number | null | undefined,
  timezone: string = "UTC",
  options?: Intl.DateTimeFormatOptions
): string {
  const d = toDate(date);
  if (!d) return String(date || "");
  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      ...options,
    }).format(d);
  } catch {
    return d.toISOString();
  }
}

/**
 * Formats date in the given timezone (e.g. "Oct 7, 2026").
 */
export function formatDate(
  date: Date | string | number | null | undefined,
  timezone: string = "UTC",
  options?: Intl.DateTimeFormatOptions
): string {
  const d = toDate(date);
  if (!d) return String(date || "");
  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      year: "numeric",
      month: "short",
      day: "numeric",
      ...options,
    }).format(d);
  } catch {
    return d.toISOString().split("T")[0];
  }
}

/**
 * Formats combined date and time in the given timezone (e.g. "Oct 7, 2026, 14:30:00 EDT").
 */
export function formatDateTime(
  date: Date | string | number | null | undefined,
  timezone: string = "UTC",
  options?: Intl.DateTimeFormatOptions
): string {
  const d = toDate(date);
  if (!d) return String(date || "");
  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZoneName: "short",
      ...options,
    }).format(d);
  } catch {
    return d.toISOString();
  }
}

/**
 * Formats relative time (e.g. "15m ago", "2h ago", "yesterday"),
 * or falls back to formatDate if older than 7 days.
 */
export function formatTimeAgo(
  date: Date | string | number | null | undefined,
  timezone: string = "UTC"
): string {
  if (typeof date === "string" && (date.includes("ago") || date.includes("just now") || date === "Never")) {
    return date;
  }
  const d = toDate(date);
  if (!d) return String(date || "");

  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return formatDate(d, timezone);
}

/**
 * Determines whether two dates fall on the same calendar day in the given timezone.
 */
export function isSameDayInTimezone(
  d1: Date,
  dateStr: string | null | undefined,
  timezone: string = "UTC"
): boolean {
  if (!dateStr) return false;
  const d2 = toDate(dateStr);
  if (!d2) return false;
  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";

  try {
    const fmt = new Intl.DateTimeFormat("en-CA", {
      timeZone: targetTz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    return fmt.format(d1) === fmt.format(d2);
  } catch {
    return (
      d1.getFullYear() === d2.getFullYear() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getDate() === d2.getDate()
    );
  }
}

/**
 * Converts a UTC HH:MM time string to the user's local timezone HH:MM.
 */
export function convertUtcTimeToLocal(
  timeStr: string,
  timezone: string = "UTC",
  refDate: Date = new Date()
): string {
  if (!timeStr || !timeStr.includes(":")) return timeStr || "08:00";
  const [hStr, mStr] = timeStr.split(":");
  const h = parseInt(hStr, 10);
  const m = parseInt(mStr, 10);
  if (isNaN(h) || isNaN(m)) return timeStr;

  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";
  // Reference date to extract hours/minutes in target timezone taking DST into account
  const d = new Date(
    Date.UTC(
      refDate.getUTCFullYear(),
      refDate.getUTCMonth(),
      refDate.getUTCDate(),
      h,
      m,
      0
    )
  );
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(d);
    const hourPart = parts.find((p) => p.type === "hour")?.value || String(h).padStart(2, "0");
    const minPart = parts.find((p) => p.type === "minute")?.value || String(m).padStart(2, "0");
    return `${hourPart}:${minPart}`;
  } catch {
    return timeStr;
  }
}

/**
 * Converts a local HH:MM time string in the given timezone to UTC HH:MM.
 */
export function convertLocalTimeToUtc(
  timeStr: string,
  timezone: string = "UTC",
  refDate: Date = new Date()
): string {
  if (!timeStr || !timeStr.includes(":")) return timeStr || "08:00";
  const [hStr, mStr] = timeStr.split(":");
  const h = parseInt(hStr, 10);
  const m = parseInt(mStr, 10);
  if (isNaN(h) || isNaN(m)) return timeStr;

  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";
  try {
    const invDate = new Date(
      Date.UTC(
        refDate.getFullYear(),
        refDate.getMonth(),
        refDate.getDate(),
        h,
        m,
        0
      )
    );
    const tzParts = new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      hour: "numeric",
      minute: "numeric",
      hour12: false,
    }).formatToParts(invDate);

    let tzH = h;
    let tzM = m;
    for (const p of tzParts) {
      if (p.type === "hour") tzH = parseInt(p.value, 10);
      if (p.type === "minute") tzM = parseInt(p.value, 10);
    }

    const diffM = (tzH - h) * 60 + (tzM - m);
    let targetUtcM = (h * 60 + m - diffM) % (24 * 60);
    if (targetUtcM < 0) targetUtcM += 24 * 60;
    const utcH = Math.floor(targetUtcM / 60);
    const utcMin = targetUtcM % 60;
    return `${String(utcH).padStart(2, "0")}:${String(utcMin).padStart(2, "0")}`;
  } catch {
    return timeStr;
  }
}

/**
 * Calculates the next upcoming scout time from active comment windows,
 * taking into account active days, current time, and user timezone.
 */
export function calculateNextScoutTime(
  windows: AutomatedCommentWindow[],
  timezone: string = "UTC",
  now: Date = new Date()
): string {
  const activeWindows = (windows || []).filter((w) => w.status === "active");
  if (activeWindows.length === 0) {
    return "No active runs scheduled";
  }

  const targetTz = isValidTimezone(timezone) ? timezone : "UTC";

  let nearestDate: Date | null = null;
  let nearestTimeStr = "";

  // Scan upcoming 8 days to catch the next occurrence
  for (let dayOffset = 0; dayOffset <= 8; dayOffset++) {
    const checkDate = new Date(now.getTime() + dayOffset * 24 * 3600 * 1000);
    const dayCode = new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      weekday: "short",
    }).format(checkDate);

    for (const win of activeWindows) {
      if (!win.days.includes(dayCode)) continue;

      const [startHStr, startMStr] = (win.start_time || "").split(":");
      const startH = parseInt(startHStr, 10);
      const startM = parseInt(startMStr, 10);
      if (isNaN(startH) || isNaN(startM)) continue;

      const candidate = new Date(
        Date.UTC(
          checkDate.getUTCFullYear(),
          checkDate.getUTCMonth(),
          checkDate.getUTCDate(),
          startH,
          startM,
          0
        )
      );

      if (candidate.getTime() > now.getTime()) {
        if (!nearestDate || candidate.getTime() < nearestDate.getTime()) {
          nearestDate = candidate;
          nearestTimeStr = formatTime(candidate, targetTz, {
            hour: "2-digit",
            minute: "2-digit",
          });
        }
      }
    }
  }

  if (!nearestDate) {
    return "None upcoming";
  }

  const isToday = isSameDayInTimezone(nearestDate, now.toISOString(), targetTz);
  const tomorrow = new Date(now.getTime() + 24 * 3600 * 1000);
  const isTomorrow = isSameDayInTimezone(nearestDate, tomorrow.toISOString(), targetTz);
  const offsetPart = getTimezoneOffsetString(targetTz, nearestDate);

  if (isToday) {
    return `Today at ${nearestTimeStr} (${offsetPart})`;
  } else if (isTomorrow) {
    return `Tomorrow at ${nearestTimeStr} (${offsetPart})`;
  } else {
    const weekday = new Intl.DateTimeFormat("en-US", {
      timeZone: targetTz,
      weekday: "short",
    }).format(nearestDate);
    return `${weekday} at ${nearestTimeStr} (${offsetPart})`;
  }
}
