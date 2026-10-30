import React, { useState } from "react";
import { Play, Pause, FastForward, RotateCcw } from "lucide-react";
import type { SimulatorState } from "../../api/types";
import { StatusBadge } from "../feedback/StatusBadge";
import { ConfirmDialog } from "../feedback/ConfirmDialog";

interface SimToolbarProps {
  simulator: SimulatorState | null | undefined;
  isAdmin: boolean;
  onAction: (action: "pause" | "resume" | "step" | "reset", stepSeconds?: number, seed?: number) => void;
  isLoading?: boolean;
}

export const SimToolbar: React.FC<SimToolbarProps> = ({
  simulator,
  isAdmin,
  onAction,
  isLoading = false,
}) => {
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  if (!simulator) return null;

  const isPaused = simulator.run_state === "paused";
  const isRunning = simulator.run_state === "running";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px",
        padding: "8px 16px",
        backgroundColor: "var(--color-panel-raised)",
        borderRadius: "var(--radius-control)",
        border: "1px solid var(--color-border)",
        marginBottom: "16px",
      }}
    >
      {/* State & Connection Indicators */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "11px", color: "var(--color-text-dim)", textTransform: "uppercase" }}>
            Fleet Simulator:
          </span>
          <StatusBadge status={simulator.run_state} />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ fontSize: "11px", color: "var(--color-text-dim)", textTransform: "uppercase" }}>
            Gateway Connection:
          </span>
          <StatusBadge status={simulator.connection_status} />
        </div>

        <div style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
          Speed: <strong>{simulator.speed_multiplier}x</strong>
        </div>
      </div>

      {/* Admin Controls */}
      {isAdmin && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {isRunning ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => onAction("pause")}
              disabled={isLoading}
              style={{ fontSize: "12px", padding: "4px 10px" }}
              title="Pause simulation progression"
            >
              <Pause size={13} /> Pause
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => onAction("resume")}
              disabled={isLoading}
              style={{ fontSize: "12px", padding: "4px 10px", borderColor: "var(--color-success)" }}
              title="Resume simulation progression"
            >
              <Play size={13} color="var(--color-success)" /> Resume
            </button>
          )}

          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => onAction("step", 60)}
            disabled={!isPaused || isLoading}
            style={{ fontSize: "12px", padding: "4px 10px" }}
            title={isPaused ? "Advance operational time by 60 seconds" : "Available only while paused"}
          >
            <FastForward size={13} /> Step (+60s)
          </button>

          <button
            type="button"
            className="btn btn-danger-ghost"
            onClick={() => setShowResetConfirm(true)}
            disabled={isLoading}
            style={{ fontSize: "12px", padding: "4px 10px" }}
            title="Reset scenario demonstration baseline"
          >
            <RotateCcw size={13} /> Reset Scenario
          </button>
        </div>
      )}

      {/* Confirmation Dialog for Reset */}
      <ConfirmDialog
        isOpen={showResetConfirm}
        isDangerous
        title="Reset Simulation Scenario"
        message="Are you sure you want to reset the simulation scenario? This will reinitialize the operational state and scenario seed. All live contacts, telemetry and jobs will be reset to baseline."
        confirmLabel="Reset State"
        onConfirm={() => {
          setShowResetConfirm(false);
          onAction("reset", undefined, 42);
        }}
        onCancel={() => setShowResetConfirm(false)}
      />
    </div>
  );
};
