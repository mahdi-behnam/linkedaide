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
    <div className="flex flex-col gap-4 p-6 rounded-2xl bg-surface-container-lowest shadow-xs border border-surface-container-high">
      <div className="flex items-center gap-3 pb-1 border-b border-surface-container-high">
        <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <SlidersHorizontal size={18} weight="bold" />
        </div>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">
            Notifications &amp; Desktop Integration
          </h2>
          <p className="font-label-sm text-label-sm text-on-surface-variant">
            System tray hooks, push events, and peripheral triggers
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2 pt-1">
        {/* Toggle 1: Minimize to System Tray */}
        <label className="flex items-center justify-between p-3.5 rounded-xl hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-surface-container-high">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface">
              Minimize to System Tray on Window Close
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant">
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
            <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 2: Native OS Notifications */}
        <label className="flex items-center justify-between p-3.5 rounded-xl hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-surface-container-high">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface">
              Native OS Notifications on New Approvals
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant">
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
            <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 3: Telegram Bot Dispatch Synchronization */}
        <label className="flex items-center justify-between p-3.5 rounded-xl hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-surface-container-high">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface">
              Telegram Bot Dispatch Synchronization
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant">
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
            <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>

        {/* Toggle 4: Sound Effects on Dispatch */}
        <label className="flex items-center justify-between p-3.5 rounded-xl hover:bg-surface-container-low/60 transition-colors cursor-pointer border border-transparent hover:border-surface-container-high">
          <div className="flex flex-col gap-0.5 pr-4">
            <span className="font-body-strong text-body-strong text-on-surface">
              Sound Effects on Dispatch
            </span>
            <span className="font-body-md text-body-md text-on-surface-variant">
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
            <div className="w-11 h-6 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary shadow-2xs" />
          </div>
        </label>
      </div>
    </div>
  );
};
