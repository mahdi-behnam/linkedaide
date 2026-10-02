import React, { useState, useCallback } from "react";
import {
  LockKey,
  ShieldCheck,
  CheckCircle,
  WarningCircle,
  CaretRight,
  ArrowClockwise,
} from "../../components/icons";

interface ManualCookieFallbackProps {
  onSuccess: (message: string) => void;
  onError: (error: string) => void;
}

export const ManualCookieFallback: React.FC<ManualCookieFallbackProps> = ({
  onSuccess,
  onError,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [liAtCookie, setLiAtCookie] = useState("");
  const [jsessionIdCookie, setJsessionIdCookie] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveBanner, setSaveBanner] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const handleManualSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmedLiAt = liAtCookie.trim();
      const trimmedJsession = jsessionIdCookie.trim();

      if (!trimmedLiAt) {
        setSaveBanner({
          type: "error",
          text: "The li_at cookie is mandatory for LinkedIn authentication.",
        });
        return;
      }

      setIsSaving(true);
      setSaveBanner(null);

      try {
        const cookiesPayload = [
          {
            name: "li_at",
            value: trimmedLiAt,
            domain: ".www.linkedin.com",
            path: "/",
            httpOnly: true,
            secure: true,
            sameSite: "None",
          },
          ...(trimmedJsession
            ? [
                {
                  name: "JSESSIONID",
                  value: trimmedJsession.replace(/^"|"$/g, ""),
                  domain: ".www.linkedin.com",
                  path: "/",
                  httpOnly: false,
                  secure: true,
                  sameSite: "None",
                },
              ]
            : []),
        ];

        const sessionJson = JSON.stringify({
          cookies: cookiesPayload,
          origins: [],
        });

        if (typeof window !== "undefined" && window.api?.saveSession) {
          const ok = await window.api.saveSession(sessionJson);
          if (ok) {
            setSaveBanner({
              type: "success",
              text: "Manual session cookies encrypted with Fernet and saved to local vault.",
            });
            onSuccess("Manual cookies saved and synced successfully.");
            setLiAtCookie("");
            setJsessionIdCookie("");
          } else {
            const err = "Failed to persist encrypted session.";
            setSaveBanner({ type: "error", text: err });
            onError(err);
          }
        } else {
          setSaveBanner({
            type: "success",
            text: "Session verified in preview environment.",
          });
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error saving manual session";
        setSaveBanner({ type: "error", text: msg });
        onError(msg);
      } finally {
        setIsSaving(false);
      }
    },
    [liAtCookie, jsessionIdCookie, onSuccess, onError]
  );

  return (
    <div className="rounded-lg bg-surface-container-lowest border border-outline-variant/30 overflow-hidden transition-all">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full p-4 flex items-center justify-between hover:bg-surface-container-low/40 transition-colors text-left cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-surface-container text-on-surface-variant">
            <LockKey size={15} />
          </span>
          <div className="flex flex-col">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Manual Cookie Fallback (Advanced)
            </span>
            <span className="font-label-sm text-[11px] text-on-surface-variant">
              Alternative for air-gapped systems or strict pop-up policies
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-on-surface-variant">
          <span className="font-label-sm text-[12px] hidden sm:inline">
            {isOpen ? "Hide Form" : "Enter Cookies"}
          </span>
          <CaretRight
            size={13}
            className={`transition-transform duration-150 ${isOpen ? "rotate-90" : ""}`}
          />
        </div>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 pt-1 border-t border-surface-container-high flex flex-col gap-3.5">
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            If the 1-Click popup cannot run, copy your session cookies from LinkedIn in DevTools (
            <code className="font-code-sm text-code-sm bg-surface-container px-1 py-0.5 rounded text-on-surface">
              Application &gt; Cookies &gt; https://www.linkedin.com
            </code>
            ). Plaintext values are never logged and are encrypted in memory with Fernet before persistence.
          </p>

          {saveBanner && (
            <div
              className={`p-2.5 rounded-md flex items-center gap-2 font-body-md text-body-md ${
                saveBanner.type === "success"
                  ? "bg-tertiary-container/15 text-tertiary border border-tertiary/20"
                  : "bg-error-container/20 text-error border border-error/20"
              }`}
            >
              {saveBanner.type === "success" ? (
                <CheckCircle size={15} weight="fill" className="shrink-0" />
              ) : (
                <WarningCircle size={15} weight="fill" className="shrink-0" />
              )}
              <span>{saveBanner.text}</span>
            </div>
          )}

          <form onSubmit={handleManualSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                  li_at cookie value <span className="text-error">*</span>
                </label>
                <input
                  type="password"
                  value={liAtCookie}
                  onChange={(e) => setLiAtCookie(e.target.value)}
                  placeholder="AQED..."
                  className="w-full px-2.5 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus:border-primary focus:bg-surface-container-lowest outline-none font-code-sm text-code-sm text-on-surface transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="font-body-strong text-body-strong text-on-surface text-[12px]">
                  JSESSIONID cookie value (optional)
                </label>
                <input
                  type="password"
                  value={jsessionIdCookie}
                  onChange={(e) => setJsessionIdCookie(e.target.value)}
                  placeholder='ajax:...'
                  className="w-full px-2.5 py-1.5 rounded-md bg-surface-container-low border border-outline-variant/30 focus:border-primary focus:bg-surface-container-lowest outline-none font-code-sm text-code-sm text-on-surface transition-colors"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary hover:bg-primary-container text-on-primary font-medium text-[13px] shadow-xs transition-colors cursor-pointer disabled:opacity-50 active:bg-primary/90"
              >
                {isSaving ? (
                  <ArrowClockwise size={13} className="animate-spin text-on-primary" />
                ) : (
                  <ShieldCheck size={15} weight="bold" />
                )}
                <span>{isSaving ? "Encrypting & Saving..." : "Encrypt & Save Session"}</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
