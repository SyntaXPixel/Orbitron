import React from "react";
import { Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import type { Operation } from "../../api/types";
import { ReasonList } from "./ReasonList";

interface OperationProgressProps {
  operation: Operation | null | undefined;
  title?: string;
  onDismiss?: () => void;
}

export const OperationProgress: React.FC<OperationProgressProps> = ({
  operation,
  title = "Operation",
  onDismiss,
}) => {
  if (!operation) return null;

  const isPending = operation.status === "queued" || operation.status === "running";
  const isSucceeded = operation.status === "succeeded";
  const isFailed = operation.status === "failed";

  return (
    <div
      className="panel-raised"
      style={{
        margin: "12px 0",
        borderLeft: `4px solid ${
          isSucceeded
            ? "var(--color-success)"
            : isFailed
            ? "var(--color-danger)"
            : "var(--color-accent)"
        }`,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {isPending && <Loader2 size={16} className="spin" color="var(--color-accent)" />}
          {isSucceeded && <CheckCircle2 size={16} color="var(--color-success)" />}
          {isFailed && <XCircle size={16} color="var(--color-danger)" />}
          <strong style={{ fontSize: "13px", color: "var(--color-pure-white)" }}>
            {title}: {operation.kind} ({operation.status.toUpperCase()})
          </strong>
        </div>

        {onDismiss && !isPending && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onDismiss}
            style={{ fontSize: "11px", padding: "2px 8px" }}
          >
            Dismiss
          </button>
        )}
      </div>

      <div style={{ fontSize: "12px", color: "var(--color-text-muted)", display: "flex", gap: "16px" }}>
        <span>
          <Clock size={12} style={{ display: "inline", marginRight: "4px" }} />
          Submitted: {new Date(operation.submitted_at).toLocaleTimeString()}
        </span>
        {operation.completed_at && (
          <span>Completed: {new Date(operation.completed_at).toLocaleTimeString()}</span>
        )}
        <span style={{ color: "var(--color-text-dim)" }}>ID: {operation.id}</span>
      </div>

      {operation.reasons && operation.reasons.length > 0 && (
        <ReasonList reasons={operation.reasons} />
      )}

      <style>{`
        .spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
