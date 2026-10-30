import React, { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { ConnectionBanner } from "./ConnectionBanner";
import { SimToolbar } from "./SimToolbar";
import { useSession, useSnapshot } from "../../api/queries";
import { useLogoutMutation, useSimulationActionMutation } from "../../api/mutations";
import { OperationProgress } from "../feedback/OperationProgress";
import type { Operation } from "../../api/types";

export const AppShell: React.FC = () => {
  const navigate = useNavigate();
  const { data: session } = useSession();
  const logoutMutation = useLogoutMutation();
  const simActionMutation = useSimulationActionMutation();

  const [activeOperation, setActiveOperation] = useState<Operation | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Poll snapshot every 2 seconds when authenticated
  const {
    data: snapshot,
    isError,
    isStaleData,
    lastSuccessfulAt,
    refetch,
  } = useSnapshot(Boolean(session?.user));

  const handleLogout = async () => {
    try {
      await logoutMutation.mutateAsync();
    } finally {
      navigate("/login");
    }
  };

  const handleSimAction = async (
    action: "pause" | "resume" | "step" | "reset",
    stepSeconds?: number,
    seed?: number
  ) => {
    try {
      const op = await simActionMutation.mutateAsync({
        action,
        step_seconds: stepSeconds,
        seed,
      });
      setActiveOperation(op);
    } catch (err) {
      console.error("Simulation action failed", err);
    }
  };

  const isAdmin = session?.user?.role === "network_admin";

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar
        user={session?.user || null}
        organizations={snapshot?.organizations || []}
        onLogout={handleLogout}
        isOpenMobile={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
      />

      {/* Main Workspace */}
      <div className="app-main">
        <Topbar
          meta={snapshot?.meta}
          onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)}
        />

        <ConnectionBanner
          isError={isError}
          isStale={isStaleData}
          lastSuccessfulAt={lastSuccessfulAt}
          simulatorStatus={snapshot?.simulator?.connection_status}
          onRetry={() => refetch()}
        />

        <div className="app-content">
          {snapshot?.simulator && (
            <SimToolbar
              simulator={snapshot.simulator}
              isAdmin={isAdmin}
              onAction={handleSimAction}
              isLoading={simActionMutation.isPending}
            />
          )}

          {activeOperation && (
            <OperationProgress
              operation={activeOperation}
              onDismiss={() => setActiveOperation(null)}
            />
          )}

          {/* Child Page Content */}
          <Outlet context={{ snapshot, session, setActiveOperation }} />
        </div>
      </div>
    </div>
  );
};
