import { describe, it, expect } from "vitest";
import {
  formatBytes,
  formatSpeed,
  formatEta,
} from "../src/components/updater/updaterUtils";

describe("updaterUtils", () => {
  describe("formatBytes", () => {
    it("handles zero, negative, and invalid values gracefully", () => {
      expect(formatBytes(0)).toBe("0 B");
      expect(formatBytes(-100)).toBe("0 B");
      expect(formatBytes(NaN)).toBe("0 B");
      expect(formatBytes(Infinity)).toBe("0 B");
    });

    it("formats bytes correctly", () => {
      expect(formatBytes(500)).toBe("500 B");
      expect(formatBytes(1023)).toBe("1023 B");
    });

    it("formats kilobytes correctly", () => {
      expect(formatBytes(1024)).toBe("1.0 KB");
      expect(formatBytes(1536)).toBe("1.5 KB");
      expect(formatBytes(500 * 1024)).toBe("500.0 KB");
    });

    it("formats megabytes correctly", () => {
      expect(formatBytes(1024 * 1024)).toBe("1.0 MB");
      expect(formatBytes(54.8 * 1024 * 1024)).toBe("54.8 MB");
    });

    it("formats gigabytes correctly", () => {
      expect(formatBytes(1024 * 1024 * 1024)).toBe("1.0 GB");
      expect(formatBytes(2.5 * 1024 * 1024 * 1024)).toBe("2.5 GB");
    });
  });

  describe("formatSpeed", () => {
    it("handles zero, negative, and invalid values", () => {
      expect(formatSpeed(0)).toBe("0 KB/s");
      expect(formatSpeed(-50)).toBe("0 KB/s");
      expect(formatSpeed(NaN)).toBe("0 KB/s");
    });

    it("formats bytes per second", () => {
      expect(formatSpeed(500)).toBe("500 B/s");
    });

    it("formats kilobytes per second", () => {
      expect(formatSpeed(1024)).toBe("1.0 KB/s");
      expect(formatSpeed(450 * 1024)).toBe("450.0 KB/s");
    });

    it("formats megabytes per second", () => {
      expect(formatSpeed(1024 * 1024)).toBe("1.0 MB/s");
      expect(formatSpeed(3.4 * 1024 * 1024)).toBe("3.4 MB/s");
    });
  });

  describe("formatEta", () => {
    it("handles zero, negative, and invalid values", () => {
      expect(formatEta(0)).toBe("calculating...");
      expect(formatEta(-5)).toBe("calculating...");
      expect(formatEta(NaN)).toBe("calculating...");
      expect(formatEta(Infinity)).toBe("calculating...");
    });

    it("formats seconds", () => {
      expect(formatEta(1)).toBe("1s left");
      expect(formatEta(25)).toBe("25s left");
      expect(formatEta(59)).toBe("59s left");
    });

    it("formats minutes and remaining seconds", () => {
      expect(formatEta(60)).toBe("1m left");
      expect(formatEta(75)).toBe("1m 15s left");
      expect(formatEta(184)).toBe("3m 4s left");
    });

    it("formats hours and remaining minutes", () => {
      expect(formatEta(3600)).toBe("1h left");
      expect(formatEta(3660)).toBe("1h 1m left");
      expect(formatEta(7320)).toBe("2h 2m left");
    });
  });
});
