import React, { useState } from "react";
import {
  PaperPlaneTilt,
  Eye,
  CheckCircle,
  WarningCircle,
  ArrowClockwise,
  ShieldCheck,
} from "../../components/icons";

interface TelegramApprovalCardProps {
  telegramBotToken: string;
  telegramAuthorizedChatId: string | number;
  onTokenChange: (token: string) => void;
  onChatIdChange: (chatId: string) => void;
}

export const TelegramApprovalCard: React.FC<TelegramApprovalCardProps> = ({
  telegramBotToken,
  telegramAuthorizedChatId,
  onTokenChange,
  onChatIdChange,
}) => {
  const [showToken, setShowToken] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyFeedback, setVerifyFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const handleVerify = async () => {
    setIsVerifying(true);
    setVerifyFeedback(null);
    try {
      if (!window.api.verifyTelegramBot) {
        throw new Error("Telegram verification API is unavailable.");
      }
      const res = await window.api.verifyTelegramBot(telegramBotToken);
      if (res.success && res.username) {
        setVerifyFeedback({
          type: "success",
          message: `Connected successfully to @${res.username}${
            res.firstName ? ` (${res.firstName})` : ""
          }`,
        });
      } else {
        setVerifyFeedback({
          type: "error",
          message: res.error || "Failed to verify Telegram Bot Token.",
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setVerifyFeedback({ type: "error", message: msg });
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-surface-container-high">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-sky-500/10 flex items-center justify-center text-sky-500 shrink-0">
            <PaperPlaneTilt size={16} weight="bold" />
          </div>
          <div>
            <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
              Telegram Approval Gateway
            </h2>
            <p className="font-label-sm text-[11px] text-on-surface-variant">
              Human-in-the-loop authorization channel for post review, approval, and live alerts
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleVerify}
          disabled={isVerifying || !telegramBotToken}
          className="px-3 py-1 rounded-md bg-surface-container hover:bg-surface-container-high text-on-surface border border-outline-variant/30 transition-colors font-medium text-[12px] flex items-center gap-1.5 shrink-0 whitespace-nowrap cursor-pointer disabled:opacity-40 self-end sm:self-auto"
        >
          <ArrowClockwise
            size={13}
            weight="bold"
            className={isVerifying ? "animate-spin text-sky-500" : "text-on-surface-variant"}
          />
          <span>{isVerifying ? "Verifying Bot..." : "Verify Bot"}</span>
        </button>
      </div>

      {verifyFeedback && (
        <div
          className={`flex items-center gap-2 rounded-md border p-2.5 text-xs font-mono ${
            verifyFeedback.type === "success"
              ? "border-tertiary/30 bg-tertiary-container/15 text-tertiary"
              : "border-error/30 bg-error-container/20 text-error"
          }`}
        >
          {verifyFeedback.type === "success" ? (
            <CheckCircle size={15} weight="fill" className="shrink-0" />
          ) : (
            <WarningCircle size={15} weight="fill" className="shrink-0" />
          )}
          <span>{verifyFeedback.message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-0.5">
        {/* Bot Token Input */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="telegram-bot-token-input"
              className="font-body-strong text-body-strong text-on-surface text-[12px]"
            >
              Telegram Bot Token
            </label>
            <button
              type="button"
              onClick={() => setShowToken((prev) => !prev)}
              aria-label="Toggle Telegram Bot Token visibility"
              className="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1 cursor-pointer"
            >
              <Eye size={13} />
              <span>{showToken ? "Hide" : "Show"}</span>
            </button>
          </div>

          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-sky-500 transition-all">
            <input
              id="telegram-bot-token-input"
              type={showToken ? "text" : "password"}
              value={telegramBotToken}
              onChange={(e) => onTokenChange(e.target.value)}
              placeholder="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            API token issued by @BotFather for sending draft proposals and receiving callback decisions.
          </span>
        </div>

        {/* Authorized Chat ID Input */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="telegram-chat-id-input"
            className="font-body-strong text-body-strong text-on-surface text-[12px]"
          >
            Authorized User / Chat ID
          </label>

          <div className="flex items-center justify-between px-3 py-1.5 rounded-md bg-surface-container-low focus-within:bg-surface-container-lowest border border-outline-variant/30 focus-within:border-sky-500 transition-all">
            <input
              id="telegram-chat-id-input"
              type="text"
              value={telegramAuthorizedChatId ? String(telegramAuthorizedChatId) : ""}
              onChange={(e) => onChatIdChange(e.target.value)}
              placeholder="e.g. 123456789"
              className="w-full bg-transparent border-0 outline-none font-code-sm text-code-sm text-on-surface p-0 focus:ring-0 placeholder:text-on-surface-variant text-[12px]"
            />
          </div>
          <span className="font-label-sm text-[11px] text-on-surface-variant">
            Numeric Telegram user or group ID authorized to review, approve, or reject queued actions.
          </span>
        </div>
      </div>

      {/* Safety Notice Callout */}
      <div className="flex items-start gap-2.5 p-2.5 rounded-md bg-surface-container-low/60 text-on-surface-variant border border-outline-variant/20">
        <ShieldCheck size={16} className="text-sky-500 shrink-0 mt-0.5" />
        <p className="font-label-sm text-[11px] leading-relaxed">
          <span className="font-semibold text-on-surface">Human Authorization Boundary:</span> Callbacks from any other chat or user are automatically discarded to prevent unauthorized execution.
        </p>
      </div>
    </div>
  );
};
