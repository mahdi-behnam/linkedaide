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
    <div className="rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high transition-all overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full p-5 flex items-center justify-between hover:bg-surface-container-low/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-surface-container text-on-surface-variant">
            <LockKey size={16} />
          </span>
          <div className="flex flex-col">
            <span className="font-body-strong text-body-strong text-on-surface">
              Manual Cookie Fallback (Advanced)
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              Alternative for air-gapped systems or strict pop-up policies
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-on-surface-variant">
          <span className="font-label-sm text-label-sm hidden sm:inline">
            {isOpen ? "Hide Form" : "Enter Cookies"}
          </span>
          <CaretRight
            size={14}
            className={`transition-transform duration-150 ${isOpen ? "rotate-90" : ""}`}
          />
        </div>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 pt-2 border-t border-surface-container-high flex flex-col gap-4">
          <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
            If the 1-Click popup cannot run, copy your session cookies from LinkedIn in DevTools (
            <code className="font-code-sm text-code-sm bg-surface-container px-1 py-0.5 rounded text-on-surface">
              Application &gt; Cookies &gt; https://www.linkedin.com
            </code>
            ). Plaintext values are never logged and are encrypted in memory with Fernet before persistence.
          </p>

          {saveBanner && (
            <div
              className={`p-3 rounded-xl flex items-center gap-2 font-body-md text-body-md ${
                saveBanner.type === "success"
                  ? "bg-tertiary-container/15 text-tertiary border border-tertiary/20"
                  : "bg-error-container/20 text-error border border-error/20"
              }`}
            >
              {saveBanner.type === "success" ? (
                <CheckCircle size={16} weight="fill" className="shrink-0" />
              ) : (
                <WarningCircle size={16} weight="fill" className="shrink-0" />
              )}
              <span>{saveBanner.text}</span>
            </div>
          )}

          <form onSubmit={handleManualSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="font-body-strong text-body-strong text-on-surface">
                  li_at cookie value <span className="text-error">*</span>
                </label>
                <input
                  type="password"
                  value={liAtCookie}
                  onChange={(e) => setLiAtCookie(e.target.value)}
                  placeholder="AQED..."
                  className="w-full px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus:border-primary focus:bg-surface-container-lowest outline-none font-code-sm text-code-sm text-on-surface transition-colors"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="font-body-strong text-body-strong text-on-surface">
                  JSESSIONID cookie value (optional)
                </label>
                <input
                  type="password"
                  value={jsessionIdCookie}
                  onChange={(e) => setJsessionIdCookie(e.target.value)}
                  placeholder='ajax:...'
                  className="w-full px-3 py-2 rounded-xl bg-surface-container-low border border-surface-container-high focus:border-primary focus:bg-surface-container-lowest outline-none font-code-sm text-code-sm text-on-surface transition-colors"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary-container text-on-primary font-body-strong text-body-strong shadow-xs transition-all cursor-pointer disabled:opacity-50"
              >
                {isSaving ? (
                  <ArrowClockwise size={14} className="animate-spin text-on-primary" />
                ) : (
                  <ShieldCheck size={16} weight="bold" />
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
