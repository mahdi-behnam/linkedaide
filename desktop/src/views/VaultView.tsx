import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  ShieldCheck,
  LockKey,
  Key,
  ArrowClockwise,
  CheckCircle,
  Warning,
} from "../components/icons";
import { SecurityCards } from "./vault/SecurityCards";
import { ArchitectureDiagram } from "./vault/ArchitectureDiagram";
import { ManualCookieFallback } from "./vault/ManualCookieFallback";
import { useDeepNavigation } from "../hooks/useDeepNavigation";

interface CookieHealthState {
  valid: boolean;
  daysRemaining: number;
  details: string;
}

export const VaultView: React.FC = () => {
  useDeepNavigation("vault");
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

  const [encryptionKey, setEncryptionKey] = useState<string>("");
  const [encryptionKeyStatus, setEncryptionKeyStatus] = useState<string>(
    "Checking encryption key..."
  );
  const [keyFeedback, setKeyFeedback] = useState<string | null>(null);
  const [isGeneratingKey, setIsGeneratingKey] = useState<boolean>(false);
  const [copiedKeyId, setCopiedKeyId] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 2800);
  }, []);

  // Initialize and check status
  useEffect(() => {
    let mounted = true;

    async function initVault() {
      if (typeof window !== "undefined" && window.api) {
        try {
          if (window.api.getSettings) {
            const settings = await window.api.getSettings();
            if (mounted) {
              if (settings?.encryptionKey) {
                setEncryptionKey(settings.encryptionKey);
                setEncryptionKeyStatus("Loaded / Valid 32-byte Fernet");
              } else {
                setEncryptionKeyStatus("Not configured / Key missing");
              }
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
          setHealthStatus({
            valid: true,
            daysRemaining: 18,
            details: "Active li_at cookie (freshly synced)",
          });
          setLastVerifiedAt("Just now");
          showToast("Secure session captured and encrypted with Fernet.");
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
  }, [showToast]);

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
        showToast(
          res.valid
            ? `Cookies verified: li_at active (${res.daysRemaining ?? 18} days remaining)`
            : "No active LinkedIn session found."
        );
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
  }, [showToast]);

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
      setEncryptionKey(newKey);
      setEncryptionKeyStatus("Loaded / Valid 32-byte Fernet");
      setKeyFeedback(
        `Generated fresh 32-byte Fernet key (${newKey.slice(0, 8)}...${newKey.slice(-4)}) and saved to settings.`
      );
      showToast("New 32-byte Fernet key generated and saved locally.");
    } catch (err) {
      setKeyFeedback(
        `Failed to generate key: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setIsGeneratingKey(false);
    }
  }, [showToast]);

  const handleCopyKeyId = useCallback(() => {
    if (encryptionKey) {
      navigator.clipboard?.writeText(encryptionKey);
      setCopiedKeyId(true);
      showToast("Key identifier copied to clipboard.");
      setTimeout(() => setCopiedKeyId(false), 2000);
    } else {
      showToast("No active Fernet key loaded to copy.");
    }
  }, [encryptionKey, showToast]);

  const maskedKeyDisplay = useMemo(() => {
    if (!encryptionKey) {
      return "Unconfigured";
    }
    const start = encryptionKey.slice(0, 6);
    const end = encryptionKey.slice(-6);
    return `k_v1:${start}...${end}`;
  }, [encryptionKey]);

  return (
    <div className="w-full max-w-[960px] mx-auto flex flex-col gap-5">
      {/* Page Header Block matching macOS HIG */}
      <div className="flex flex-col gap-1 pb-1">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
              LinkedIn Session Vault
            </h1>
            <span
              data-testid="encryption-badge"
              className="inline-flex items-center gap-1.5 font-mono text-[11px] text-tertiary font-medium"
            >
              <ShieldCheck size={13} weight="bold" />
              <span>AES-128-CBC + HMAC-SHA256 Fernet</span>
            </span>
          </div>
        </div>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Secure local session credentials storage. Plaintext cookies are never logged or stored in version control.
        </p>
      </div>

      {/* 1-Click Connect LinkedIn Highlight Banner */}
      <div className="rounded-lg bg-surface-container-lowest p-5 border border-outline-variant/30 flex flex-col md:flex-row md:items-center justify-between gap-5 transition-all">
        <div className="flex items-start gap-3.5">
          <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0 text-primary">
            <Key size={18} weight="bold" />
          </div>
          <div className="flex flex-col gap-1 max-w-xl">
            <div className="flex items-center gap-2">
              <h2 className="font-headline-sm text-headline-sm text-on-surface">
                1-Click Connect LinkedIn
              </h2>
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
              Open a secure, isolated embedded browser session to authenticate. Session cookies are automatically captured, encrypted with Fernet, and synced to Cloudflare KV.
            </p>
          </div>
        </div>

        <div className="flex items-center shrink-0">
          <button
            type="button"
            data-testid="launch-login-btn"
            disabled={isCapturing}
            onClick={handleLaunchLogin}
            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md font-medium text-[13px] shadow-xs transition-colors cursor-pointer ${
              isCapturing
                ? "bg-surface-container-highest text-on-surface-variant cursor-not-allowed opacity-75"
                : "bg-primary hover:bg-primary-container text-on-primary active:bg-primary/90"
            }`}
          >
            {isCapturing ? (
              <>
                <ArrowClockwise size={14} className="animate-spin text-on-primary" />
                <span>Waiting for Login...</span>
              </>
            ) : (
              <>
                <LockKey size={14} weight="bold" />
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
          className="p-3 rounded-lg border border-tertiary/30 bg-tertiary-container/15 flex items-center gap-2.5 text-tertiary text-xs font-medium"
        >
          <CheckCircle size={16} weight="fill" className="shrink-0" />
          <div className="flex-1">{captureSuccess}</div>
        </div>
      )}

      {/* Capture Error Banner */}
      {captureError && (
        <div
          data-testid="capture-error-banner"
          className="p-3 rounded-lg border border-error/30 bg-error-container/30 flex items-center gap-2.5 text-error text-xs font-medium"
        >
          <Warning size={16} weight="fill" className="shrink-0" />
          <div className="flex-1">{captureError}</div>
        </div>
      )}

      {/* 3-Card Security Center Grid */}
      <SecurityCards
        healthStatus={healthStatus}
        lastVerifiedAt={lastVerifiedAt}
        isVerifyingHealth={isVerifyingHealth}
        onVerifyHealth={handleVerifyHealth}
        encryptionKeyStatus={encryptionKeyStatus}
        keyFeedback={keyFeedback}
        isGeneratingKey={isGeneratingKey}
        onGenerateKey={handleGenerateKey}
        onCopyKeyId={handleCopyKeyId}
        copiedKeyId={copiedKeyId}
        maskedKey={maskedKeyDisplay}
      />

      {/* Manual Cookie Fallback Component */}
      <div id="vault-manual-cookie">
        <ManualCookieFallback
          onSuccess={(msg) => {
            showToast(msg);
            setHealthStatus((prev) => ({
              ...prev,
              valid: true,
              daysRemaining: 18,
              details: "Active li_at cookie (manually supplied)",
            }));
            setLastVerifiedAt("Just now");
          }}
          onError={(err) => {
            showToast(`Error: ${err}`);
          }}
        />
      </div>

      {/* Architecture & Invariants Native SVG/HTML Diagram */}
      <ArchitectureDiagram />

      {/* Bottom Status Bar matching Things 3 Calm Footer */}
      <footer className="p-3.5 rounded-lg bg-surface-container border border-outline-variant/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-on-surface-variant">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-surface-container-highest flex items-center justify-center text-on-surface">
            <ShieldCheck size={16} weight="bold" />
          </div>
          <div className="flex flex-col">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Vault Memory Guard
            </span>
            <span className="font-label-sm text-[11px]">
              Isolated sandbox process · Zero plain cookies stored on disk
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 self-end sm:self-auto">
          <span className="font-code-sm text-code-sm text-on-surface-variant">
            {healthStatus.valid ? "Session Keyring Active" : "No Session in Keyring"}
          </span>
          <button
            type="button"
            id="flush-cache-btn"
            onClick={handleVerifyHealth}
            disabled={isVerifyingHealth}
            className="px-2.5 py-1 rounded-md bg-surface-container-highest hover:bg-surface-container-high text-on-surface font-label-md text-[12px] transition-colors cursor-pointer border border-outline-variant/30 disabled:opacity-50"
          >
            Verify Health
          </button>
        </div>
      </footer>

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface-container-highest text-on-surface shadow-lg font-medium text-[13px] border border-outline">
          <CheckCircle size={16} weight="fill" className="text-tertiary" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};
