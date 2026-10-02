import React from "react";
import { ThemeProvider } from "./context/ThemeContext";
import { AppProvider, useApp } from "./context/AppContext";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardView } from "./views/DashboardView";
import { ApprovalQueueView } from "./views/ApprovalQueueView";
import { OutreachQueueView } from "./views/OutreachQueueView";
import { ComposerView } from "./views/ComposerView";
import { CalendarView } from "./views/CalendarView";
import { AnalyticsView } from "./views/AnalyticsView";
import { VaultView } from "./views/VaultView";
import { AuditHistoryView } from "./views/AuditHistoryView";
import { DoctorView } from "./views/DoctorView";
import { SettingsView } from "./views/SettingsView";

const MainContent: React.FC = () => {
  const { currentTab } = useApp();

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
