import React from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardView } from "./views/DashboardView";
import { ApprovalQueueView } from "./views/ApprovalQueueView";
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
    <AppProvider>
      <AppLayout>
        <MainContent />
      </AppLayout>
    </AppProvider>
  );
};

export default App;
