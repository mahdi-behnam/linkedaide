import React from "react";
import { Key, Copy, Check, LockKey, ShieldCheck } from "../../components/icons";

interface VaultEncryptionCardProps {
  encryptionKey: string;
  onKeyChange: (key: string) => void;
  onGenerateKey: () => void;
  onCopyKey: () => void;
  copiedKey: boolean;
}

export const VaultEncryptionCard: React.FC<VaultEncryptionCardProps> = ({
  encryptionKey,
  onKeyChange,
  onGenerateKey,
  onCopyKey,
  copiedKey,
}) => {
  const maskedDisplay = encryptionKey
    ? `k_v1:${encryptionKey.slice(0, 8)}...${encryptionKey.slice(-6)}`
    : "k_v1:•g7Q8...tY7aQ==";

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-secondary/10 flex items-center justify-center text-secondary shrink-0">
            <LockKey size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              Session Vault Encryption (Fernet AES-128-CBC)
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
              Fernet AES-128-CBC payload seal keyring
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            type="button"
            onClick={onGenerateKey}
            className="px-3 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 transition-colors font-medium text-[12px] flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer"
          >
            <Key size={13} />
            <span>Generate Key</span>
          </button>
          <button
            type="button"
            onClick={onCopyKey}
            disabled={!encryptionKey}
            className="px-3 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 transition-colors font-medium text-[12px] flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer disabled:opacity-40"
          >
            {copiedKey ? (
              <Check size={13} className="text-tertiary" />
            ) : (
              <Copy size={13} />
            )}
            <span>{copiedKey ? "Copied!" : "Copy Key"}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed text-[12px]">
          32-byte URL-safe base64 Fernet key used by the Python agent and browser runner to decrypt LinkedIn session credentials.
        </p>

        {/* Masked Display Strip */}
        <div className="flex items-center px-3 py-1.5 rounded-md bg-surface-container-low font-code-sm text-code-sm text-on-surface border border-outline-variant/20 select-all text-[11px]">
          <span className="text-on-surface-variant select-none mr-2 font-medium">FERNET_KEY=</span>
          <span className="tracking-wide font-mono text-[11px]">{maskedDisplay}</span>
        </div>

        {/* Key Input */}
        <div className="flex flex-col gap-1.5">
          <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
            32-Byte URL-Safe Base64 Fernet Key
          </label>
          <input
            type="text"
            value={encryptionKey}
            onChange={(e) => onKeyChange(e.target.value)}
            placeholder="Base64 URL-safe 32-byte key matching SESSION_ENCRYPTION_KEY"
            className="w-full px-3 py-1.5 rounded-md bg-surface-container-low focus:bg-surface-container-lowest border border-outline-variant/30 focus:border-secondary outline-none font-code-sm text-code-sm text-on-surface transition-all placeholder:text-on-surface-variant text-[12px]"
          />
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Must match the SESSION_ENCRYPTION_KEY repository secret used by Python agents to decrypt LinkedIn session state.
          </span>
        </div>

        {/* Zero-knowledge callout */}
        <div className="flex items-start gap-2.5 p-2.5 rounded-md bg-surface-container-low/60 text-on-surface-variant border border-outline-variant/20">
          <ShieldCheck size={16} className="text-primary shrink-0 mt-0.5" />
          <p className="font-label-sm text-[11px] leading-relaxed">
            <span className="font-semibold text-on-surface">Zero-knowledge architecture:</span> Keys are stored exclusively in macOS Keychain / local secure enclave and are never committed to version control or mirrored in edge worker databases.
          </p>
        </div>
      </div>
    </div>
  );
};
