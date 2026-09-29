import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  mapElectronCookieToPlaywright,
  createPlaywrightStorageState,
  captureLinkedInSession,
  type CookieLike,
} from "../electron/auth/linkedinAuth";
import {
  decryptSession,
  encryptSession,
  generateFernetKey,
} from "../electron/crypto/fernet";

// Mock Electron BrowserWindow and session cookies
const mockCookieStore: CookieLike[] = [];
let mockWindowClosedCallback: (() => void) | null = null;
let mockCookieChangedCallback: (() => void) | null = null;
let mockIsDestroyed = false;
let mockCloseFn = vi.fn();

vi.mock("electron", () => {
  return {
    BrowserWindow: vi.fn().mockImplementation(() => {
      mockIsDestroyed = false;
      mockCloseFn = vi.fn(() => {
        mockIsDestroyed = true;
      });

      return {
        webContents: {
          setUserAgent: vi.fn(),
          session: {
            cookies: {
              get: vi.fn().mockImplementation(async () => mockCookieStore),
              on: vi.fn((event: string, cb: () => void) => {
                if (event === "changed") {
                  mockCookieChangedCallback = cb;
                }
              }),
              removeListener: vi.fn(),
            },
          },
        },
        loadURL: vi.fn().mockResolvedValue(undefined),
        close: mockCloseFn,
        isDestroyed: vi.fn(() => mockIsDestroyed),
        on: vi.fn((event: string, cb: () => void) => {
          if (event === "closed") {
            mockWindowClosedCallback = cb;
          }
        }),
      };
    }),
  };
});

describe("LinkedIn Auth & Session Capture Engine", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCookieStore.length = 0;
    mockWindowClosedCallback = null;
    mockCookieChangedCallback = null;
    mockIsDestroyed = false;
  });

  describe("mapElectronCookieToPlaywright", () => {
    it("maps an Electron cookie with expirationDate and no_restriction SameSite to Playwright None", () => {
      const electronCookie: CookieLike = {
        name: "li_at",
        value: "AQEDASampleCookieValueXYZ",
        domain: ".linkedin.com",
        path: "/",
        expirationDate: 1790000000.45,
        httpOnly: true,
        secure: true,
        sameSite: "no_restriction",
      };

      const pwCookie = mapElectronCookieToPlaywright(electronCookie);

      expect(pwCookie.name).toBe("li_at");
      expect(pwCookie.value).toBe("AQEDASampleCookieValueXYZ");
      expect(pwCookie.domain).toBe(".linkedin.com");
      expect(pwCookie.path).toBe("/");
      expect(pwCookie.expires).toBe(1790000000);
      expect(pwCookie.httpOnly).toBe(true);
      expect(pwCookie.secure).toBe(true);
      expect(pwCookie.sameSite).toBe("None");
    });

    it("maps session cookies without expiration date to expires: -1", () => {
      const sessionCookie: CookieLike = {
        name: "JSESSIONID",
        value: '"ajax:123456789"',
        domain: ".linkedin.com",
        path: "/",
        httpOnly: false,
        secure: true,
        sameSite: "lax",
      };

      const pwCookie = mapElectronCookieToPlaywright(sessionCookie);

      expect(pwCookie.name).toBe("JSESSIONID");
      expect(pwCookie.expires).toBe(-1);
      expect(pwCookie.sameSite).toBe("Lax");
      expect(pwCookie.httpOnly).toBe(false);
      expect(pwCookie.secure).toBe(true);
    });

    it("correctly handles strict and unspecified SameSite flags", () => {
      const strictCookie: CookieLike = {
        name: "bcookie",
        value: "v=2&uuid",
        sameSite: "strict",
      };
      expect(mapElectronCookieToPlaywright(strictCookie).sameSite).toBe("Strict");

      const unspecifiedCookie: CookieLike = {
        name: "lidc",
        value: "b=1",
        sameSite: "unspecified",
      };
      expect(mapElectronCookieToPlaywright(unspecifiedCookie).sameSite).toBe("Lax");
    });
  });

  describe("createPlaywrightStorageState", () => {
    it("formats an array of cookies into Playwright storage state JSON format with empty origins", () => {
      const cookies: CookieLike[] = [
        {
          name: "li_at",
          value: "val-li-at",
          domain: ".linkedin.com",
          path: "/",
          expirationDate: 1800000000,
          httpOnly: true,
          secure: true,
          sameSite: "none",
        },
        {
          name: "JSESSIONID",
          value: "ajax:888",
          domain: ".www.linkedin.com",
          path: "/",
          httpOnly: false,
          secure: true,
          sameSite: "lax",
        },
      ];

      const state = createPlaywrightStorageState(cookies);

      expect(state).toHaveProperty("cookies");
      expect(state).toHaveProperty("origins");
      expect(Array.isArray(state.cookies)).toBe(true);
      expect(state.cookies.length).toBe(2);
      expect(state.origins).toEqual([]);

      expect(state.cookies[0].name).toBe("li_at");
      expect(state.cookies[0].value).toBe("val-li-at");
      expect(state.cookies[1].name).toBe("JSESSIONID");
    });
  });

  describe("Storage State Encryption & Decryption Round-trip", () => {
    it("encrypts formatted Playwright storage state using Fernet and round-trips cleanly", () => {
      const key = generateFernetKey();
      const cookies: CookieLike[] = [
        {
          name: "li_at",
          value: "AQEDASampleToken1234567890",
          domain: ".linkedin.com",
          path: "/",
          expirationDate: 1795000000,
          httpOnly: true,
          secure: true,
          sameSite: "no_restriction",
        },
        {
          name: "JSESSIONID",
          value: '"ajax:3344556677"',
          domain: ".linkedin.com",
          path: "/",
          httpOnly: false,
          secure: true,
          sameSite: "lax",
        },
      ];

      const state = createPlaywrightStorageState(cookies);
      const jsonStr = JSON.stringify(state);

      // Encrypt
      const encryptedToken = encryptSession(jsonStr, key);
      expect(typeof encryptedToken).toBe("string");
      expect(encryptedToken.length).toBeGreaterThan(50);

      // Decrypt
      const decryptedJson = decryptSession(encryptedToken, key);
      const parsed = JSON.parse(decryptedJson);

      expect(parsed).toEqual(state);
      expect(parsed.cookies[0].name).toBe("li_at");
      expect(parsed.cookies[0].value).toBe("AQEDASampleToken1234567890");
      expect(parsed.cookies[1].name).toBe("JSESSIONID");
      expect(parsed.origins).toEqual([]);
    });
  });

  describe("captureLinkedInSession", () => {
    it("fails immediately if encryption key is missing or blank", async () => {
      const onSave = vi.fn();
      const result = await captureLinkedInSession(null as any, "", onSave);

      expect(result.success).toBe(false);
      expect(result.error).toContain("Session encryption key is required");
      expect(onSave).not.toHaveBeenCalled();
    });

    it("captures li_at and JSESSIONID, encrypts payload, and calls onSave", async () => {
      const key = generateFernetKey();
      let savedPayload = "";
      const onSave = vi.fn().mockImplementation(async (encData: string) => {
        savedPayload = encData;
        return true;
      });

      // Prepare cookies in jar
      mockCookieStore.push(
        {
          name: "li_at",
          value: "AQEDATestCapturedCookieValue999",
          domain: ".linkedin.com",
          path: "/",
          expirationDate: 1799000000,
          httpOnly: true,
          secure: true,
          sameSite: "no_restriction",
        },
        {
          name: "JSESSIONID",
          value: '"ajax:112233"',
          domain: ".linkedin.com",
          path: "/",
          httpOnly: false,
          secure: true,
          sameSite: "lax",
        }
      );

      const capturePromise = captureLinkedInSession(null as any, key, onSave);

      // Trigger cookie changed event
      if (mockCookieChangedCallback) {
        mockCookieChangedCallback();
      }

      const result = await capturePromise;

      expect(result.success).toBe(true);
      expect(onSave).toHaveBeenCalledTimes(1);
      expect(mockCloseFn).toHaveBeenCalled();

      // Verify the saved payload is valid Fernet ciphertext decrypting to Playwright storage state
      const decrypted = decryptSession(savedPayload, key);
      const parsedState = JSON.parse(decrypted);

      expect(parsedState.cookies.length).toBe(2);
      expect(parsedState.cookies[0].name).toBe("li_at");
      expect(parsedState.cookies[0].value).toBe("AQEDATestCapturedCookieValue999");
      expect(parsedState.origins).toEqual([]);
    });

    it("returns error if user closes auth window before logging in", async () => {
      const key = generateFernetKey();
      const onSave = vi.fn();

      const capturePromise = captureLinkedInSession(null as any, key, onSave);

      // User closes window without cookies populated
      if (mockWindowClosedCallback) {
        mockWindowClosedCallback();
      }

      const result = await capturePromise;

      expect(result.success).toBe(false);
      expect(result.error).toBe("Authentication window closed before completion");
      expect(onSave).not.toHaveBeenCalled();
    });

    it("returns error if onSave returns false", async () => {
      const key = generateFernetKey();
      const onSave = vi.fn().mockResolvedValue(false);

      mockCookieStore.push({
        name: "li_at",
        value: "AQEDATestCookieValue123",
        domain: ".linkedin.com",
      });

      const capturePromise = captureLinkedInSession(null as any, key, onSave);

      if (mockCookieChangedCallback) {
        mockCookieChangedCallback();
      }

      const result = await capturePromise;

      expect(result.success).toBe(false);
      expect(result.error).toBe("Failed to persist encrypted session to remote storage");
      expect(mockCloseFn).toHaveBeenCalled();
    });
  });
});
