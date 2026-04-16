import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { AdminShell } from "@/components/admin-shell"
import { AlertsPage } from "@/pages/alerts-page"
import { DashboardPage } from "@/pages/dashboard-page"
import { InstanceDetailPage } from "@/pages/instance-detail-page"
import { SettingsPage } from "@/pages/settings-page"
import { StrategiesPage } from "@/pages/strategies-page"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/admin" replace />} />
        <Route path="/admin" element={<AdminShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="strategies" element={<StrategiesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="instances/:instanceId" element={<InstanceDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
