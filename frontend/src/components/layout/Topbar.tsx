import React, { useState } from "react";
import { Clock, Globe, ChevronDown, ChevronUp, Terminal } from "lucide-react";
import type { SnapshotMeta } from "../../api/types";
import { formatDateTime, formatUtcDateTime, getBrowserTimeZone } from "../../utils/time";

interface TopbarProps {
  meta?: SnapshotMeta;
  onToggleMobileMenu?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ meta }) => {
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const timeZone = getBrowserTimeZone();

  return (
    <header className="app-topbar">
      {/* Simulation Badge & Time indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            backgroundColor: "rgba(139, 128, 255, 0.15)",
            border: "1px solid rgba(139, 128, 255, 0.4)",
            padding: "4px 10px",
            borderRadius: "var(--radius-pill)",
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--color-accent)",
          }}
        >
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: "var(--color-accent)",
            }}
          />
          SIMULATION ENVIRONMENT
        </div>

        {meta && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "13px",
              color: "var(--color-text)",
            }}
            title={`UTC: ${formatUtcDateTime(meta.simulation_time)}`}
          >
            <Clock size={15} color="var(--color-text-muted)" />
            <span>
              <strong>Sim Time:</strong> {formatDateTime(meta.simulation_time)}{" "}
              <span style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>({timeZone})</span>
            </span>
          </div>
        )}
      </div>

      {/* Diagnostics collapse toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {meta && (
          <div
            style={{
              fontSize: "12px",
              color: "var(--color-text-dim)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
            title={`UTC: ${formatUtcDateTime(meta.server_time)}`}
          >
            <Globe size={13} />
            <span>Server: {new Date(meta.server_time).toLocaleTimeString()}</span>
          </div>
        )}

        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setShowDiagnostics(!showDiagnostics)}
          style={{ fontSize: "11px", padding: "4px 8px" }}
          aria-expanded={showDiagnostics}
        >
          <Terminal size={13} />
          <span>Diagnostics</span>
          {showDiagnostics ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      {/* Collapsed diagnostics drawer/strip */}
      {showDiagnostics && meta && (
        <div
          style={{
            width: "100%",
            marginTop: "8px",
            padding: "10px 14px",
            background: "var(--color-panel-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-control)",
            fontSize: "12px",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "10px",
            color: "var(--color-text-muted)",
          }}
        >
          <div>
            <strong>Contract:</strong> <code>{meta.contract_version}</code>
          </div>
          <div>
            <strong>Schedule Version:</strong> <code>v{meta.schedule_version}</code>
          </div>
          <div>
            <strong>State Revision:</strong> <code>#{meta.state_revision}</code>
          </div>
          <div>
            <strong>Scheduler Service:</strong>{" "}
            <span
              style={{
                color: meta.services.scheduler === "ready" ? "var(--color-success)" : "var(--color-danger)",
              }}
            >
              {meta.services.scheduler.toUpperCase()}
            </span>
          </div>
          <div>
            <strong>Security Service:</strong>{" "}
            <span
              style={{
                color: meta.services.security === "ready" ? "var(--color-success)" : "var(--color-danger)",
              }}
            >
              {meta.services.security.toUpperCase()}
            </span>
          </div>
          <div>
            <strong>Visible Window:</strong>{" "}
            <code>
              {new Date(meta.visible_start_at).toLocaleTimeString()} – {new Date(meta.visible_end_at).toLocaleTimeString()}
            </code>
          </div>
        </div>
      )}
    </header>
  );
};
