import React, { Suspense, lazy, useState, useEffect } from "react";
import { ThemeProvider } from "./context/ThemeContext";
import { AppProvider, useApp } from "./context/AppContext";
import { AppLayout } from "./layouts/AppLayout";

import { NavigationTab } from "./types";

const DashboardView = lazy(() => import("./views/DashboardView").then((m) => ({ default: m.DashboardView })));
const ApprovalQueueView = lazy(() => import("./views/ApprovalQueueView").then((m) => ({ default: m.ApprovalQueueView })));
const OutreachQueueView = lazy(() => import("./views/OutreachQueueView").then((m) => ({ default: m.OutreachQueueView })));
const ComposerView = lazy(() => import("./views/ComposerView").then((m) => ({ default: m.ComposerView })));
const CalendarView = lazy(() => import("./views/CalendarView").then((m) => ({ default: m.CalendarView })));
const AnalyticsView = lazy(() => import("./views/AnalyticsView").then((m) => ({ default: m.AnalyticsView })));
const VaultView = lazy(() => import("./views/VaultView").then((m) => ({ default: m.VaultView })));
const AuditHistoryView = lazy(() => import("./views/AuditHistoryView").then((m) => ({ default: m.AuditHistoryView })));
const DoctorView = lazy(() => import("./views/DoctorView").then((m) => ({ default: m.DoctorView })));
const SettingsView = lazy(() => import("./views/SettingsView").then((m) => ({ default: m.SettingsView })));

const TAB_COMPONENTS: { id: NavigationTab; component: React.ComponentType }[] = [
  { id: "dashboard", component: DashboardView },
  { id: "queue", component: ApprovalQueueView },
  { id: "outreach", component: OutreachQueueView },
  { id: "composer", component: ComposerView },
  { id: "calendar", component: CalendarView },
  { id: "analytics", component: AnalyticsView },
  { id: "vault", component: VaultView },
  { id: "history", component: AuditHistoryView },
  { id: "doctor", component: DoctorView },
  { id: "settings", component: SettingsView },
];

const ViewLoadingFallback: React.FC = () => (
  <div className="flex items-center justify-center h-full min-h-[350px] text-gray-400">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
  </div>
);

const MainContent: React.FC = () => {
  const { currentTab } = useApp();
  const [visitedTabs, setVisitedTabs] = useState<Set<NavigationTab>>(() => new Set([currentTab]));

  useEffect(() => {
    setVisitedTabs((prev: Set<NavigationTab>) => {
      if (prev.has(currentTab)) return prev;
      const next = new Set<NavigationTab>(prev);
      next.add(currentTab);
      return next;
    });
  }, [currentTab]);

  return (
    <Suspense fallback={<ViewLoadingFallback />}>
      {TAB_COMPONENTS.map(({ id, component: Component }) => {
        if (!visitedTabs.has(id)) return null;
        const isActive = currentTab === id;
        return (
          <div
            key={id}
            className={isActive ? "contents" : "hidden"}
            aria-hidden={!isActive}
          >
            <Component />
          </div>
        );
      })}
    </Suspense>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AppProvider>
        <AppLayout>
          <MainContent />
        </AppLayout>
      </AppProvider>
    </ThemeProvider>
  );
};

export default App;
