import React, { useState } from "react";
import { SlidersHorizontal } from "../../components/icons";

interface NotificationsCardProps {
  minimizeToTray: boolean;
  notificationsEnabled: boolean;
  onMinimizeChange: (val: boolean) => void;
  onNotificationsChange: (val: boolean) => void;
}

export const NotificationsCard: React.FC<NotificationsCardProps> = ({
  minimizeToTray,
  notificationsEnabled,
  onMinimizeChange,
  onNotificationsChange,
}) => {
  const [telegramSync, setTelegramSync] = useState(true);
  const [soundEffects, setSoundEffects] = useState(false);

  return (
    <div className="flex flex-col gap-3.5 p-4.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30">
      <div className="flex items-center gap-2.5 pb-1 border-b border-surface-container-high">
        <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <SlidersHorizontal size={16} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface text-[14px]">
            Notifications &amp; Desktop Integration
          </h2>
          <p className="font-label-sm text-[11px] text-on-surface-variant">
            System tray hooks, push events, and peripheral triggers
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-1.5 pt-0.5">
        {/* Toggle 1: Minimize to System Tray */}
        <label className="flex items-center justify-between p-2.5 rounded-md hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-outline-variant/20">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Minimize to System Tray on Window Close
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              Keep background feed scout running silently in the macOS menu bar / Windows tray.
            </span>
          </div>
          <div className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={minimizeToTray}
              onChange={(e) => onMinimizeChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 2: Native OS Notifications */}
        <label className="flex items-center justify-between p-2.5 rounded-md hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-outline-variant/20">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Native OS Notifications on New Approvals
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              Display high-priority desktop notification banners when a new candidate needs review.
            </span>
          </div>
          <div className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={notificationsEnabled}
              onChange={(e) => onNotificationsChange(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 3: Telegram Bot Dispatch Synchronization */}
        <label className="flex items-center justify-between p-2.5 rounded-md hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-outline-variant/20">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Telegram Bot Dispatch Synchronization
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              Mirror pending triage approvals to Telegram chat immediately for 1-click mobile execution.
            </span>
          </div>
          <div className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={telegramSync}
              onChange={(e) => setTelegramSync(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 4: Sound Effects on Dispatch */}
        <label className="flex items-center justify-between p-2.5 rounded-md hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-outline-variant/20">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface text-[13px]">
              Sound Effects on Dispatch
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant text-[12px]">
              Play subtle chime when an approval action is successfully executed.
            </span>
          </div>
          <div className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={soundEffects}
              onChange={(e) => setSoundEffects(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>
      </div>
    </div>
  );
};
