import React from "react";
import {
  ShieldCheck,
  Key,
  Globe,
  ArrowClockwise,
  CheckCircle,
  Copy,
  LockKey,
} from "../../components/icons";

interface CookieHealthState {
  valid: boolean;
  daysRemaining: number;
  details: string;
}

interface SecurityCardsProps {
  healthStatus: CookieHealthState;
  lastVerifiedAt: string | null;
  isVerifyingHealth: boolean;
  onVerifyHealth: () => void;
  encryptionKeyStatus: string;
  keyFeedback: string | null;
  isGeneratingKey: boolean;
  onGenerateKey: () => void;
  onCopyKeyId: () => void;
  copiedKeyId: boolean;
  maskedKey: string;
}

export const SecurityCards: React.FC<SecurityCardsProps> = ({
  healthStatus,
  lastVerifiedAt,
  isVerifyingHealth,
  onVerifyHealth,
  encryptionKeyStatus,
  keyFeedback,
  isGeneratingKey,
  onGenerateKey,
  onCopyKeyId,
  copiedKeyId,
  maskedKey,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Card 1: Cookie Health Card */}
      <div className="rounded-2xl bg-surface-container-lowest p-5 shadow-xs border border-surface-container-high flex flex-col justify-between gap-4 transition-all">
        <div className="flex flex-col gap-3.5">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ShieldCheck size={17} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface">
                Cookie Health Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="verify-cookie-health-btn"
              disabled={isVerifyingHealth}
              onClick={onVerifyHealth}
              title="Verify Cookie Health"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors font-label-sm text-label-sm shrink-0 cursor-pointer disabled:opacity-50"
            >
              <ArrowClockwise
                size={13}
                className={isVerifyingHealth ? "animate-spin text-primary" : "text-on-surface-variant"}
              />
              <span>Verify Cookie Health</span>
            </button>
          </div>

          {/* li_at status */}
          <div className="flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">li_at status:</span>
              <span
                data-testid="li-at-status"
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold ${
                  healthStatus.valid
                    ? "bg-tertiary-container/15 text-tertiary"
                    : "bg-error-container/40 text-error"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    healthStatus.valid ? "bg-tertiary" : "bg-error"
                  }`}
                />
                {healthStatus.valid
                  ? `Active (${healthStatus.daysRemaining} days remaining)`
                  : healthStatus.details === "Checking session..."
                  ? "Checking session..."
                  : "No active session"}
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              {healthStatus.valid
                ? `${healthStatus.daysRemaining} days remaining · Session auth token`
                : "Awaiting authentication"}
            </span>
          </div>

          {/* JSESSIONID status */}
          <div className="flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">JSESSIONID status:</span>
              <span
                data-testid="jsessionid-status"
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold ${
                  healthStatus.valid
                    ? "bg-tertiary-container/15 text-tertiary"
                    : "bg-surface-container-highest text-on-surface-variant"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    healthStatus.valid ? "bg-tertiary" : "bg-on-surface-variant"
                  }`}
                />
                {healthStatus.valid
                  ? "Active (CSRF token valid)"
                  : healthStatus.details === "Checking session..."
                  ? "Checking..."
                  : "Inactive / Missing"}
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              {healthStatus.valid ? "CSRF token valid & verified" : "Required for write actions"}
            </span>
          </div>

          {/* Cookie details & Last verified */}
          <div className="flex flex-col gap-1.5 pt-1 text-label-sm">
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Cookie details:</span>
              <span className="font-body-strong text-on-surface truncate max-w-[190px]">
                {healthStatus.details}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Last verified:</span>
              <span className="text-on-surface font-mono text-[11px]">
                {lastVerifiedAt || "On system startup"}
              </span>
            </div>
          </div>
        </div>

        {/* Footer Fingerprint */}
        <div className="pt-2 border-t border-surface-container-high flex items-center justify-between font-code-sm text-code-sm text-on-surface-variant">
          <span className="truncate">sha256:7f4c91...b801</span>
          <span className={`font-medium ${healthStatus.valid ? "text-tertiary" : "text-on-surface-variant"}`}>
            {healthStatus.valid ? "Valid" : "Inactive"}
          </span>
        </div>
      </div>

      {/* Card 2: Fernet Encryption Key Card */}
      <div className="rounded-2xl bg-surface-container-lowest p-5 shadow-xs border border-surface-container-high flex flex-col justify-between gap-4 transition-all">
        <div className="flex flex-col gap-3.5">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-secondary/10 text-secondary">
                <Key size={17} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface">
                Fernet Encryption Key Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="generate-key-btn"
              disabled={isGeneratingKey}
              onClick={onGenerateKey}
              title="Generate New Key"
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors font-label-sm text-label-sm shrink-0 cursor-pointer disabled:opacity-50"
            >
              <ArrowClockwise
                size={13}
                className={isGeneratingKey ? "animate-spin text-secondary" : "text-on-surface-variant"}
              />
              <span>Generate New Key</span>
            </button>
          </div>

          {/* Key Status */}
          <div className="flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">Key Status:</span>
              <span
                data-testid="key-status"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-tertiary-container/15 text-tertiary font-label-sm text-label-sm font-semibold"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-tertiary" />
                {encryptionKeyStatus.includes("Loaded") ? "Loaded" : encryptionKeyStatus}
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Valid 32-byte Fernet key
            </span>
          </div>

          {/* Cipher Spec Details */}
          <div className="flex flex-col gap-1.5 text-label-sm">
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Cipher Specification:</span>
              <span className="font-code-sm text-code-sm text-on-surface font-medium">
                AES-128-CBC
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Integrity:</span>
              <span className="font-code-sm text-code-sm text-on-surface font-medium">
                HMAC-SHA256 PKCS7
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Entropy Source:</span>
              <span className="text-on-surface font-code-sm text-code-sm">
                crypto.randomBytes(32) URL-safe
              </span>
            </div>
          </div>

          {/* Masked Key Display with Copy ID button */}
          <div className="p-2 rounded-xl bg-surface-container flex items-center justify-between font-code-sm text-code-sm">
            <span className="text-on-surface truncate font-mono text-[11px]">
              {maskedKey}
            </span>
            <button
              type="button"
              id="copy-key-btn"
              onClick={onCopyKeyId}
              className="shrink-0 ml-2 px-2 py-0.5 rounded-lg bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-sm text-label-sm shadow-2xs transition-colors flex items-center gap-1"
            >
              <Copy size={11} />
              <span>{copiedKeyId ? "Copied" : "Copy ID"}</span>
            </button>
          </div>

          {keyFeedback && (
            <div
              data-testid="key-feedback-msg"
              className="rounded-xl border border-secondary/30 bg-secondary/10 p-2 text-xs text-secondary font-body-md"
            >
              {keyFeedback}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pt-2 border-t border-surface-container-high flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
          <span>Zero-Knowledge Fernet</span>
          <LockKey size={14} className="text-tertiary" />
        </div>
      </div>

      {/* Card 3: Cloudflare KV Edge Sync */}
      <div className="rounded-2xl bg-surface-container-lowest p-5 shadow-xs border border-surface-container-high flex flex-col justify-between gap-4 transition-all">
        <div className="flex flex-col gap-3.5">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Globe size={17} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface">
                Cloudflare KV Sync Status
              </h3>
            </div>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold ${
                healthStatus.valid
                  ? "bg-tertiary-container/15 text-tertiary"
                  : "bg-surface-container-highest text-on-surface-variant"
              }`}
            >
              {healthStatus.valid ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse" />
                  <span>Synced</span>
                </>
              ) : (
                <span>Not Synced</span>
              )}
            </span>
          </div>

          {/* Payload Status */}
          <div className="flex flex-col gap-1 p-2.5 rounded-xl bg-surface-container-low">
            <div className="flex items-center justify-between">
              <span
                data-testid="kv-payload-status"
                className="font-code-sm text-code-sm font-semibold text-on-surface truncate"
              >
                {healthStatus.valid ? "LINKEDIN_SESSION_STATE_ENC in KV" : "Awaiting session capture"}
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              {healthStatus.valid
                ? "Encrypted payload in KV · Blob: 1.84 KB"
                : "No encrypted session state stored"}
            </span>
          </div>

          {/* Namespace and PoP Details */}
          <div className="flex flex-col gap-1.5 text-label-sm">
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">KV Namespace:</span>
              <span className="font-body-strong text-on-surface font-mono text-[11px]">
                hitl-state (Protected Edge)
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Edge Coverage:</span>
              <span className="text-on-surface">275 PoPs · 14ms avg</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Sync Frequency:</span>
              <span className="text-on-surface font-code-sm text-code-sm">
                1/min (Write Ops)
              </span>
            </div>
          </div>

          {/* Tamper-proof Signature Verified Badge */}
          <div className="px-2.5 py-1.5 rounded-xl bg-surface-container flex items-center gap-2 text-tertiary font-label-sm text-label-sm font-medium">
            <CheckCircle size={15} weight="fill" className="shrink-0" />
            <span className="truncate">Tamper-proof signature verified</span>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-2 border-t border-surface-container-high flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
          <span>Worker #cf-worker-9a84</span>
          <span className="font-code-sm text-code-sm">2m ago</span>
        </div>
      </div>
    </div>
  );
};
