import React, { useEffect } from "react";
import { X, Satellite as SatIcon, Radio, Shield, Clock } from "lucide-react";
import type { Organization, Satellite, Station } from "../../api/types";
import { StatusBadge } from "../feedback/StatusBadge";
import { formatBytes, formatCapacityFactor, formatRate } from "../../utils/format";
import { formatDateTime } from "../../utils/time";

interface DetailDrawerProps {
  item: Satellite | Station | null;
  type: "satellite" | "station" | null;
  organizations: Organization[];
  onClose: () => void;
}

export const DetailDrawer: React.FC<DetailDrawerProps> = ({
  item,
  type,
  organizations,
  onClose,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (item) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [item, onClose]);

  if (!item || !type) return null;

  const orgName =
    organizations.find((o) => o.id === item.owner_org_id)?.name || item.owner_org_id;

  const isSatellite = type === "satellite";
  const sat = isSatellite ? (item as Satellite) : null;
  const station = !isSatellite ? (item as Station) : null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(4, 9, 19, 0.6)",
        backdropFilter: "blur(2px)",
        display: "flex",
        justifyContent: "flex-end",
        zIndex: 900,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          height: "100%",
          backgroundColor: "var(--color-panel)",
          borderLeft: "1px solid var(--color-border)",
          boxShadow: "-8px 0 24px rgba(0, 0, 0, 0.6)",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Detail view"
      >
        {/* Drawer Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                backgroundColor: "var(--color-panel-raised)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-accent)",
              }}
            >
              {isSatellite ? <SatIcon size={20} /> : <Radio size={20} />}
            </div>
            <div>
              <h3 style={{ margin: 0 }}>{item.name}</h3>
              <div style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
                ID: <code>{item.id}</code>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            style={{ padding: "6px" }}
            aria-label="Close drawer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Status Strip */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 14px",
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "var(--radius-control)",
          }}
        >
          <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>Operational:</span>
          <StatusBadge status={item.operational_status} />
          {sat && (
            <>
              <span style={{ fontSize: "12px", color: "var(--color-text-muted)", marginLeft: "8px" }}>
                Telemetry:
              </span>
              <StatusBadge status={sat.telemetry_status} />
            </>
          )}
          {station && (
            <>
              <span style={{ fontSize: "12px", color: "var(--color-text-muted)", marginLeft: "8px" }}>
                Gateway:
              </span>
              <StatusBadge status={station.connection_status} />
            </>
          )}
        </div>

        {/* Satellite details */}
        {sat && (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "13px" }}>
            <div>
              <div className="form-label">Owner Organization</div>
              <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>{orgName}</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <div className="form-label">Onboard Data</div>
                <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>
                  {formatBytes(sat.onboard_bytes)}
                </div>
              </div>
              <div>
                <div className="form-label">Max Downlink Rate</div>
                <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>
                  {formatRate(sat.max_downlink_rate_bps)}
                </div>
              </div>
            </div>

            <div>
              <div className="form-label">Supported Frequency Bands</div>
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "4px" }}>
                {sat.supported_bands.map((b) => (
                  <span key={b} className="badge badge-muted">
                    {b}
                  </span>
                ))}
              </div>
            </div>

            <div className="panel-raised" style={{ padding: "12px" }}>
              <div className="form-label" style={{ marginBottom: "6px" }}>
                Observed Position (Simulated)
              </div>
              {sat.position ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
                  <div>Latitude: <strong>{sat.position.latitude_deg.toFixed(4)}°</strong></div>
                  <div>Longitude: <strong>{sat.position.longitude_deg.toFixed(4)}°</strong></div>
                  <div>Altitude: <strong>{sat.position.altitude_km.toFixed(1)} km</strong></div>
                  <div>Observed: <strong>{formatDateTime(sat.position.observed_at)}</strong></div>
                </div>
              ) : (
                <div style={{ color: "var(--color-text-dim)", fontStyle: "italic", fontSize: "12px" }}>
                  Position telemetry currently unavailable.
                </div>
              )}
            </div>

            <div style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
              <div>Provenance: <code>{sat.source}</code> ({sat.orbit_source})</div>
              {sat.orbit_epoch_at && <div>Epoch: {formatDateTime(sat.orbit_epoch_at)}</div>}
              {sat.last_telemetry_at && <div>Last Telemetry: {formatDateTime(sat.last_telemetry_at)}</div>}
            </div>
          </div>
        )}

        {/* Station details */}
        {station && (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "13px" }}>
            <div>
              <div className="form-label">Operator Organization</div>
              <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>{orgName}</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <div className="form-label">Weather Capacity</div>
                <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>
                  {formatCapacityFactor(station.weather_capacity_factor)}
                </div>
              </div>
              <div>
                <div className="form-label">Min Elevation</div>
                <div style={{ color: "var(--color-pure-white)", marginTop: "2px" }}>
                  {station.min_elevation_deg}°
                </div>
              </div>
            </div>

            <div className="panel-raised" style={{ padding: "12px" }}>
              <div className="form-label" style={{ marginBottom: "6px" }}>
                Antennas ({station.antennas.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {station.antennas.map((ant) => (
                  <div
                    key={ant.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "6px 8px",
                      backgroundColor: "var(--color-panel)",
                      borderRadius: "var(--radius-control)",
                      fontSize: "12px",
                    }}
                  >
                    <div>
                      <strong>{ant.name}</strong>
                      <div style={{ color: "var(--color-text-dim)", fontSize: "11px" }}>
                        Bands: {ant.supported_bands.join(", ")} | Setup: {ant.setup_seconds}s
                      </div>
                    </div>
                    <StatusBadge status={ant.status} />
                  </div>
                ))}
              </div>
            </div>

            <div className="panel-raised" style={{ padding: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
                <Shield size={14} color="var(--color-accent)" />
                <span className="form-label" style={{ margin: 0 }}>
                  Network Sharing Policy
                </span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--color-text)" }}>
                Sharing: <strong>{station.sharing_enabled ? "Enabled" : "Disabled"}</strong>
              </div>
              {station.sharing_enabled && (
                <div style={{ fontSize: "11px", color: "var(--color-text-muted)", marginTop: "4px" }}>
                  Approved Partner Orgs:{" "}
                  {station.approved_partner_org_ids.length > 0
                    ? station.approved_partner_org_ids.join(", ")
                    : "None configured"}
                </div>
              )}
            </div>

            {station.last_heartbeat_at && (
              <div style={{ fontSize: "12px", color: "var(--color-text-dim)", display: "flex", alignItems: "center", gap: "4px" }}>
                <Clock size={12} />
                Last Heartbeat: {formatDateTime(station.last_heartbeat_at)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
