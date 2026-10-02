/**
 * LinkedIn Embedded Authentication & Session Vault Capturer
 *
 * Spawns a dedicated child BrowserWindow for human authentication on LinkedIn,
 * monitors the session cookie jar for authentication completion (li_at and JSESSIONID),
 * formats cookies into Playwright-compatible storage state JSON,
 * and encrypts the session state via Fernet before triggering onSave.
 */

import { BrowserWindow } from "electron";
import { encryptSession } from "../crypto/fernet";

export interface PlaywrightCookie {
  name: string;
  value: string;
  domain: string;
  path: string;
  expires: number;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "Strict" | "Lax" | "None";
}

export interface PlaywrightStorageState {
  cookies: PlaywrightCookie[];
  origins: Array<{
    origin: string;
    localStorage: Array<{ name: string; value: string }>;
  }>;
}

export interface CaptureSessionResult {
  success: boolean;
  error?: string;
}

export interface CookieLike {
  name: string;
  value: string;
  domain?: string;
  path?: string;
  expires?: number;
  expirationDate?: number;
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: string;
}

const DEFAULT_USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

/**
 * Maps an Electron cookie or cookie-like object to Playwright cookie format.
 */
export function mapElectronCookieToPlaywright(cookie: CookieLike): PlaywrightCookie {
  let sameSite: "Strict" | "Lax" | "None" = "Lax";
  if (cookie.sameSite) {
    const s = cookie.sameSite.toLowerCase();
    if (s === "no_restriction" || s === "none") {
      sameSite = "None";
    } else if (s === "strict") {
      sameSite = "Strict";
    } else if (s === "lax" || s === "unspecified") {
      sameSite = "Lax";
    }
  }

  let expires = -1;
  if (typeof cookie.expirationDate === "number") {
    expires = Math.floor(cookie.expirationDate);
  } else if (typeof cookie.expires === "number") {
    expires = Math.floor(cookie.expires);
  }

  return {
    name: cookie.name,
    value: cookie.value,
    domain: cookie.domain || ".linkedin.com",
    path: cookie.path || "/",
    expires,
    httpOnly: Boolean(cookie.httpOnly),
    secure: Boolean(cookie.secure),
    sameSite,
  };
}

/**
 * Formats a list of Electron cookies into Playwright storage state JSON format:
 * { cookies: [...mappedCookies], origins: [] }
 */
export function createPlaywrightStorageState(
  cookies: CookieLike[]
): PlaywrightStorageState {
  return {
    cookies: cookies.map(mapElectronCookieToPlaywright),
    origins: [],
  };
}

/**
 * Spawns a child BrowserWindow navigated to https://www.linkedin.com/login,
 * monitors the cookie jar for li_at, serializes and encrypts the session state,
 * and calls onSave with the Fernet-encrypted ciphertext.
 */
export async function captureLinkedInSession(
  parentWindow: BrowserWindow,
  encryptionKey: string,
  onSave: (encData: string) => Promise<boolean>
): Promise<CaptureSessionResult> {
  if (!encryptionKey || !encryptionKey.trim()) {
    return {
      success: false,
      error: "Session encryption key is required",
    };
  }

  return new Promise<CaptureSessionResult>((resolve) => {
    let completed = false;
    let isProcessing = false;
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    let authWin: BrowserWindow;
    try {
      authWin = new BrowserWindow({
        parent: parentWindow || undefined,
        modal: Boolean(parentWindow),
        width: 640,
        height: 780,
        title: "LinkedIn Login - HITL Agent",
        autoHideMenuBar: true,
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
          sandbox: true,
        },
      });
      if (typeof authWin.removeMenu === "function") {
        authWin.removeMenu();
      }
    } catch (err) {
      resolve({
        success: false,
        error: `Failed to create authentication window: ${err instanceof Error ? err.message : String(err)}`,
      });
      return;
    }

    // Set custom User-Agent to avoid automation detection
    try {
      authWin.webContents.setUserAgent(DEFAULT_USER_AGENT);
    } catch {
      // ignore
    }

    const cookieJar = authWin.webContents.session.cookies;

    const cleanup = () => {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
      try {
        cookieJar.removeListener("changed", onCookieChanged);
      } catch {
        // ignore
      }
    };

    const processCookies = async () => {
      if (completed || isProcessing) return;

      try {
        const allCookies = await cookieJar.get({});
        const linkedinCookies = allCookies.filter(
          (c) =>
            c.domain &&
            (c.domain === ".linkedin.com" ||
              c.domain.endsWith(".linkedin.com") ||
              c.domain === "linkedin.com")
        );

        const liAt = linkedinCookies.find((c) => c.name === "li_at");
        // Verify li_at is present and non-empty
        if (liAt && liAt.value && liAt.value.trim().length > 0) {
          isProcessing = true;
          completed = true;
          cleanup();

          // Format into Playwright storage state JSON: { cookies: [...], origins: [] }
          const storageState = createPlaywrightStorageState(linkedinCookies);
          const storageStateJson = JSON.stringify(storageState);

          // Encrypt storage state using Fernet
          const encryptedSession = encryptSession(storageStateJson, encryptionKey);

          // Call onSave callback
          const saveOk = await onSave(encryptedSession);

          if (!authWin.isDestroyed()) {
            authWin.close();
          }

          if (saveOk) {
            resolve({ success: true });
          } else {
            resolve({
              success: false,
              error: "Failed to persist encrypted session to remote storage",
            });
          }
        }
      } catch (err) {
        if (!completed) {
          // If window was destroyed during check, handle gracefully
          if (authWin.isDestroyed()) {
            cleanup();
            completed = true;
            resolve({
              success: false,
              error: "Authentication window closed before completion",
            });
          }
        }
      } finally {
        isProcessing = false;
      }
    };

    const onCookieChanged = () => {
      void processCookies();
    };

    cookieJar.on("changed", onCookieChanged);
    pollInterval = setInterval(() => {
      void processCookies();
    }, 1200);

    authWin.on("closed", () => {
      cleanup();
      if (!completed) {
        completed = true;
        resolve({
          success: false,
          error: "Authentication window closed before completion",
        });
      }
    });

    authWin.loadURL("https://www.linkedin.com/login").catch((err) => {
      if (!completed) {
        cleanup();
        completed = true;
        resolve({
          success: false,
          error: `Failed to load LinkedIn login page: ${err instanceof Error ? err.message : String(err)}`,
        });
      }
    });
  });
}
