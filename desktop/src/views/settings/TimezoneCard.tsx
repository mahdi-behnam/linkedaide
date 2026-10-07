import React, { useMemo, useState, useEffect } from "react";
import { Clock, Check } from "../../components/icons";
import {
  getTimezoneOptions,
  getTimezoneOffsetString,
  getDefaultTimezone,
  formatDateTime,
} from "../../utils/datetime";

interface TimezoneCardProps {
  timezone: string;
  onChange: (tz: string) => void;
}

export const TimezoneCard: React.FC<TimezoneCardProps> = ({ timezone, onChange }) => {
  const systemTimezone = useMemo(() => getDefaultTimezone(), []);
  const options = useMemo(() => getTimezoneOptions(), []);
  const [searchFilter, setSearchFilter] = useState("");
  const [now, setNow] = useState<Date>(() => new Date());

  // Update live preview clock every 5 seconds
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 5000);
    return () => clearInterval(timer);
  }, []);

  const activeTz = timezone || systemTimezone;
  const activeOffset = useMemo(
    () => getTimezoneOffsetString(activeTz, now),
    [activeTz, now]
  );
  const livePreviewStr = useMemo(
    () => formatDateTime(now, activeTz),
    [now, activeTz]
  );

  const filteredOptions = useMemo(() => {
    if (!searchFilter.trim()) return options;
    const q = searchFilter.toLowerCase();
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(q) ||
        opt.value.toLowerCase().includes(q) ||
        opt.region.toLowerCase().includes(q) ||
        opt.offset.toLowerCase().includes(q)
    );
  }, [options, searchFilter]);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Regional & Timezone Settings
          </h2>
          <span className="font-label-sm text-[11px] text-on-surface-variant font-normal">
            Application-wide time display & scheduling
          </span>
        </div>
      </div>

      <div className="p-4 rounded-lg border border-outline/40 bg-surface-container-low flex flex-col gap-3.5 shadow-2xs">
        {/* Live Preview Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 p-3 rounded-md bg-surface-container-lowest border border-outline/50 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <Clock size={16} weight="bold" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-on-surface flex items-center gap-1.5">
                <span>{activeTz}</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface-container text-on-surface-variant">
                  {activeOffset}
                </span>
                {activeTz === systemTimezone && (
                  <span className="text-[10px] text-tertiary font-medium">
                    (System Match)
                  </span>
                )}
              </span>
              <span className="text-[11px] text-on-surface-variant font-mono">
                Current Time: {livePreviewStr}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            {activeTz !== systemTimezone && (
              <button
                type="button"
                data-testid="reset-timezone-system-btn"
                onClick={() => onChange(systemTimezone)}
                className="text-xs px-2.5 py-1 rounded border border-outline bg-surface-container hover:bg-surface-container-high text-on-surface transition-colors cursor-pointer"
              >
                Use System ({systemTimezone})
              </button>
            )}
          </div>
        </div>

        {/* Timezone Selector Input */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="timezone-select"
              className="text-xs font-medium text-on-surface"
            >
              Select Active Timezone
            </label>
            <span className="text-[11px] text-on-surface-variant">
              {filteredOptions.length} timezones available
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <select
              id="timezone-select"
              data-testid="timezone-select"
              value={activeTz}
              onChange={(e) => onChange(e.target.value)}
              aria-label="Select Active Timezone"
              className="w-full px-3 py-1.5 text-xs rounded-md bg-surface-container-lowest border border-outline text-on-surface focus:outline-none focus:border-primary shadow-2xs cursor-pointer font-sans"
            >
              <optgroup label="System Default">
                <option value={systemTimezone}>
                  System Timezone: {systemTimezone} ({getTimezoneOffsetString(systemTimezone, now)})
                </option>
              </optgroup>
              <optgroup label="Popular Global Timezones">
                {options.slice(0, 22).map((opt) => (
                  <option key={`pop-${opt.value}`} value={opt.value}>
                    {opt.label} ({opt.offset})
                  </option>
                ))}
              </optgroup>
              <optgroup label="All IANA Timezones">
                {options.slice(22).map((opt) => (
                  <option key={`all-${opt.value}`} value={opt.value}>
                    {opt.value} ({opt.offset})
                  </option>
                ))}
              </optgroup>
            </select>

            {/* Quick Filter Search */}
            <input
              type="text"
              data-testid="timezone-filter-input"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search timezones (e.g. London, Tokyo, UTC)..."
              className="w-full px-3 py-1.5 text-xs rounded-md bg-surface-container-lowest border border-outline text-on-surface focus:outline-none focus:border-primary shadow-2xs font-sans placeholder:text-on-surface-variant"
            />
          </div>

          {searchFilter.trim() && filteredOptions.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-1.5 bg-surface-container-lowest rounded-md border border-outline/40">
              {filteredOptions.slice(0, 10).map((opt) => (
                <button
                  key={`quick-${opt.value}`}
                  type="button"
                  onClick={() => {
                    onChange(opt.value);
                    setSearchFilter("");
                  }}
                  className={`text-[11px] px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                    activeTz === opt.value
                      ? "bg-primary text-on-primary border-primary font-medium"
                      : "bg-surface-container border-outline/40 text-on-surface hover:bg-surface-container-high"
                  }`}
                >
                  {activeTz === opt.value && <Check size={11} weight="bold" />}
                  <span>{opt.label}</span>
                  <span className="opacity-70 text-[10px]">{opt.offset}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          Configuring this setting automatically synchronizes all times and dates across LinkedAide—including content calendar slots, approval queue creation times, scout audit logs, and rate-limit reset cycles—to your selected regional timezone.
        </p>
      </div>
    </div>
  );
};
