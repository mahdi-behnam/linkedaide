// @vitest-environment happy-dom
import { describe, it, expect } from "vitest";
import {
  formatAndSanitizeReleaseNotes,
  containsHtmlTags,
} from "../src/components/updater/releaseNotesSanitizer";

describe("releaseNotesSanitizer", () => {
  it("returns empty string for null, undefined, or empty inputs", () => {
    expect(formatAndSanitizeReleaseNotes(null)).toBe("");
    expect(formatAndSanitizeReleaseNotes(undefined)).toBe("");
    expect(formatAndSanitizeReleaseNotes("")).toBe("");
    expect(formatAndSanitizeReleaseNotes("   ")).toBe("");
  });

  it("detects HTML tags properly", () => {
    expect(containsHtmlTags("<h2>1.6.0</h2>")).toBe(true);
    expect(containsHtmlTags("<ul><li>item</li></ul>")).toBe(true);
    expect(containsHtmlTags("<a href=\"url\">link</a>")).toBe(true);
    expect(containsHtmlTags("- Plain bullet item\n- Second item")).toBe(false);
  });

  it("renders structured HTML changelog correctly and preserves hierarchy", () => {
    const rawHtml = `<h2><a href="https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0">1.6.0</a> (2026-10-16)</h2>
<h3>Features</h3>
<ul>
<li><strong>desktop:</strong> add fork drift detection (<a href="https://github.com/mahdi-behnam/linkedaide/commit/1234567">1234567</a>)</li>
</ul>`;

    const sanitized = formatAndSanitizeReleaseNotes(rawHtml);
    expect(sanitized).toContain("<h2>");
    expect(sanitized).toContain("<h3>Features</h3>");
    expect(sanitized).toContain("<ul>");
    expect(sanitized).toContain("<li><strong>desktop:</strong> add fork drift detection");
    expect(sanitized).toContain('target="_blank"');
    expect(sanitized).toContain('rel="noopener noreferrer"');
    expect(sanitized).toContain('href="https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0"');
  });

  it("strips malicious script tags, onerror handlers, and javascript: links", () => {
    const malicious = `<h3>Security Update</h3>
<script>alert("pwned")</script>
<img src="x" onerror="alert(1)" />
<a href="javascript:alert(2)">Malicious Link</a>
<p style="background: red;" onclick="doBad()">Safe text</p>`;

    const sanitized = formatAndSanitizeReleaseNotes(malicious);
    expect(sanitized).not.toContain("<script");
    expect(sanitized).not.toContain("alert");
    expect(sanitized).not.toContain("onerror");
    expect(sanitized).not.toContain("javascript:");
    expect(sanitized).not.toContain("onclick");
    expect(sanitized).not.toContain("style=");
    expect(sanitized).toContain("<p>Safe text</p>");
  });

  it("converts plain text bullet lists and markdown headings into HTML", () => {
    const markdown = `## 1.6.0
### Features
- **desktop:** add live progress
- **telemetry:** improve speed calculation

[Documentation](https://linkedaide.com/docs)`;

    const sanitized = formatAndSanitizeReleaseNotes(markdown);
    expect(sanitized).toContain("<h2>1.6.0</h2>");
    expect(sanitized).toContain("<h3>Features</h3>");
    expect(sanitized).toContain("<ul>");
    expect(sanitized).toContain("<li><strong>desktop:</strong> add live progress</li>");
    expect(sanitized).toContain('href="https://linkedaide.com/docs"');
  });
});
