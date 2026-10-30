import React from "react";
import { AlertOctagon, RefreshCw } from "lucide-react";
import { ApiClientError, getErrorMessage } from "../../utils/errors";

interface ErrorPanelProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorPanel: React.FC<ErrorPanelProps> = ({
  error,
  title = "An error occurred",
  onRetry,
  className = "",
}) => {
  const message = getErrorMessage(error);
  const isNetwork = error instanceof ApiClientError && error.isNetworkError;
  const isContract = error instanceof ApiClientError && error.isContractMismatch;

  return (
    <div
      className={`panel ${className}`}
      style={{
        borderLeft: "4px solid var(--color-danger)",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        margin: "12px 0",
      }}
      role="alert"
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <AlertOctagon size={18} color="var(--color-danger)" />
        <h4 style={{ color: "var(--color-danger)", margin: 0 }}>
          {isContract ? "Integration Contract Mismatch" : isNetwork ? "Backend Connection Error" : title}
        </h4>
      </div>

      <p style={{ color: "var(--color-text)", fontSize: "13px" }}>{message}</p>

      {error instanceof ApiClientError && error.details && error.details.length > 0 && (
        <ul style={{ paddingLeft: "20px", fontSize: "12px", color: "var(--color-text-muted)" }}>
          {error.details.map((d, i) => (
            <li key={i}>
              <strong>{d.field}:</strong> {d.message}
            </li>
          ))}
        </ul>
      )}

      {onRetry && (
        <div style={{ marginTop: "4px" }}>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onRetry}
            style={{ fontSize: "12px", padding: "4px 10px" }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}
    </div>
  );
};
