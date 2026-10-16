/**
 * Release Notes Sanitizer and Formatter
 *
 * Safely parses and sanitizes release notes from electron-updater / GitHub Releases.
 * Supports structured HTML, markdown, and plain-text changelogs while neutralizing
 * scripts, style injections, unsafe attributes, and malformed tags.
 */

const ALLOWED_TAGS = new Set([
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "p",
  "br",
  "hr",
  "ul",
  "ol",
  "li",
  "strong",
  "b",
  "em",
  "i",
  "u",
  "s",
  "del",
  "code",
  "pre",
  "a",
  "blockquote",
  "span",
  "div",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
]);

const DANGEROUS_TAGS = new Set([
  "script",
  "style",
  "iframe",
  "object",
  "embed",
  "form",
  "input",
  "button",
  "textarea",
  "select",
  "svg",
  "canvas",
  "base",
  "link",
  "meta",
  "applet",
  "audio",
  "video",
]);

/**
 * Checks whether content contains block HTML tags.
 */
export function containsHtmlTags(content: string): boolean {
  return /<\/?(ul|ol|li|p|h[1-6]|table|div|blockquote|pre|hr|a|strong|b|em|code)[^>]*>/i.test(
    content,
  );
}

/**
 * Converts markdown-style constructs and plain-text lists to HTML.
 */
function convertMarkdownToHtml(raw: string): string {
  let content = raw;

  // Headings
  content = content.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  content = content.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  content = content.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // Bold & italic
  content = content.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  content = content.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  content = content.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // Inline code
  content = content.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Links [text](url)
  content = content.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2">$1</a>',
  );

  // Lists and paragraphs
  const lines = content.split("\n");
  let inList = false;
  let listType: "ul" | "ol" | null = null;
  const processed: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/);
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);

    if (bulletMatch) {
      if (!inList || listType !== "ul") {
        if (inList && listType) processed.push(`</${listType}>`);
        processed.push("<ul>");
        inList = true;
        listType = "ul";
      }
      processed.push(`<li>${bulletMatch[1]}</li>`);
    } else if (numMatch) {
      if (!inList || listType !== "ol") {
        if (inList && listType) processed.push(`</${listType}>`);
        processed.push("<ol>");
        inList = true;
        listType = "ol";
      }
      processed.push(`<li>${numMatch[2]}</li>`);
    } else {
      if (inList && listType) {
        processed.push(`</${listType}>`);
        inList = false;
        listType = null;
      }
      if (trimmed) {
        if (/^<h[1-6]>.*<\/h[1-6]>$/i.test(trimmed)) {
          processed.push(trimmed);
        } else {
          processed.push(`<p>${trimmed}</p>`);
        }
      }
    }
  }

  if (inList && listType) {
    processed.push(`</${listType}>`);
  }

  return processed.join("\n");
}

/**
 * Sanitizes an HTML DOM tree recursively.
 */
function sanitizeElement(node: Node): void {
  const children = Array.from(node.childNodes);
  for (const child of children) {
    if (child.nodeType === 1) {
      // Element node
      const el = child as HTMLElement;
      const tag = el.tagName.toLowerCase();

      // Completely remove dangerous elements and their subtrees
      if (DANGEROUS_TAGS.has(tag)) {
        el.remove();
        continue;
      }

      // If not in allowed list, unwrap children into parent
      if (!ALLOWED_TAGS.has(tag)) {
        while (el.firstChild) {
          node.insertBefore(el.firstChild, el);
        }
        el.remove();
        continue;
      }

      // Sanitize attributes
      const attrs = Array.from(el.attributes);
      for (const attr of attrs) {
        const name = attr.name.toLowerCase();

        // Strip event handlers and styles
        if (name.startsWith("on") || name === "style") {
          el.removeAttribute(attr.name);
          continue;
        }

        // Validate links
        if (tag === "a") {
          if (name === "href") {
            const val = attr.value.trim().toLowerCase();
            const isSafeUrl =
              val.startsWith("http://") ||
              val.startsWith("https://") ||
              val.startsWith("mailto:") ||
              val.startsWith("#");
            if (!isSafeUrl) {
              el.removeAttribute("href");
            }
          } else if (
            name !== "target" &&
            name !== "rel" &&
            name !== "title"
          ) {
            el.removeAttribute(attr.name);
          }
        } else {
          // Disallow arbitrary attributes on other tags
          el.removeAttribute(attr.name);
        }
      }

      // Enforce safe target and rel on all links
      if (tag === "a") {
        el.setAttribute("target", "_blank");
        el.setAttribute("rel", "noopener noreferrer");
      }

      // Recurse into children
      sanitizeElement(el);
    }
  }
}

/**
 * Formats and sanitizes release notes into secure, render-ready HTML.
 */
export function formatAndSanitizeReleaseNotes(
  raw: string | undefined | null,
): string {
  if (!raw || typeof raw !== "string") {
    return "";
  }

  const trimmed = raw.trim();
  if (!trimmed) {
    return "";
  }

  // If content is not HTML, convert markdown / plain lists first
  const content = containsHtmlTags(trimmed)
    ? trimmed
    : convertMarkdownToHtml(trimmed);

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(content, "text/html");
    sanitizeElement(doc.body);
    return doc.body.innerHTML;
  } catch (err) {
    console.warn("Failed parsing release notes with DOMParser:", err);
    // Safe fallback: strip tags entirely if parsing failed
    return content.replace(/<[^>]*>/g, "");
  }
}
