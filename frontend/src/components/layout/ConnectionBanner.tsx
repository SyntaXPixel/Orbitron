import React from "react";
import { AlertCircle, AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { isContractMismatch } from "../../api/client";

interface ConnectionBannerProps {
  isError: boolean;
  isStale: boolean;
  lastSuccessfulAt: number;
  simulatorStatus?: "connected" | "stale" | "disconnected";
  onRetry: () => void;
}

export const ConnectionBanner: React.FC<ConnectionBannerProps> = ({
  isError,
  isStale,
  lastSuccessfulAt,
  simulatorStatus,
  onRetry,
}) => {
  const contractMismatch = isContractMismatch();

  if (contractMismatch) {
    return (
      <div
        style={{
          backgroundColor: "rgba(255, 127, 138, 0.2)",
          borderBottom: "1px solid var(--color-danger)",
          color: "var(--color-danger)",
          padding: "10px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "13px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AlertCircle size={16} />
          <strong>Contract Version Mismatch:</strong>
          <span>
            The backend reported an incompatible API contract version (expected <code>orbitron.v1</code>). Mutations have been disabled.
          </span>
        </div>
      </div>
    );
  }

  if (isError) {
    const ageSeconds = Math.round((Date.now() - lastSuccessfulAt) / 1000);
    return (
      <div
        style={{
          backgroundColor: "rgba(243, 189, 98, 0.2)",
          borderBottom: "1px solid var(--color-warning)",
          color: "var(--color-warning)",
          padding: "10px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "13px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <WifiOff size={16} />
          <strong>Backend Unreachable:</strong>
          <span>
            {isStale
              ? `Retaining operational snapshot from ${ageSeconds}s ago. Operational records are stale.`
              : "Unable to connect to Orbitron backend."}
          </span>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onRetry}
          style={{ fontSize: "12px", padding: "4px 10px", borderColor: "var(--color-warning)" }}
        >
          <RefreshCw size={13} /> Reconnect
        </button>
      </div>
    );
  }

  if (simulatorStatus === "disconnected") {
    return (
      <div
        style={{
          backgroundColor: "rgba(243, 189, 98, 0.15)",
          borderBottom: "1px solid var(--color-warning)",
          color: "var(--color-warning)",
          padding: "8px 24px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontSize: "12px",
        }}
      >
        <AlertTriangle size={14} />
        <strong>Simulator Disconnected:</strong>
        <span>
          The simulated satellite fleet is disconnected from backend gateway ingestion. Displaying last reported telemetry.
        </span>
      </div>
    );
  }

  return null;
};
