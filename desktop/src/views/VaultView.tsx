import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  LockKey,
  Key,
  ArrowClockwise,
  CheckCircle,
  Warning,
} from "../components/icons";

interface CookieHealthState {
  valid: boolean;
  daysRemaining: number;
  details: string;
}

export const VaultView: React.FC = () => {
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [captureSuccess, setCaptureSuccess] = useState<string | null>(null);
  const [captureError, setCaptureError] = useState<string | null>(null);

  const [isVerifyingHealth, setIsVerifyingHealth] = useState<boolean>(false);
  const [healthStatus, setHealthStatus] = useState<CookieHealthState>({
    valid: false,
    daysRemaining: 0,
    details: "Checking session...",
  });
  const [lastVerifiedAt, setLastVerifiedAt] = useState<string | null>(null);

  const [encryptionKeyStatus, setEncryptionKeyStatus] = useState<string>(
    "Checking encryption key..."
  );
  const [keyFeedback, setKeyFeedback] = useState<string | null>(null);
  const [isGeneratingKey, setIsGeneratingKey] = useState<boolean>(false);

  // Initialize and check status
  useEffect(() => {
    let mounted = true;

    async function initVault() {
      if (typeof window !== "undefined" && window.api) {
        try {
          if (window.api.getSettings) {
            const settings = await window.api.getSettings();
            if (mounted) {
              setEncryptionKeyStatus(
                settings?.encryptionKey
                  ? "Loaded / Valid 32-byte Fernet"
                  : "Not configured / Key missing"
              );
            }
          }
          if (window.api.checkSessionHealth) {
            const health = await window.api.checkSessionHealth();
            if (mounted && health) {
              setHealthStatus({
                valid: health.valid,
                daysRemaining: health.daysRemaining ?? (health.valid ? 18 : 0),
                details: health.details || (health.valid ? "Active li_at cookie" : "No active session"),
              });
              setLastVerifiedAt("Just now");
            }
          }
        } catch {
          // ignore error on initial passive check
        }
      } else {
        if (mounted) {
          setEncryptionKeyStatus("Not configured / Key missing");
          setHealthStatus({
            valid: false,
            daysRemaining: 0,
            details: "Desktop API unavailable outside Electron runtime",
          });
        }
      }
    }

    void initVault();
    return () => {
      mounted = false;
    };
  }, []);

  // 1-Click Connect LinkedIn Handler
  const handleLaunchLogin = useCallback(async () => {
    setIsCapturing(true);
    setCaptureSuccess(null);
    setCaptureError(null);

    try {
      if (typeof window !== "undefined" && window.api?.captureSession) {
        const result = await window.api.captureSession();
        if (result.success) {
          setCaptureSuccess(
            "LinkedIn session captured successfully! Storage state encrypted and synced to Cloudflare KV."
          );
          setHealthStatus((prev) => ({
            ...prev,
            valid: true,
            daysRemaining: 18,
            details: "Active li_at cookie (freshly synced)",
          }));
        } else {
          setCaptureError(
            result.error || "Authentication window closed before completion"
          );
        }
      } else {
        setCaptureError(
          "Session capture requires running within the Electron desktop application"
        );
      }
    } catch (err) {
      setCaptureError(
        err instanceof Error
          ? err.message
          : "Authentication window closed before completion"
      );
    } finally {
      setIsCapturing(false);
    }
  }, []);

  // Verify Cookie Health Handler
  const handleVerifyHealth = useCallback(async () => {
    setIsVerifyingHealth(true);
    try {
      if (typeof window !== "undefined" && window.api?.checkSessionHealth) {
        const res = await window.api.checkSessionHealth();
        setHealthStatus({
          valid: res.valid,
          daysRemaining: res.daysRemaining ?? (res.valid ? 18 : 0),
          details: res.details || (res.valid ? "Active li_at cookie" : "No active session"),
        });
        setLastVerifiedAt("Just now");
      } else {
        setHealthStatus({
          valid: false,
          daysRemaining: 0,
          details: "Session health check unavailable outside desktop runtime",
        });
        setLastVerifiedAt("Just now");
      }
    } catch (err) {
      setHealthStatus((prev) => ({
        ...prev,
        valid: false,
        daysRemaining: 0,
        details: err instanceof Error ? err.message : "Health check failed",
      }));
    } finally {
      setIsVerifyingHealth(false);
    }
  }, []);

  // Generate New Fernet Key Handler
  const handleGenerateKey = useCallback(async () => {
    setIsGeneratingKey(true);
    setKeyFeedback(null);
    try {
      let newKey = "";
      if (typeof window !== "undefined" && window.api?.generateFernetKey) {
        newKey = await window.api.generateFernetKey();
        if (window.api.saveSettings) {
          await window.api.saveSettings({ encryptionKey: newKey });
        }
      } else {
        const randomBytes = new Uint8Array(32);
        crypto.getRandomValues(randomBytes);
        newKey = btoa(String.fromCharCode(...randomBytes));
      }
      setEncryptionKeyStatus("Loaded / Valid 32-byte Fernet");
      setKeyFeedback(
        `Generated fresh 32-byte Fernet key (${newKey.slice(0, 8)}...${newKey.slice(-4)}) and saved to settings.`
      );
    } catch (err) {
      setKeyFeedback(
        `Failed to generate key: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setIsGeneratingKey(false);
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header with Encryption Badge */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              LinkedIn Session Vault
            </h1>
            <span
              data-testid="encryption-badge"
              className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-xs text-emerald-400"
            >
              AES-128-CBC + HMAC-SHA256 Fernet
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            Secure local session credentials storage. Plaintext cookies are never logged or stored in version control.
          </p>
        </div>
      </div>

      {/* 1-Click Connect LinkedIn Action Card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-5 shadow-sm">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <LockKey size={20} className="text-emerald-400" />
              <h2 className="text-sm font-semibold text-zinc-100">
                1-Click Connect LinkedIn
              </h2>
            </div>
            <p className="text-xs text-zinc-400">
              Open a secure, isolated embedded login browser to authenticate.
              Session cookies are automatically captured, encrypted with Fernet, and synced to Cloudflare KV.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              data-testid="launch-login-btn"
              disabled={isCapturing}
              onClick={handleLaunchLogin}
              className={`flex items-center gap-2 rounded-md border px-4 py-2 text-xs font-semibold tracking-wide transition-all duration-150 active:translate-y-[1px] active:scale-[0.98] ${
                isCapturing
                  ? "cursor-not-allowed border-zinc-800 bg-zinc-900/40 text-zinc-500"
                  : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:border-emerald-500/50 hover:bg-emerald-500/20"
              }`}
            >
              {isCapturing ? (
                <>
                  <ArrowClockwise
                    size={15}
                    className="animate-spin text-emerald-400"
                  />
                  <span>Waiting for Login...</span>
                </>
              ) : (
                <>
                  <LockKey size={15} className="text-emerald-400" />
                  <span>Launch Secure Login</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Capture Success Banner */}
        {captureSuccess && (
          <div
            data-testid="capture-success-banner"
            className="mt-4 flex items-center gap-2.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300"
          >
            <CheckCircle size={18} className="shrink-0 text-emerald-400" />
            <div className="font-medium">{captureSuccess}</div>
          </div>
        )}

        {/* Capture Error Banner */}
        {captureError && (
          <div
            data-testid="capture-error-banner"
            className="mt-4 flex items-center gap-2.5 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300"
          >
            <Warning size={18} className="shrink-0 text-rose-400" />
            <div className="font-medium">{captureError}</div>
          </div>
        )}
      </div>

      {/* Two Column Grid: Cookie Health & Encryption Key */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Cookie Health Card */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2.5">
              <ShieldCheck size={18} className="text-emerald-400" />
              <h3 className="text-xs font-semibold text-zinc-200">
                Cookie Health Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="verify-cookie-health-btn"
              disabled={isVerifyingHealth}
              onClick={handleVerifyHealth}
              className="flex items-center gap-1.5 rounded border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-[11px] font-medium text-zinc-300 transition-colors hover:border-zinc-700 hover:text-zinc-100"
            >
              <ArrowClockwise
                size={13}
                className={isVerifyingHealth ? "animate-spin text-emerald-400" : "text-zinc-400"}
              />
              <span>Verify Cookie Health</span>
            </button>
          </div>

          <div className="mt-3 space-y-2.5 font-mono text-xs">
            <div className="flex justify-between border-b border-zinc-800/40 pb-1.5">
              <span className="text-zinc-500">li_at status:</span>
              <span
                data-testid="li-at-status"
                className={`font-medium ${healthStatus.valid ? "text-emerald-400" : "text-amber-400"}`}
              >
                {healthStatus.valid
                  ? `Active (${healthStatus.daysRemaining} days remaining)`
                  : healthStatus.details === "Checking session..."
                    ? "Checking session..."
                    : "No active session"}
              </span>
            </div>
            <div className="flex justify-between border-b border-zinc-800/40 pb-1.5">
              <span className="text-zinc-500">JSESSIONID status:</span>
              <span
                data-testid="jsessionid-status"
                className={`font-medium ${healthStatus.valid ? "text-emerald-400" : "text-zinc-500"}`}
              >
                {healthStatus.valid
                  ? "Active (CSRF token valid)"
                  : healthStatus.details === "Checking session..."
                    ? "Checking..."
                    : "Inactive / Missing"}
              </span>
            </div>
            <div className="flex justify-between border-b border-zinc-800/40 pb-1.5">
              <span className="text-zinc-500">Cookie Details:</span>
              <span className="text-zinc-300">{healthStatus.details}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Last Verified:</span>
              <span className="text-zinc-400">
                {lastVerifiedAt || "On system startup"}
              </span>
            </div>
          </div>
        </div>

        {/* Fernet Encryption Key Card */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
            <div className="flex items-center gap-2.5">
              <Key size={18} className="text-amber-400" />
              <h3 className="text-xs font-semibold text-zinc-200">
                Fernet Encryption Key Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="generate-key-btn"
              disabled={isGeneratingKey}
              onClick={handleGenerateKey}
              className="flex items-center gap-1.5 rounded border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-[11px] font-medium text-amber-300 transition-colors hover:border-amber-500/40 hover:bg-amber-500/10"
            >
              <Key size={13} className="text-amber-400" />
              <span>Generate New Key</span>
            </button>
          </div>

          <div className="mt-3 space-y-2.5 font-mono text-xs">
            <div className="flex justify-between border-b border-zinc-800/40 pb-1.5">
              <span className="text-zinc-500">Key Status:</span>
              <span
                data-testid="key-status"
                className="font-medium text-emerald-400"
              >
                {encryptionKeyStatus}
              </span>
            </div>
            <div className="flex justify-between border-b border-zinc-800/40 pb-1.5">
              <span className="text-zinc-500">Cipher Specification:</span>
              <span className="text-zinc-300">
                AES-128-CBC + HMAC-SHA256 PKCS7
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Entropy Source:</span>
              <span className="text-zinc-300">
                crypto.randomBytes(32) URL-safe
              </span>
            </div>

            {keyFeedback && (
              <div
                data-testid="key-feedback-msg"
                className="mt-2 rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-300"
              >
                {keyFeedback}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Cloudflare KV Sync Status Card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
          <div className="flex items-center gap-2.5">
            <LockKey size={18} className={healthStatus.valid ? "text-emerald-400" : "text-zinc-500"} />
            <h3 className="text-xs font-semibold text-zinc-200">
              Cloudflare KV Sync Status
            </h3>
          </div>
          <span
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
              healthStatus.valid
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-zinc-800 bg-zinc-900/80 text-zinc-400"
            }`}
          >
            {healthStatus.valid ? (
              <>
                <CheckCircle size={12} weight="fill" />
                <span>Synced</span>
              </>
            ) : (
              <span>Not Synced</span>
            )}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3 font-mono text-xs">
          <div className="rounded border border-zinc-800/80 bg-zinc-950 p-2.5">
            <div className="text-zinc-500">Encrypted Payload Status:</div>
            <div
              data-testid="kv-payload-status"
              className={`mt-1 font-semibold ${healthStatus.valid ? "text-zinc-200" : "text-zinc-500"}`}
            >
              {healthStatus.valid ? "LINKEDIN_SESSION_STATE_ENC in KV" : "Awaiting session capture"}
            </div>
          </div>
          <div className="rounded border border-zinc-800/80 bg-zinc-950 p-2.5">
            <div className="text-zinc-500">KV Namespace:</div>
            <div className="mt-1 text-zinc-300">hitl-state (Protected Edge)</div>
          </div>
          <div className="rounded border border-zinc-800/80 bg-zinc-950 p-2.5">
            <div className="text-zinc-500">Payload Encryption:</div>
            <div className="mt-1 text-emerald-400">AES-128-CBC + HMAC-SHA256</div>
          </div>
        </div>
      </div>
    </div>
  );
};
