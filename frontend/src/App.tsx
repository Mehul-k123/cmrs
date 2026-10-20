import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import type { Role } from "./api/types";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import AuditLogPage from "./pages/AuditLog";
import CollectionsPage from "./pages/Collections";
import CustomerDetail from "./pages/CustomerDetail";
import CustomersPage from "./pages/Customers";
import DailyCollections from "./pages/DailyCollections";
import Dashboard from "./pages/Dashboard";
import DepositsPage from "./pages/Deposits";
import DiscrepanciesPage from "./pages/Discrepancies";
import LoanDetail from "./pages/LoanDetail";
import Login from "./pages/Login";
import PaymentsPage from "./pages/Payments";
import RecordCollection from "./pages/RecordCollection";
import SubmissionsPage from "./pages/Submissions";
import SubmitCash from "./pages/SubmitCash";

function Guard({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner className="h-screen" />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

const STAFF: Role[] = ["ADMIN", "FINANCE", "BRANCH_MANAGER"];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Guard>
            <Layout />
          </Guard>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:id" element={<CustomerDetail />} />
        <Route path="loans/:id" element={<LoanDetail />} />
        <Route path="collect" element={<Guard roles={["AGENT"]}><RecordCollection /></Guard>} />
        <Route path="daily" element={<Guard roles={["AGENT"]}><DailyCollections /></Guard>} />
        <Route path="submit" element={<Guard roles={["AGENT"]}><SubmitCash /></Guard>} />
        <Route path="collections" element={<Guard roles={STAFF}><CollectionsPage /></Guard>} />
        <Route path="submissions" element={<SubmissionsPage />} />
        <Route path="discrepancies" element={<Guard roles={STAFF}><DiscrepanciesPage /></Guard>} />
        <Route path="deposits" element={<Guard roles={STAFF}><DepositsPage /></Guard>} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="audit" element={<Guard roles={["ADMIN", "FINANCE"]}><AuditLogPage /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
