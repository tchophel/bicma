import { ConfirmProvider } from "./components/Confirm";
import { PasswordRecovery } from "./pages/staff/PasswordRecovery";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ToastProvider } from "./components/Toast";
import { GlobalLoader } from "./components/Loader";
import { PublicLayout, StaffLayout } from "./components/Layout";
import { Help } from "./pages/staff/Help";
import { Home } from "./pages/public/Home";
import { Submit, Submitted } from "./pages/public/Submit";
import { Track } from "./pages/public/Track";
import { NotFound } from "./pages/public/NotFound";
import { Categories } from "./pages/staff/Categories";
import { ComplaintView } from "./pages/staff/ComplaintView";
import { Complaints } from "./pages/staff/Complaints";
import { DashboardPage } from "./pages/staff/Dashboard";
import { Divisions } from "./pages/staff/Divisions";
import { Dzongkhags } from "./pages/staff/Dzongkhags";
import { Login } from "./pages/staff/Login";
import { Profile } from "./pages/staff/Profile";
import { Register } from "./pages/staff/Register";
import { SettingsPage } from "./pages/staff/Settings";
import { WorkflowPage } from "./pages/staff/Workflow";
import { Users } from "./pages/staff/Users";
import { Reports } from "./pages/staff/Reports";
import { Permissions } from "./pages/staff/Permissions";
import { Uploads } from "./pages/staff/Uploads";
import { Logs } from "./pages/staff/Logs";
import { Roles } from "./pages/staff/MasterPage";
import { CableTv } from "./pages/staff/CableTv";
import { ClosureReasons, Outcomes, Priorities, ProviderTypes, Providers } from "./pages/staff/MasterPage";

function AdminOnly({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  return user?.base_role === "super_admin" ? children : <Navigate to="/staff/dashboard" replace />;
}

export default function App() {
  return (
    <ToastProvider>
    <ConfirmProvider>
    <AuthProvider>
      <GlobalLoader />
      <BrowserRouter>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<Home />} />
            <Route path="submit" element={<Submit />} />
            <Route path="submitted" element={<Submitted />} />
            <Route path="track" element={<Track />} />
            <Route path="help" element={<Navigate to="/staff/help" replace />} />
            <Route path="staff" element={<Login />} />
            <Route path="staff/forgot-password" element={<PasswordRecovery key="request" />} />
            <Route path="staff/reset-password/:uid/:token" element={<PasswordRecovery key="reset" reset />} />
            <Route path="*" element={<NotFound />} />
          </Route>
          <Route path="staff" element={<StaffLayout />}>
            <Route path="profile" element={<Profile />} />
            <Route path="help" element={<AdminOnly><Help /></AdminOnly>} />
            <Route path="settings" element={<AdminOnly><SettingsPage /></AdminOnly>} />
            <Route path="workflow" element={<AdminOnly><WorkflowPage /></AdminOnly>} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="complaints" element={<Complaints />} />
            <Route path="complaints/:id" element={<ComplaintView />} />
            <Route path="register" element={<Register />} />
            <Route path="users" element={<AdminOnly><Users /></AdminOnly>} />
            <Route path="dzongkhags" element={<AdminOnly><Dzongkhags /></AdminOnly>} />
            <Route path="divisions" element={<AdminOnly><Divisions /></AdminOnly>} />
            <Route path="categories" element={<AdminOnly><Categories /></AdminOnly>} />
            <Route path="roles" element={<AdminOnly><Roles /></AdminOnly>} />
            <Route path="uploads" element={<AdminOnly><Uploads /></AdminOnly>} />
            <Route path="permissions" element={<AdminOnly><Permissions /></AdminOnly>} />
            <Route path="reports" element={<Reports />} />
            <Route path="cable-tv" element={<AdminOnly><CableTv /></AdminOnly>} />
            <Route path="providers" element={<AdminOnly><Providers /></AdminOnly>} />
            <Route path="provider-types" element={<AdminOnly><ProviderTypes /></AdminOnly>} />
            <Route path="priorities" element={<AdminOnly><Priorities /></AdminOnly>} />
            <Route path="outcomes" element={<AdminOnly><Outcomes /></AdminOnly>} />
            <Route path="closure-reasons" element={<AdminOnly><ClosureReasons /></AdminOnly>} />
            <Route path="logs" element={<AdminOnly><Logs /></AdminOnly>} />
            <Route path="audit" element={<Navigate to="/staff/logs?tab=audit" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ConfirmProvider>
    </ToastProvider>
  );
}
