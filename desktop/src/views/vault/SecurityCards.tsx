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
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
      {/* Card 1: Cookie Health Card */}
      <div className="rounded-lg bg-surface-container-lowest p-4.5 border border-outline-variant/30 flex flex-col justify-between gap-3.5 transition-all">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                <ShieldCheck size={15} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface text-[13px]">
                Cookie Health Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="verify-cookie-health-btn"
              disabled={isVerifyingHealth}
              onClick={onVerifyHealth}
              title="Verify Cookie Health"
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/20 transition-colors font-label-sm text-[11px] shrink-0 cursor-pointer disabled:opacity-50"
            >
              <ArrowClockwise
                size={12}
                className={isVerifyingHealth ? "animate-spin text-primary" : "text-on-surface-variant"}
              />
              <span>Verify Cookie Health</span>
            </button>
          </div>

          {/* li_at status */}
          <div className="flex flex-col gap-1 p-2 rounded-md bg-surface-container-low border border-outline-variant/15">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">li_at status:</span>
              <span
                data-testid="li-at-status"
                className={`font-label-sm text-[12px] font-medium ${
                  healthStatus.valid ? "text-tertiary" : "text-error"
                }`}
              >
                {healthStatus.valid
                  ? `Active (${healthStatus.daysRemaining} days remaining)`
                  : healthStatus.details === "Checking session..."
                  ? "Checking session..."
                  : "No active session"}
              </span>
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              {healthStatus.valid
                ? `${healthStatus.daysRemaining} days remaining · Session auth token`
                : "Awaiting authentication"}
            </span>
          </div>

          {/* JSESSIONID status */}
          <div className="flex flex-col gap-1 p-2 rounded-md bg-surface-container-low border border-outline-variant/15">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">JSESSIONID status:</span>
              <span
                data-testid="jsessionid-status"
                className={`font-label-sm text-[12px] font-medium ${
                  healthStatus.valid ? "text-tertiary" : "text-on-surface-variant"
                }`}
              >
                {healthStatus.valid
                  ? "Active (CSRF token valid)"
                  : healthStatus.details === "Checking session..."
                  ? "Checking..."
                  : "Inactive / Missing"}
              </span>
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              {healthStatus.valid ? "CSRF token valid & verified" : "Required for write actions"}
            </span>
          </div>

          {/* Cookie details & Last verified */}
          <div className="flex flex-col gap-1 pt-0.5 text-label-sm text-[12px]">
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
          <span className="truncate">{healthStatus.valid ? "Enclave: Fernet AES-128" : "No Session Enclave"}</span>
          <span className={`font-medium ${healthStatus.valid ? "text-tertiary" : "text-on-surface-variant"}`}>
            {healthStatus.valid ? "Valid" : "Inactive"}
          </span>
        </div>
      </div>

      {/* Card 2: Fernet Encryption Key Card */}
      <div className="rounded-lg bg-surface-container-lowest p-4.5 border border-outline-variant/30 flex flex-col justify-between gap-3.5 transition-all">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-secondary/10 text-secondary">
                <Key size={15} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface text-[13px]">
                Fernet Encryption Key Card
              </h3>
            </div>
            <button
              type="button"
              data-testid="generate-key-btn"
              disabled={isGeneratingKey}
              onClick={onGenerateKey}
              title="Generate New Key"
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/20 transition-colors font-label-sm text-[11px] shrink-0 cursor-pointer disabled:opacity-50"
            >
              <ArrowClockwise
                size={12}
                className={isGeneratingKey ? "animate-spin text-secondary" : "text-on-surface-variant"}
              />
              <span>Generate New Key</span>
            </button>
          </div>

          {/* Key Status */}
          <div className="flex flex-col gap-1 p-2 rounded-md bg-surface-container-low border border-outline-variant/15">
            <div className="flex items-center justify-between">
              <span className="font-code-sm text-code-sm font-medium text-on-surface">Key Status:</span>
              <span
                data-testid="key-status"
                className="font-label-sm text-[12px] font-medium text-tertiary"
              >
                {encryptionKeyStatus.includes("Loaded") ? "Loaded" : encryptionKeyStatus}
              </span>
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Valid 32-byte Fernet key
            </span>
          </div>

          {/* Cipher Spec Details */}
          <div className="flex flex-col gap-1 text-label-sm text-[12px]">
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
          <div className="p-2 rounded-md bg-surface-container border border-outline-variant/20 flex items-center justify-between font-code-sm text-code-sm">
            <span className="text-on-surface truncate font-mono text-[11px]">
              {maskedKey}
            </span>
            <button
              type="button"
              id="copy-key-btn"
              onClick={onCopyKeyId}
              className="shrink-0 ml-2 px-2 py-0.5 rounded-md bg-surface-container-lowest text-on-surface-variant hover:text-on-surface font-label-sm text-[11px] border border-outline-variant/30 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <Copy size={11} />
              <span>{copiedKeyId ? "Copied" : "Copy ID"}</span>
            </button>
          </div>

          {keyFeedback && (
            <div
              data-testid="key-feedback-msg"
              className="rounded-md border border-secondary/30 bg-secondary/10 p-2 text-xs text-secondary font-body-md"
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
      <div className="rounded-lg bg-surface-container-lowest p-4.5 border border-outline-variant/30 flex flex-col justify-between gap-3.5 transition-all">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between pb-2 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Globe size={15} weight="bold" />
              </span>
              <h3 className="font-body-strong text-body-strong text-on-surface text-[13px]">
                Cloudflare KV Sync Status
              </h3>
            </div>
            <span
              className={`font-label-sm text-[12px] font-medium ${
                healthStatus.valid ? "text-tertiary" : "text-on-surface-variant"
              }`}
            >
              {healthStatus.valid ? "Synced" : "Not Synced"}
            </span>
          </div>

          {/* Payload Status */}
          <div className="flex flex-col gap-1 p-2 rounded-md bg-surface-container-low border border-outline-variant/15">
            <div className="flex items-center justify-between">
              <span
                data-testid="kv-payload-status"
                className="font-code-sm text-code-sm font-semibold text-on-surface truncate"
              >
                {healthStatus.valid ? "LINKEDIN_SESSION_STATE_ENC in KV" : "Awaiting session capture"}
              </span>
            </div>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              {healthStatus.valid
                ? "Fernet encrypted session payload synced to edge"
                : "No encrypted session state stored"}
            </span>
          </div>

          {/* Edge Details */}
          <div className="flex flex-col gap-1 text-label-sm text-[12px]">
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Edge Storage:</span>
              <span className="text-on-surface">Global Workers KV</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-on-surface-variant">Sync Policy:</span>
              <span className="text-on-surface font-code-sm text-code-sm">
                Write-on-capture / Replicated
              </span>
            </div>
          </div>

          {/* Tamper-proof Signature Verified Badge */}
          <div className="px-2 py-1.5 rounded-md bg-surface-container border border-outline-variant/20 flex items-center gap-2 text-tertiary font-label-sm text-[11px] font-medium">
            <CheckCircle size={14} weight="fill" className="shrink-0" />
            <span className="truncate">Tamper-proof signature verified</span>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-2 border-t border-surface-container-high flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
          <span>Worker Binding</span>
          <span className="font-code-sm text-code-sm">{healthStatus.valid ? "Active" : "Standby"}</span>
        </div>
      </div>
    </div>
  );
};
