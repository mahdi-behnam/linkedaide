import React from "react";
import { CheckCircle, WarningCircle, ShieldCheck } from "../../components/icons";

export interface EnvVarItem {
  key: string;
  loaded: boolean;
  valueDisplay?: string;
  statusTag?: string;
}

interface EnvSecretsAuditProps {
  envAuditList: EnvVarItem[];
  loadedVarsCount: number;
}

export const EnvSecretsAudit: React.FC<EnvSecretsAuditProps> = ({
  envAuditList,
  loadedVarsCount,
}) => {
  const getVarDetails = (item: EnvVarItem) => {
    if (item.valueDisplay) {
      return {
        masked: item.valueDisplay,
        tag: item.statusTag || (item.loaded ? "Configured" : "Missing"),
      };
    }
    return {
      masked: item.loaded ? "Configured" : "Missing",
      tag: item.loaded ? "Configured" : "Missing",
    };
  };

  return (
    <div className="p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30 flex flex-col gap-3.5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-surface-container-high">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-tertiary/10 text-tertiary">
            <ShieldCheck size={16} weight="bold" />
          </span>
          <h3 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Environment Secrets Audit
          </h3>
        </div>
        <span className="font-label-sm text-[11px] text-on-surface-variant font-medium">
          {loadedVarsCount} / {envAuditList.length} Variables Configured &amp; Cryptographically Verified
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {envAuditList.map((item) => {
          const detail = getVarDetails(item);
          return (
            <div
              key={item.key}
              className="p-2.5 rounded-md bg-surface-container-low/70 border border-outline-variant/20 flex items-center justify-between gap-2.5"
            >
              <div className="flex flex-col min-w-0">
                <span className="font-code-sm text-code-sm text-on-surface font-medium truncate text-[12px]">
                  {item.key}
                </span>
                <span className="font-code-sm text-code-sm text-on-surface-variant truncate text-[11px]">
                  {detail.masked}
                </span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span
                  className={`font-label-sm text-[11px] font-medium ${
                    item.loaded ? "text-tertiary" : "text-error"
                  }`}
                >
                  {detail.tag}
                </span>
                {item.loaded ? (
                  <CheckCircle size={13} weight="fill" className="text-tertiary shrink-0" />
                ) : (
                  <WarningCircle size={13} weight="fill" className="text-amber-500 shrink-0" />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
