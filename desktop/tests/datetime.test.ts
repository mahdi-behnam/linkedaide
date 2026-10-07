import { describe, it, expect } from "vitest";
import {
  getDefaultTimezone,
  isValidTimezone,
  getTimezoneOffsetString,
  getTimezoneOptions,
  formatTime,
  formatDate,
  formatDateTime,
  formatTimeAgo,
  isSameDayInTimezone,
} from "../src/utils/datetime";

describe("Datetime & Timezone Utilities", () => {
  it("getDefaultTimezone returns a valid IANA timezone string", () => {
    const tz = getDefaultTimezone();
    expect(typeof tz).toBe("string");
    expect(tz.length).toBeGreaterThan(0);
    expect(isValidTimezone(tz)).toBe(true);
  });

  it("isValidTimezone correctly validates valid and invalid timezones", () => {
    expect(isValidTimezone("UTC")).toBe(true);
    expect(isValidTimezone("America/New_York")).toBe(true);
    expect(isValidTimezone("Europe/London")).toBe(true);
    expect(isValidTimezone("Asia/Tokyo")).toBe(true);
    expect(isValidTimezone("Invalid/NonExistent_Zone")).toBe(false);
    expect(isValidTimezone("")).toBe(false);
  });

  it("getTimezoneOffsetString returns expected UTC offset format", () => {
    const utcOffset = getTimezoneOffsetString("UTC");
    expect(utcOffset).toMatch(/UTC\+00:00|UTC/);

    const nyOffset = getTimezoneOffsetString("America/New_York");
    expect(nyOffset).toMatch(/^UTC[+-]\d{2}:\d{2}$/);
  });

  it("getTimezoneOptions returns a comprehensive list of timezone options", () => {
    const options = getTimezoneOptions();
    expect(options.length).toBeGreaterThan(20);

    const utcOpt = options.find((o) => o.value === "UTC");
    expect(utcOpt).toBeDefined();
    expect(utcOpt?.label).toContain("UTC");

    const nyOpt = options.find((o) => o.value === "America/New_York");
    expect(nyOpt).toBeDefined();
  });

  it("formatTime formats correctly across different timezones", () => {
    // 2026-10-07 12:00:00 UTC
    const date = new Date("2026-10-07T12:00:00Z");

    const utcTime = formatTime(date, "UTC");
    expect(utcTime).toBe("12:00:00");

    const nyTime = formatTime(date, "America/New_York");
    // EDT is UTC-4 in October -> 08:00:00
    expect(nyTime).toBe("08:00:00");

    const tokyoTime = formatTime(date, "Asia/Tokyo");
    // JST is UTC+9 -> 21:00:00
    expect(tokyoTime).toBe("21:00:00");
  });

  it("formatDate formats dates correctly across timezones", () => {
    // 2026-10-07 23:30:00 UTC
    const date = new Date("2026-10-07T23:30:00Z");

    const nyDate = formatDate(date, "America/New_York");
    expect(nyDate).toContain("Oct 7, 2026");

    const tokyoDate = formatDate(date, "Asia/Tokyo");
    // In Tokyo, 23:30 UTC is already Oct 8!
    expect(tokyoDate).toContain("Oct 8, 2026");
  });

  it("formatDateTime formats complete date and time with timezone indicator", () => {
    const date = new Date("2026-10-07T12:00:00Z");
    const formatted = formatDateTime(date, "UTC");

    expect(formatted).toContain("Oct 7, 2026");
    expect(formatted).toContain("12:00:00");
    expect(formatted).toContain("UTC");
  });

  it("formatTimeAgo handles relative timestamps appropriately", () => {
    expect(formatTimeAgo("15m ago")).toBe("15m ago");
    expect(formatTimeAgo("just now")).toBe("just now");
    expect(formatTimeAgo("Never")).toBe("Never");

    const now = new Date();
    expect(formatTimeAgo(now)).toBe("just now");

    const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000);
    expect(formatTimeAgo(tenMinutesAgo)).toBe("10m ago");

    const threeHoursAgo = new Date(Date.now() - 3 * 3600 * 1000);
    expect(formatTimeAgo(threeHoursAgo)).toBe("3h ago");

    const twoDaysAgo = new Date(Date.now() - 2 * 86400 * 1000);
    expect(formatTimeAgo(twoDaysAgo)).toBe("2d ago");
  });

  it("isSameDayInTimezone respects timezone boundaries", () => {
    // 2026-10-07 23:30:00 UTC
    const postTimeIso = "2026-10-07T23:30:00Z";

    // Day date for Oct 7
    const oct7 = new Date("2026-10-07T12:00:00Z");
    // Day date for Oct 8
    const oct8 = new Date("2026-10-08T12:00:00Z");

    // In New York (EDT, UTC-4), 23:30 UTC is 19:30 on Oct 7
    expect(isSameDayInTimezone(oct7, postTimeIso, "America/New_York")).toBe(true);
    expect(isSameDayInTimezone(oct8, postTimeIso, "America/New_York")).toBe(false);

    // In Tokyo (JST, UTC+9), 23:30 UTC is 08:30 on Oct 8
    expect(isSameDayInTimezone(oct7, postTimeIso, "Asia/Tokyo")).toBe(false);
    expect(isSameDayInTimezone(oct8, postTimeIso, "Asia/Tokyo")).toBe(true);
  });
});
