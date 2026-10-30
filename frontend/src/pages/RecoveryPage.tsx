import React, { useState } from "react";
import { useOutletContext, Link } from "react-router-dom";
import { CloudRain, ZapOff, RefreshCcw, LifeBuoy, ArrowRight, ShieldAlert } from "lucide-react";
import type { Operation, Session, Snapshot } from "../api/types";
import { useCreateDisruptionMutation } from "../api/mutations";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { ReasonList } from "../components/feedback/ReasonList";
import { EmptyState } from "../components/feedback/EmptyState";
import { ErrorPanel } from "../components/feedback/ErrorPanel";
import { formatCapacityFactor } from "../utils/format";
import { formatDateTime } from "../utils/time";

interface ContextType {
  snapshot?: Snapshot;
  session?: Session;
  setActiveOperation?: (op: Operation) => void;
}

export const RecoveryPage: React.FC = () => {
  const { snapshot, session, setActiveOperation } = useOutletContext<ContextType>();
  const createDisruptionMutation = useCreateDisruptionMutation();

  const stations = snapshot?.stations || [];
  const events = snapshot?.events || [];
  const scheduleChanges = snapshot?.schedule_changes || [];
  const scheduleVersion = snapshot?.meta?.schedule_version ?? 0;
  const isAdmin = session?.user?.role === "network_admin";

  // Form states
  const [selectedStationId, setSelectedStationId] = useState<string>("");
  const [rainCapacityFactor, setRainCapacityFactor] = useState<number>(0.4);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  React.useEffect(() => {
    if (!selectedStationId && stations.length > 0) {
      setSelectedStationId(stations[0].id);
    }
  }, [stations, selectedStationId]);

  // Handle disruption actions
  const handleApplyDisruption = async (type: "rain" | "station_outage" | "station_recovery") => {
    if (!selectedStationId) return;

    try {
      const op = await createDisruptionMutation.mutateAsync({
        type,
        station_id: selectedStationId,
        capacity_factor: type === "rain" ? rainCapacityFactor : null,
        expected_schedule_version: scheduleVersion,
      });
      if (setActiveOperation) {
        setActiveOperation(op);
      }
    } catch (err) {
      console.error("Disruption submission failed", err);
    }
  };

  const selectedEvent = events.find((e) => e.id === selectedEventId) || events[0] || null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Network Recovery & Operational Disruptions</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Simulate rain attenuation, ground-station outages and recovery events. Inspect automated rescheduling decisions and contact reassignments.
        </p>
      </div>

      {createDisruptionMutation.error && (
        <ErrorPanel
          error={createDisruptionMutation.error}
          title="Disruption Event Failed"
        />
      )}

      {/* Disruption Injection Controls (Admin Only) */}
      <div className="panel" style={{ borderLeft: "4px solid var(--color-warning)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
          <h3 style={{ display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
            <LifeBuoy size={18} color="var(--color-warning)" />
            Disruption Injection Controls
          </h3>

          <Link to="/requests" className="btn btn-ghost" style={{ fontSize: "12px", padding: "4px 10px" }}>
            Submit Emergency Job →
          </Link>
        </div>

        {!isAdmin ? (
          <div style={{ fontSize: "13px", color: "var(--color-text-dim)" }}>
            <ShieldAlert size={16} style={{ display: "inline", verticalAlign: "middle", marginRight: "6px" }} />
            Administrator role required to inject simulated disruption events.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: "16px",
                alignItems: "flex-end",
              }}
            >
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" htmlFor="disruption-station">
                  Target Ground Station
                </label>
                <select
                  id="disruption-station"
                  className="form-select"
                  value={selectedStationId}
                  onChange={(e) => setSelectedStationId(e.target.value)}
                  disabled={createDisruptionMutation.isPending}
                >
                  {stations.map((st) => (
                    <option key={st.id} value={st.id}>
                      {st.name} ({st.id}) — Weather: {formatCapacityFactor(st.weather_capacity_factor)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" htmlFor="rain-factor">
                  Rain Degradation Factor (0 to 1)
                </label>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input
                    id="rain-factor"
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={rainCapacityFactor}
                    onChange={(e) => setRainCapacityFactor(Number(e.target.value))}
                    disabled={createDisruptionMutation.isPending}
                    style={{ flex: 1 }}
                  />
                  <strong style={{ width: "50px", textAlign: "right" }}>
                    {formatCapacityFactor(rainCapacityFactor)}
                  </strong>
                </div>
              </div>
            </div>

            <p style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>
              Note: The weather factor represents the prototype's configured attenuation model. Applying rain or outage initiates authoritative replanning through the scheduler.
            </p>

            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => handleApplyDisruption("rain")}
                disabled={createDisruptionMutation.isPending || !selectedStationId}
                style={{ borderColor: "var(--color-warning)" }}
              >
                <CloudRain size={14} color="var(--color-warning)" />
                <span>Apply Rain Attenuation</span>
              </button>

              <button
                type="button"
                className="btn btn-danger-ghost"
                onClick={() => handleApplyDisruption("station_outage")}
                disabled={createDisruptionMutation.isPending || !selectedStationId}
              >
                <ZapOff size={14} />
                <span>Trigger Station Outage</span>
              </button>

              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => handleApplyDisruption("station_recovery")}
                disabled={createDisruptionMutation.isPending || !selectedStationId}
                style={{ borderColor: "var(--color-success)" }}
              >
                <RefreshCcw size={14} color="var(--color-success)" />
                <span>Restore Station Connectivity</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Disruption Events & Rescheduling Audit */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        {/* Disruption Events List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <h3>Operational Disruptions ({events.length})</h3>

          {events.length === 0 ? (
            <EmptyState message="No disruption events recorded." />
          ) : (
            <div className="table-container">
              <table className="op-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Station</th>
                    <th>Factor</th>
                    <th>Status</th>
                    <th>Occurred</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <tr
                      key={ev.id}
                      onClick={() => setSelectedEventId(ev.id)}
                      style={{
                        backgroundColor:
                          selectedEvent?.id === ev.id ? "var(--color-panel-raised)" : undefined,
                      }}
                    >
                      <td>
                        <strong>{ev.type.replace(/_/g, " ").toUpperCase()}</strong>
                      </td>
                      <td>{ev.station_id}</td>
                      <td>{ev.capacity_factor !== null ? formatCapacityFactor(ev.capacity_factor) : "N/A"}</td>
                      <td>
                        <StatusBadge status={ev.status} />
                      </td>
                      <td>{formatDateTime(ev.occurred_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Schedule Changes (Before / After view) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <h3>Rescheduled Contacts & Allocations ({scheduleChanges.length})</h3>

          {scheduleChanges.length === 0 ? (
            <EmptyState message="No schedule revisions have occurred yet." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {scheduleChanges.map((change) => {
                const isNewAssignment = change.old_contact_ids.length === 0;
                const isUnassigned = change.new_contact_ids.length === 0;

                return (
                  <div key={change.id} className="panel-raised" style={{ padding: "12px", fontSize: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                      <strong style={{ color: "var(--color-pure-white)" }}>
                        Job: <code>{change.job_id}</code>
                      </strong>
                      <span className="badge badge-scheduled">Schedule v{change.schedule_version}</span>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "8px",
                        backgroundColor: "var(--color-panel)",
                        borderRadius: "var(--radius-control)",
                        marginBottom: "8px",
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div className="form-label">Previous</div>
                        <div style={{ color: isNewAssignment ? "var(--color-accent)" : "var(--color-text)" }}>
                          {isNewAssignment ? "New Assignment" : change.old_contact_ids.join(", ")}
                        </div>
                      </div>

                      <ArrowRight size={16} color="var(--color-text-dim)" />

                      <div style={{ flex: 1 }}>
                        <div className="form-label">Updated</div>
                        <div style={{ color: isUnassigned ? "var(--color-danger)" : "var(--color-success)" }}>
                          {isUnassigned ? "Unassigned" : change.new_contact_ids.join(", ")}
                        </div>
                      </div>
                    </div>

                    {change.reasons && change.reasons.length > 0 && (
                      <ReasonList reasons={change.reasons} />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
