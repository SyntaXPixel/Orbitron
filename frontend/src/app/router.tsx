import React from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { LoginPage } from "../pages/LoginPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SchedulePage } from "../pages/SchedulePage";
import { RequestsPage } from "../pages/RequestsPage";
import { RecoveryPage } from "../pages/RecoveryPage";
import { SecurityPage } from "../pages/SecurityPage";
import { EvaluationPage } from "../pages/EvaluationPage";
import { AuditPage } from "../pages/AuditPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { useSession } from "../api/queries";

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: session, isLoading, isError } = useSession();

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "var(--color-bg)",
          color: "var(--color-text-muted)",
        }}
      >
        Initializing Orbitron session...
      </div>
    );
  }

  if (isError || !session?.user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <OverviewPage />,
      },
      {
        path: "schedule",
        element: <SchedulePage />,
      },
      {
        path: "requests",
        element: <RequestsPage />,
      },
      {
        path: "recovery",
        element: <RecoveryPage />,
      },
      {
        path: "security",
        element: <SecurityPage />,
      },
      {
        path: "evaluation",
        element: <EvaluationPage />,
      },
      {
        path: "audit",
        element: <AuditPage />,
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
