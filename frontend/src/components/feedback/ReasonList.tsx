import React from "react";
import type { Reason } from "../../api/types";
import { AlertCircle, AlertTriangle, Info, Clock, ShieldAlert } from "lucide-react";

interface ReasonListProps {
  reasons: Reason[] | null | undefined;
  className?: string;
}

export const ReasonList: React.FC<ReasonListProps> = ({ reasons, className = "" }) => {
  if (!reasons || reasons.length === 0) return null;

  const getReasonIcon = (code: string) => {
    switch (code) {
      case "AUTHORIZATION_DENIED":
      case "PARTNER_NOT_APPROVED":
        return <ShieldAlert size={14} className="reason-icon text-danger" />;
      case "DEADLINE_UNREACHABLE":
      case "SETUP_CONFLICT":
      case "ANTENNA_BUSY":
      case "STATION_OFFLINE":
        return <AlertCircle size={14} className="reason-icon text-danger" />;
      case "WEATHER_DEGRADED":
      case "EMERGENCY_REPLAN":
      case "PARTIAL_DELIVERY":
        return <AlertTriangle size={14} className="reason-icon text-warning" />;
      case "ACTIVE_CONTACT_PROTECTED":
      case "STALE_SCHEDULE":
        return <Clock size={14} className="reason-icon text-muted" />;
      default:
        return <Info size={14} className="reason-icon text-muted" />;
    }
  };

  return (
    <div className={`reasons-container ${className}`} style={{ marginTop: "4px" }}>
      {reasons.map((r, index) => (
        <div
          key={`${r.code}-${index}`}
          className="reason-item"
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "6px",
            fontSize: "12px",
            color: "var(--color-text-muted)",
            padding: "2px 0",
          }}
        >
          <span style={{ marginTop: "2px" }}>{getReasonIcon(r.code)}</span>
          <div>
            <strong style={{ color: "var(--color-text)" }}>[{r.code}]</strong>{" "}
            <span>{r.message}</span>
            {r.resource_ids && r.resource_ids.length > 0 && (
              <span style={{ color: "var(--color-text-dim)", marginLeft: "4px" }}>
                ({r.resource_ids.join(", ")})
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
