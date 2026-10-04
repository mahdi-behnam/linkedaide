import React, { Suspense, lazy } from "react";
import { ThemeProvider } from "./context/ThemeContext";
import { AppProvider, useApp } from "./context/AppContext";
import { AppLayout } from "./layouts/AppLayout";

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

const ViewLoadingFallback: React.FC = () => (
  <div className="flex items-center justify-center h-full min-h-[350px] text-gray-400">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
  </div>
);

const MainContent: React.FC = () => {
  const { currentTab } = useApp();

  return (
    <Suspense fallback={<ViewLoadingFallback />}>
      {(() => {
        switch (currentTab) {
          case "dashboard":
            return <DashboardView />;
          case "queue":
            return <ApprovalQueueView />;
          case "outreach":
            return <OutreachQueueView />;
          case "composer":
            return <ComposerView />;
          case "calendar":
            return <CalendarView />;
          case "analytics":
            return <AnalyticsView />;
          case "vault":
            return <VaultView />;
          case "history":
            return <AuditHistoryView />;
          case "doctor":
            return <DoctorView />;
          case "settings":
            return <SettingsView />;
          default:
            return <DashboardView />;
        }
      })()}
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
