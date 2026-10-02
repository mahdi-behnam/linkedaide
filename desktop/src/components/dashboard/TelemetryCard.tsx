import React from "react";

export interface TelemetryCardProps {
  title: string;
  value: string;
  subLeft: string;
  subRight: string;
  icon: React.ReactNode;
  iconBgClass?: string;
  iconColorClass?: string;
  subRightColorClass?: string;
}

export const TelemetryCard: React.FC<TelemetryCardProps> = ({
  title,
  value,
  subLeft,
  subRight,
  icon,
  iconBgClass = "bg-surface-container-low",
  iconColorClass = "text-primary",
  subRightColorClass = "text-tertiary",
}) => {
  return (
    <div className="p-3.5 rounded-lg bg-surface-container-lowest border border-outline shadow-2xs flex flex-col justify-between min-h-[110px] transition-colors hover:border-outline-variant">
      <div className="flex items-center justify-between text-on-surface-variant">
        <span className="text-[11px] font-medium text-on-surface-variant">
          {title}
        </span>
        <div
          className={`w-6 h-6 rounded-md ${iconBgClass} ${iconColorClass} flex items-center justify-center border border-outline/40`}
        >
          {icon}
        </div>
      </div>
      <div className="mt-2">
        <div className="text-[15px] text-on-surface font-semibold tracking-tight truncate">
          {value}
        </div>
        <div className="flex items-center justify-between mt-1 text-on-surface-variant text-[11px] font-sans">
          <span className="truncate">{subLeft}</span>
          <span className={`${subRightColorClass} font-medium shrink-0 ml-2`}>
            {subRight}
          </span>
        </div>
      </div>
    </div>
  );
};
