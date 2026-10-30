import React from "react";
import { useOutletContext } from "react-router-dom";
import type { Operation, Session, Snapshot } from "../api/types";
import { AntennaTimeline } from "../components/timeline/AntennaTimeline";
import { useRunScheduleMutation, useCreateTransferMutation } from "../api/mutations";
import { ErrorPanel } from "../components/feedback/ErrorPanel";

interface ContextType {
  snapshot?: Snapshot;
  session?: Session;
  setActiveOperation?: (op: Operation) => void;
}

export const SchedulePage: React.FC = () => {
  const { snapshot, session, setActiveOperation } = useOutletContext<ContextType>();
  const runScheduleMutation = useRunScheduleMutation();
  const createTransferMutation = useCreateTransferMutation();

  const handleRunScheduler = async (expectedVersion: number) => {
    try {
      const op = await runScheduleMutation.mutateAsync({
        algorithm: "optimized",
        expected_schedule_version: expectedVersion,
      });
      if (setActiveOperation) {
        setActiveOperation(op);
      }
    } catch (err) {
      console.error("Failed to run scheduler", err);
    }
  };

  const handleStartTransfer = async (contactId: string) => {
    try {
      const op = await createTransferMutation.mutateAsync({ contact_id: contactId });
      if (setActiveOperation) {
        setActiveOperation(op);
      }
    } catch (err) {
      console.error("Failed to start transfer", err);
    }
  };

  const canStartTransfer = Boolean(session?.user);

  if (!snapshot) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center", color: "var(--color-text-muted)" }}>
        Loading operational schedule...
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div>
        <h2>Antenna & Ground Station Schedule</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Interactive multi-antenna contact timeline with setup intervals, pass opportunities, and simulation-time tracking.
        </p>
      </div>

      {runScheduleMutation.error && (
        <ErrorPanel
          error={runScheduleMutation.error}
          title="Scheduler Execution Conflict"
          onRetry={() => handleRunScheduler(snapshot.meta.schedule_version)}
        />
      )}

      {createTransferMutation.error && (
        <ErrorPanel
          error={createTransferMutation.error}
          title="Secure Transfer Rejection"
        />
      )}

      <AntennaTimeline
        meta={snapshot.meta}
        stations={snapshot.stations}
        contacts={snapshot.contacts}
        jobs={snapshot.jobs}
        opportunities={snapshot.opportunities}
        onRunScheduler={handleRunScheduler}
        isScheduling={runScheduleMutation.isPending}
        onStartTransfer={handleStartTransfer}
        canStartTransfer={canStartTransfer}
      />
    </div>
  );
};
