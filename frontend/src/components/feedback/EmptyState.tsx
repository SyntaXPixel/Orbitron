import React from "react";
import { FolderOpen } from "lucide-react";

interface EmptyStateProps {
  message: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  message,
  description,
  action,
  icon,
}) => {
  return (
    <div
      style={{
        padding: "40px 20px",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "12px",
        color: "var(--color-text-muted)",
        border: "1px dashed var(--color-border)",
        borderRadius: "var(--radius-panel)",
        backgroundColor: "rgba(17, 30, 48, 0.4)",
      }}
    >
      <div style={{ color: "var(--color-text-dim)" }}>
        {icon || <FolderOpen size={36} />}
      </div>
      <div>
        <h4 style={{ color: "var(--color-text)", marginBottom: "4px" }}>{message}</h4>
        {description && <p style={{ fontSize: "13px", color: "var(--color-text-muted)" }}>{description}</p>}
      </div>
      {action && <div style={{ marginTop: "8px" }}>{action}</div>}
    </div>
  );
};
