import React from "react";
import { X, Radio, Satellite, ShieldCheck } from "lucide-react";
import type { Contact, Job, Opportunity, Station } from "../../api/types";
import { StatusBadge } from "../feedback/StatusBadge";
import { ReasonList } from "../feedback/ReasonList";
import { formatBytes, formatRate } from "../../utils/format";
import { formatUtcDateTime } from "../../utils/time";

interface ContactDetailModalProps {
  contact: Contact | null;
  job?: Job;
  station?: Station;
  opportunity?: Opportunity;
  onClose: () => void;
  onStartTransfer?: (contactId: string) => void;
  canStartTransfer?: boolean;
}

export const ContactDetailModal: React.FC<ContactDetailModalProps> = ({
  contact,
  job,
  station,
  opportunity,
  onClose,
  onStartTransfer,
  canStartTransfer = false,
}) => {
  if (!contact) return null;

  const antenna = station?.antennas.find((a) => a.id === contact.antenna_id);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(4, 9, 19, 0.7)",
        backdropFilter: "blur(2px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
      onClick={onClose}
      role="dialog"
      aria-label="Contact Details"
    >
      <div
        className="panel"
        style={{
          width: "100%",
          maxWidth: "520px",
          backgroundColor: "var(--color-panel)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Radio size={20} color="var(--color-accent)" />
            <div>
              <h3 style={{ margin: 0 }}>Contact: {contact.id}</h3>
              <div style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>
                Schedule Version: v{contact.schedule_version}
              </div>
            </div>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose} style={{ padding: "4px" }}>
            <X size={18} />
          </button>
        </div>

        {/* Statuses */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>Contact Status:</span>
          <StatusBadge status={contact.status} />

          <span style={{ fontSize: "12px", color: "var(--color-text-muted)", marginLeft: "8px" }}>
            Authorization:
          </span>
          <StatusBadge status={contact.authorization_status} />
        </div>

        {/* Resource info grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12px",
            padding: "12px",
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "var(--radius-control)",
            fontSize: "12px",
          }}
        >
          <div>
            <div className="form-label">Satellite</div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-text)" }}>
              <Satellite size={14} />
              <strong>{contact.satellite_id}</strong>
            </div>
          </div>

          <div>
            <div className="form-label">Job ID</div>
            <div style={{ color: "var(--color-text)" }}>
              <code>{contact.job_id}</code>
              {job && <span style={{ marginLeft: "6px", color: "var(--color-text-dim)" }}>({job.priority})</span>}
            </div>
          </div>

          <div>
            <div className="form-label">Station & Antenna</div>
            <div style={{ color: "var(--color-text)" }}>
              {station?.name || contact.station_id} / {antenna?.name || contact.antenna_id}
            </div>
          </div>

          <div>
            <div className="form-label">Band</div>
            <div style={{ color: "var(--color-text)" }}>
              <span className="badge badge-muted">{contact.band}</span>
            </div>
          </div>
        </div>

        {/* Timing Details */}
        <div className="panel-raised" style={{ padding: "12px", fontSize: "12px" }}>
          <div className="form-label" style={{ marginBottom: "8px" }}>
            Timeline Windows
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div>
              <strong>Setup Interval:</strong> {new Date(contact.setup_start_at).toLocaleTimeString()} –{" "}
              {new Date(contact.start_at).toLocaleTimeString()}
            </div>
            <div>
              <strong>Communication Window:</strong> {new Date(contact.start_at).toLocaleTimeString()} –{" "}
              {new Date(contact.end_at).toLocaleTimeString()}
            </div>
            <div style={{ color: "var(--color-text-dim)" }}>
              <strong>Pass Visibility:</strong> {new Date(contact.window_start_at).toLocaleTimeString()} –{" "}
              {new Date(contact.window_end_at).toLocaleTimeString()}{" "}
              {opportunity && `(Predicted: ${formatRate(opportunity.predicted_rate_bps)})`}
            </div>
            <div style={{ color: "var(--color-text-dim)", fontSize: "11px" }}>
              UTC: {formatUtcDateTime(contact.start_at)} → {formatUtcDateTime(contact.end_at)}
            </div>
          </div>
        </div>

        {/* Data Allocation */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: "8px",
            padding: "12px",
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "var(--radius-control)",
            fontSize: "12px",
          }}
        >
          <div>
            <div className="form-label">Allocated</div>
            <strong style={{ color: "var(--color-pure-white)" }}>
              {formatBytes(contact.allocated_bytes)}
            </strong>
          </div>
          <div>
            <div className="form-label">Transferred</div>
            <strong style={{ color: "var(--color-success)" }}>
              {formatBytes(contact.transferred_bytes)}
            </strong>
          </div>
          <div>
            <div className="form-label">Data Rate</div>
            <strong style={{ color: "var(--color-text)" }}>
              {formatRate(contact.expected_rate_bps)}
            </strong>
          </div>
        </div>

        {/* Reasons */}
        {contact.reasons && contact.reasons.length > 0 && (
          <div>
            <div className="form-label" style={{ marginBottom: "4px" }}>
              Decision / Scheduling Reasons
            </div>
            <ReasonList reasons={contact.reasons} />
          </div>
        )}

        {/* Footer Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "8px" }}>
          {canStartTransfer && onStartTransfer && contact.status === "confirmed" && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onStartTransfer(contact.id)}
            >
              <ShieldCheck size={14} /> Start Secure Transfer
            </button>
          )}
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
