import React, { useState, useMemo } from "react";
import { useOutletContext } from "react-router-dom";
import {
  Satellite as SatIcon,
  Radio,
  Clock,
  AlertTriangle,
  Database,
  ArrowUpRight,
} from "lucide-react";
import type { Snapshot, Satellite, Station } from "../api/types";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { DetailDrawer } from "../components/tables/DetailDrawer";
import { EmptyState } from "../components/feedback/EmptyState";
import { formatBytes, formatCapacityFactor } from "../utils/format";
import { formatDateTime, isApproachingDeadline } from "../utils/time";

interface ContextType {
  snapshot?: Snapshot;
}

export const OverviewPage: React.FC = () => {
  const { snapshot } = useOutletContext<ContextType>();

  const [selectedItem, setSelectedItem] = useState<{
    item: Satellite | Station | null;
    type: "satellite" | "station" | null;
  }>({ item: null, type: null });

  const satellites = snapshot?.satellites || [];
  const stations = snapshot?.stations || [];
  const jobs = snapshot?.jobs || [];
  const contacts = snapshot?.contacts || [];
  const organizations = snapshot?.organizations || [];
  const simulationTime = snapshot?.meta?.simulation_time;

  // Overview calculated metrics
  const metrics = useMemo(() => {
    const activeContacts = contacts.filter((c) => c.status === "active").length;
    const pendingJobs = jobs.filter((j) => j.status === "pending" || j.status === "scheduled").length;
    const blockedJobs = jobs.filter((j) => j.status === "blocked").length;

    const approachingDeadlineJobs = simulationTime
      ? jobs.filter(
          (j) =>
            j.status !== "completed" &&
            j.status !== "cancelled" &&
            isApproachingDeadline(j.deadline_at, simulationTime)
        ).length
      : 0;

    const totalDeliveredBytes = jobs.reduce((sum, j) => sum + (j.delivered_bytes || 0), 0);

    return {
      satellitesCount: satellites.length,
      stationsCount: stations.length,
      activeContacts,
      pendingJobs,
      blockedJobs,
      approachingDeadlineJobs,
      totalDeliveredBytes,
    };
  }, [satellites, stations, jobs, contacts, simulationTime]);

  const getOrgName = (orgId: string) => {
    return organizations.find((o) => o.id === orgId)?.name || orgId;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Page Title */}
      <div>
        <h2>Fleet & Network Overview</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Authoritative operational telemetry from simulated satellite constellation and ground network.
        </p>
      </div>

      {/* KPI Metric Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "16px",
        }}
      >
        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Registered Fleet</span>
            <SatIcon size={16} color="var(--color-accent)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-pure-white)", marginTop: "8px" }}>
            {metrics.satellitesCount}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Simulated Constellation
          </div>
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Active Contacts</span>
            <Radio size={16} color="var(--color-active)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-active)", marginTop: "8px" }}>
            {metrics.activeContacts}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Currently Downlinking
          </div>
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Pending Requests</span>
            <Clock size={16} color="var(--color-accent)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-pure-white)", marginTop: "8px" }}>
            {metrics.pendingJobs}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Queued or Scheduled
          </div>
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Approaching Deadline</span>
            <AlertTriangle size={16} color="var(--color-warning)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-warning)", marginTop: "8px" }}>
            {metrics.approachingDeadlineJobs}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Due within 30 sim mins
          </div>
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Blocked Requests</span>
            <AlertTriangle size={16} color="var(--color-danger)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-danger)", marginTop: "8px" }}>
            {metrics.blockedJobs}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Requires Rescheduling
          </div>
        </div>

        <div className="panel" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="form-label">Data Delivered</span>
            <Database size={16} color="var(--color-success)" />
          </div>
          <div style={{ fontSize: "28px", fontWeight: 600, color: "var(--color-success)", marginTop: "8px" }}>
            {formatBytes(metrics.totalDeliveredBytes)}
          </div>
          <div style={{ fontSize: "11px", color: "var(--color-text-dim)", marginTop: "4px" }}>
            Across Visible Jobs
          </div>
        </div>
      </div>

      {/* Fleet Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h3>Satellite Fleet Catalogue ({satellites.length})</h3>
          <span style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
            Select a row to inspect orbital telemetry
          </span>
        </div>

        {satellites.length === 0 ? (
          <EmptyState message="No satellite records received yet." />
        ) : (
          <div className="table-container">
            <table className="op-table">
              <thead>
                <tr>
                  <th>Satellite</th>
                  <th>Owner</th>
                  <th>Operational Status</th>
                  <th>Bands</th>
                  <th>Onboard Data</th>
                  <th>Telemetry Freshness</th>
                  <th>Last Observation</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {satellites.map((sat) => (
                  <tr
                    key={sat.id}
                    onClick={() => setSelectedItem({ item: sat, type: "satellite" })}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedItem({ item: sat, type: "satellite" });
                      }
                    }}
                  >
                    <td>
                      <strong>{sat.name}</strong>
                      <div style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>{sat.id}</div>
                    </td>
                    <td>{getOrgName(sat.owner_org_id)}</td>
                    <td>
                      <StatusBadge status={sat.operational_status} />
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                        {sat.supported_bands.map((b) => (
                          <span key={b} className="badge badge-muted" style={{ fontSize: "10px" }}>
                            {b}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{formatBytes(sat.onboard_bytes)}</td>
                    <td>
                      <StatusBadge status={sat.telemetry_status} />
                    </td>
                    <td style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                      {sat.last_telemetry_at ? formatDateTime(sat.last_telemetry_at) : "Never"}
                    </td>
                    <td>
                      <ArrowUpRight size={14} color="var(--color-text-dim)" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Ground Station Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h3>Ground Station Network ({stations.length})</h3>
          <span style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
            Select a row to inspect station antennas & sharing configuration
          </span>
        </div>

        {stations.length === 0 ? (
          <EmptyState message="No ground station records configured yet." />
        ) : (
          <div className="table-container">
            <table className="op-table">
              <thead>
                <tr>
                  <th>Ground Station</th>
                  <th>Operator</th>
                  <th>Operational Status</th>
                  <th>Gateway Connectivity</th>
                  <th>Antennas</th>
                  <th>Weather Factor</th>
                  <th>Sharing Policy</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {stations.map((station) => (
                  <tr
                    key={station.id}
                    onClick={() => setSelectedItem({ item: station, type: "station" })}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedItem({ item: station, type: "station" });
                      }
                    }}
                  >
                    <td>
                      <strong>{station.name}</strong>
                      <div style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>{station.id}</div>
                    </td>
                    <td>{getOrgName(station.owner_org_id)}</td>
                    <td>
                      <StatusBadge status={station.operational_status} />
                    </td>
                    <td>
                      <StatusBadge status={station.connection_status} />
                    </td>
                    <td>{station.antennas.length} Antennas</td>
                    <td>{formatCapacityFactor(station.weather_capacity_factor)}</td>
                    <td>
                      <span className={station.sharing_enabled ? "badge badge-success" : "badge badge-muted"}>
                        {station.sharing_enabled ? "Shared Partner" : "Private"}
                      </span>
                    </td>
                    <td>
                      <ArrowUpRight size={14} color="var(--color-text-dim)" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Drawer */}
      <DetailDrawer
        item={selectedItem.item}
        type={selectedItem.type}
        organizations={organizations}
        onClose={() => setSelectedItem({ item: null, type: null })}
      />
    </div>
  );
};
