import { describe, it, expect, vi, beforeEach } from "vitest";
import worker, { Env, inferContentType } from "../src/index";

describe("Cloudflare R2 Media Vault API Suite", () => {
  const mockApiSecret = "test-desktop-api-secret-123";

  const createMockR2 = (initialObjects: Record<string, { body: Uint8Array | string; contentType?: string }> = {}) => {
    const store = new Map<string, { body: Uint8Array | string; contentType?: string }>(
      Object.entries(initialObjects)
    );

    return {
      store,
      bucket: {
        get: vi.fn(async (key: string) => {
          const item = store.get(key);
          if (!item) return null;
          return {
            body: item.body,
            httpMetadata: {
              contentType: item.contentType,
            },
          };
        }),
        put: vi.fn(async (key: string, value: ArrayBuffer | Uint8Array, options?: { httpMetadata?: { contentType?: string } }) => {
          store.set(key, {
            body: new Uint8Array(value),
            contentType: options?.httpMetadata?.contentType,
          });
          return { key };
        }),
        delete: vi.fn(async (key: string) => {
          store.delete(key);
        }),
      } as unknown as R2Bucket,
    };
  };

  const createMockContext = () => ({
    waitUntil: vi.fn((promise: Promise<unknown>) => promise),
    passThroughOnException: vi.fn(),
    props: {},
  });

  const getBaseEnv = (r2Bucket?: R2Bucket): Env => ({
    TELEGRAM_WEBHOOK_SECRET: "test-webhook-secret",
    TELEGRAM_BOT_TOKEN: "123:TOKEN",
    TELEGRAM_AUTHORIZED_CHAT_ID: "12345",
    GITHUB_DISPATCH_PAT: "ghp_mock",
    GITHUB_REPO_OWNER: "owner",
    GITHUB_REPO_NAME: "repo",
    DESKTOP_API_SECRET: mockApiSecret,
    SCREENSHOTS_BUCKET: r2Bucket,
  });

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("inferContentType helper", () => {
    it("correctly identifies common MIME types", () => {
      expect(inferContentType("screenshots/pic.png")).toBe("image/png");
      expect(inferContentType("carousels/doc.pdf")).toBe("application/pdf");
      expect(inferContentType("img/photo.jpg")).toBe("image/jpeg");
      expect(inferContentType("img/photo.jpeg")).toBe("image/jpeg");
      expect(inferContentType("banner.webp")).toBe("image/webp");
      expect(inferContentType("anim.gif")).toBe("image/gif");
      expect(inferContentType("vector.svg")).toBe("image/svg+xml");
      expect(inferContentType("archive.bin")).toBe("application/octet-stream");
    });
  });

  describe("PUT /api/media/*", () => {
    it("returns 401 when Authorization header is missing", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/screenshots/test.png", {
        method: "PUT",
        body: new Uint8Array([1, 2, 3]),
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(401);
      const data = (await res.json()) as { error: string };
      expect(data.error).toBe("Unauthorized");
    });

    it("returns 401 when Authorization Bearer token is invalid", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/screenshots/test.png", {
        method: "PUT",
        headers: { Authorization: "Bearer wrong-secret" },
        body: new Uint8Array([1, 2, 3]),
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(401);
    });

    it("returns 500 when SCREENSHOTS_BUCKET is not bound", async () => {
      const env = getBaseEnv(undefined);
      const req = new Request("http://localhost/api/media/screenshots/test.png", {
        method: "PUT",
        headers: { Authorization: `Bearer ${mockApiSecret}` },
        body: new Uint8Array([1, 2, 3]),
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(500);
      const data = (await res.json()) as { error: string };
      expect(data.error).toBe("R2 bucket not configured");
    });

    it("returns 400 when media key is missing", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/", {
        method: "PUT",
        headers: { Authorization: `Bearer ${mockApiSecret}` },
        body: new Uint8Array([1, 2, 3]),
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(400);
      const data = (await res.json()) as { error: string };
      expect(data.error).toBe("Media key is required");
    });

    it("successfully uploads a screenshot PNG and stores in R2", async () => {
      const { bucket, store } = createMockR2();
      const env = getBaseEnv(bucket);
      const pngBytes = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);

      const req = new Request("http://localhost/api/media/screenshots/success_comment_abc.png", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
        },
        body: pngBytes,
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(200);
      const data = (await res.json()) as { success: boolean; key: string; size: number };
      expect(data.success).toBe(true);
      expect(data.key).toBe("screenshots/success_comment_abc.png");
      expect(data.size).toBe(pngBytes.byteLength);

      expect(bucket.put).toHaveBeenCalledWith(
        "screenshots/success_comment_abc.png",
        expect.any(ArrayBuffer),
        { httpMetadata: { contentType: "image/png" } }
      );
      expect(store.has("screenshots/success_comment_abc.png")).toBe(true);
    });

    it("correctly sets content type for PDF carousel uploads", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const pdfBytes = new Uint8Array([37, 80, 68, 70]);

      const req = new Request("http://localhost/api/media/carousels/my-post.pdf", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
        },
        body: pdfBytes,
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(200);
      expect(bucket.put).toHaveBeenCalledWith(
        "carousels/my-post.pdf",
        expect.any(ArrayBuffer),
        { httpMetadata: { contentType: "application/pdf" } }
      );
    });
  });

  describe("GET /api/media/*", () => {
    it("returns 401 when neither Authorization header nor query token is provided", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/screenshots/test.png", {
        method: "GET",
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(401);
    });

    it("returns 401 when query token is incorrect", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/screenshots/test.png?token=wrong-token", {
        method: "GET",
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(401);
    });

    it("returns 500 when SCREENSHOTS_BUCKET is not bound", async () => {
      const env = getBaseEnv(undefined);
      const req = new Request(`http://localhost/api/media/screenshots/test.png?token=${mockApiSecret}`, {
        method: "GET",
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(500);
    });

    it("returns 404 when media key is not found in R2", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request(`http://localhost/api/media/screenshots/non-existent.png?token=${mockApiSecret}`, {
        method: "GET",
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(404);
      const data = (await res.json()) as { error: string };
      expect(data.error).toBe("Media object not found");
    });

    it("serves media successfully via ?token= query parameter", async () => {
      const samplePng = new Uint8Array([137, 80, 78, 71]);
      const { bucket } = createMockR2({
        "screenshots/success_comment_abc.png": {
          body: samplePng,
          contentType: "image/png",
        },
      });
      const env = getBaseEnv(bucket);

      const req = new Request(
        `http://localhost/api/media/screenshots/success_comment_abc.png?token=${mockApiSecret}`,
        { method: "GET" }
      );

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(200);
      expect(res.headers.get("Content-Type")).toBe("image/png");
      expect(res.headers.get("Cache-Control")).toBe("public, max-age=86400");
    });

    it("serves media successfully via Bearer Authorization header", async () => {
      const samplePdf = new Uint8Array([37, 80, 68, 70]);
      const { bucket } = createMockR2({
        "carousels/my-post.pdf": {
          body: samplePdf,
          contentType: "application/pdf",
        },
      });
      const env = getBaseEnv(bucket);

      const req = new Request("http://localhost/api/media/carousels/my-post.pdf", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
        },
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(200);
      expect(res.headers.get("Content-Type")).toBe("application/pdf");
      expect(res.headers.get("Cache-Control")).toBe("public, max-age=86400");
    });

    it("returns 405 Method Not Allowed for unsupported methods like POST on media endpoint", async () => {
      const { bucket } = createMockR2();
      const env = getBaseEnv(bucket);
      const req = new Request("http://localhost/api/media/screenshots/test.png", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mockApiSecret}`,
        },
      });

      const res = await worker.fetch(req, env, createMockContext());
      expect(res.status).toBe(405);
    });
  });
});
