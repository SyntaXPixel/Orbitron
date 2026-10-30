import React, { useState, useMemo } from "react";
import { Play, Filter, AlertTriangle, Crosshair } from "lucide-react";
import type { Contact, Job, Opportunity, Station, SnapshotMeta } from "../../api/types";
import { ContactDetailModal } from "./ContactDetailModal";
import { formatTimeOnly } from "../../utils/time";

interface AntennaTimelineProps {
  meta: SnapshotMeta;
  stations: Station[];
  contacts: Contact[];
  jobs: Job[];
  opportunities: Opportunity[];
  onRunScheduler: (expectedScheduleVersion: number) => void;
  isScheduling?: boolean;
  onStartTransfer?: (contactId: string) => void;
  canStartTransfer?: boolean;
}

export const AntennaTimeline: React.FC<AntennaTimelineProps> = ({
  meta,
  stations,
  contacts,
  jobs,
  opportunities,
  onRunScheduler,
  isScheduling = false,
  onStartTransfer,
  canStartTransfer = false,
}) => {
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [satelliteFilter, setSatelliteFilter] = useState<string>("all");
  const [stationFilter, setStationFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [followSimTime, setFollowSimTime] = useState<boolean>(true);

  // Time boundaries in milliseconds
  const windowStart = useMemo(() => new Date(meta.visible_start_at).getTime(), [meta.visible_start_at]);
  const windowEnd = useMemo(() => new Date(meta.visible_end_at).getTime(), [meta.visible_end_at]);
  const totalWindowMs = useMemo(() => Math.max(1, windowEnd - windowStart), [windowEnd, windowStart]);

  const simTimeMs = useMemo(() => new Date(meta.simulation_time).getTime(), [meta.simulation_time]);

  // Unique satellites for filter dropdown
  const uniqueSatellites = useMemo(() => {
    const set = new Set<string>();
    contacts.forEach((c) => set.add(c.satellite_id));
    return Array.from(set).sort();
  }, [contacts]);

  // Filtered contacts
  const filteredContacts = useMemo(() => {
    return contacts.filter((c) => {
      if (satelliteFilter !== "all" && c.satellite_id !== satelliteFilter) return false;
      if (stationFilter !== "all" && c.station_id !== stationFilter) return false;
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      return true;
    });
  }, [contacts, satelliteFilter, stationFilter, statusFilter]);

  // Check for conflicts: overlapping contacts on the same antenna
  const conflictingContactIds = useMemo(() => {
    const conflictSet = new Set<string>();
    const byAntenna: Record<string, Contact[]> = {};

    contacts.forEach((c) => {
      if (!byAntenna[c.antenna_id]) byAntenna[c.antenna_id] = [];
      byAntenna[c.antenna_id].push(c);
    });

    Object.values(byAntenna).forEach((list) => {
      for (let i = 0; i < list.length; i++) {
        for (let j = i + 1; j < list.length; j++) {
          const a = list[i];
          const b = list[j];
          const aStart = new Date(a.setup_start_at || a.start_at).getTime();
          const aEnd = new Date(a.end_at).getTime();
          const bStart = new Date(b.setup_start_at || b.start_at).getTime();
          const bEnd = new Date(b.end_at).getTime();

          if (aStart < bEnd && bStart < aEnd) {
            conflictSet.add(a.id);
            conflictSet.add(b.id);
          }
        }
      }
    });

    return conflictSet;
  }, [contacts]);

  // Flatten rows: Station + Antenna
  const antennaRows = useMemo(() => {
    const rows: { station: Station; antennaId: string; antennaName: string }[] = [];
    stations.forEach((st) => {
      if (stationFilter !== "all" && st.id !== stationFilter) return;
      st.antennas.forEach((ant) => {
        rows.push({
          station: st,
          antennaId: ant.id,
          antennaName: `${st.name} — ${ant.name}`,
        });
      });
    });
    return rows;
  }, [stations, stationFilter]);

  // Generate 6 time ticks across the window
  const timeTicks = useMemo(() => {
    const ticks: { label: string; pct: number }[] = [];
    const count = 6;
    for (let i = 0; i <= count; i++) {
      const pct = (i / count) * 100;
      const t = windowStart + (i / count) * totalWindowMs;
      ticks.push({
        label: formatTimeOnly(new Date(t).toISOString()),
        pct,
      });
    }
    return ticks;
  }, [windowStart, totalWindowMs]);

  // Simulation time position percentage
  const simTimePct = Math.max(0, Math.min(100, ((simTimeMs - windowStart) / totalWindowMs) * 100));

  // Compute block style based on start/end
  const computePosition = (startIso: string, endIso: string) => {
    const s = new Date(startIso).getTime();
    const e = new Date(endIso).getTime();
    const rawLeft = ((s - windowStart) / totalWindowMs) * 100;
    const rawRight = ((e - windowStart) / totalWindowMs) * 100;

    // Clip to viewport without altering timestamps
    const left = Math.max(0, Math.min(100, rawLeft));
    const right = Math.max(0, Math.min(100, rawRight));
    const width = Math.max(0.5, right - left);

    const isVisible = rawRight >= 0 && rawLeft <= 100;
    return { left: `${left}%`, width: `${width}%`, isVisible };
  };

  const getContactColor = (c: Contact) => {
    if (c.status === "active") return "var(--color-active)";
    if (c.status === "completed") return "var(--color-success)";
    if (c.status === "failed" || c.status === "cancelled") return "var(--color-danger)";
    return "var(--color-accent)";
  };

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Timeline Controls & Filters */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Filter size={14} color="var(--color-text-dim)" />
            <span className="form-label" style={{ margin: 0 }}>
              Filters:
            </span>
          </div>

          <select
            className="form-select"
            value={satelliteFilter}
            onChange={(e) => setSatelliteFilter(e.target.value)}
            style={{ fontSize: "12px", padding: "4px 8px" }}
            aria-label="Filter by satellite"
          >
            <option value="all">All Satellites</option>
            {uniqueSatellites.map((sat) => (
              <option key={sat} value={sat}>
                {sat}
              </option>
            ))}
          </select>

          <select
            className="form-select"
            value={stationFilter}
            onChange={(e) => setStationFilter(e.target.value)}
            style={{ fontSize: "12px", padding: "4px 8px" }}
            aria-label="Filter by ground station"
          >
            <option value="all">All Stations</option>
            {stations.map((st) => (
              <option key={st.id} value={st.id}>
                {st.name}
              </option>
            ))}
          </select>

          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ fontSize: "12px", padding: "4px 8px" }}
            aria-label="Filter by contact status"
          >
            <option value="all">All Statuses</option>
            <option value="tentative">Tentative</option>
            <option value="confirmed">Confirmed</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>

          <button
            type="button"
            className={`btn ${followSimTime ? "btn-ghost" : "btn-ghost"}`}
            onClick={() => setFollowSimTime(!followSimTime)}
            style={{
              fontSize: "12px",
              padding: "4px 10px",
              borderColor: followSimTime ? "var(--color-accent)" : "var(--color-border)",
            }}
            title="Keep viewport synced with simulation progress"
          >
            <Crosshair size={13} color={followSimTime ? "var(--color-accent)" : undefined} />
            <span>Follow Sim Time</span>
          </button>
        </div>

        {/* Schedule run button & version badge */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
            Schedule: <strong>v{meta.schedule_version}</strong>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onRunScheduler(meta.schedule_version)}
            disabled={isScheduling || meta.services.scheduler !== "ready"}
            title={
              meta.services.scheduler !== "ready"
                ? "Scheduler service unavailable"
                : "Run optimized scheduling algorithm"
            }
          >
            <Play size={14} />
            <span>{isScheduling ? "Optimizing..." : "Run Scheduler"}</span>
          </button>
        </div>
      </div>

      {conflictingContactIds.size > 0 && (
        <div
          style={{
            padding: "8px 12px",
            backgroundColor: "var(--color-danger-subtle)",
            border: "1px solid var(--color-danger)",
            borderRadius: "var(--radius-control)",
            color: "var(--color-danger)",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <AlertTriangle size={15} />
          <strong>Conflict Detected:</strong>
          <span>
            {conflictingContactIds.size} bookings overlap on the same antenna row. Conflicts are flagged below without alteration.
          </span>
        </div>
      )}

      {/* Timeline Chart Container */}
      <div
        className="timeline-wrapper"
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-control)",
          backgroundColor: "var(--color-panel-raised)",
          overflowX: "auto",
        }}
      >
        <div style={{ minWidth: "750px", position: "relative" }}>
          {/* Header Axis */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "200px 1fr",
              borderBottom: "1px solid var(--color-border)",
              backgroundColor: "var(--color-panel)",
            }}
          >
            <div
              style={{
                padding: "8px 12px",
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--color-text-dim)",
                textTransform: "uppercase",
                borderRight: "1px solid var(--color-border)",
              }}
            >
              Ground Station / Antenna
            </div>
            <div style={{ position: "relative", height: "32px" }}>
              {timeTicks.map((t, i) => (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: `${t.pct}%`,
                    top: "8px",
                    transform: "translateX(-50%)",
                    fontSize: "11px",
                    color: "var(--color-text-muted)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {t.label}
                </div>
              ))}
            </div>
          </div>

          {/* Rows Body */}
          <div style={{ position: "relative" }}>
            {/* Vertical Simulation Time Marker */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `calc(200px + ${simTimePct}% * (100% - 200px) / 100)`,
                width: "2px",
                backgroundColor: "var(--color-active)",
                zIndex: 20,
                pointerEvents: "none",
              }}
              title="Current Simulation Time"
            >
              <div
                style={{
                  position: "absolute",
                  top: "-4px",
                  left: "-4px",
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: "var(--color-active)",
                }}
              />
            </div>

            {/* Grid lines */}
            <div
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: "200px",
                right: 0,
                pointerEvents: "none",
                zIndex: 1,
              }}
            >
              {timeTicks.map((t, i) => (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: `${t.pct}%`,
                    top: 0,
                    bottom: 0,
                    borderLeft: "1px dashed var(--color-border-subtle)",
                  }}
                />
              ))}
            </div>

            {/* Antenna Rows */}
            {antennaRows.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", color: "var(--color-text-dim)" }}>
                No antenna resources available for the selected filters.
              </div>
            ) : (
              antennaRows.map((row) => {
                const rowContacts = filteredContacts.filter((c) => c.antenna_id === row.antennaId);

                return (
                  <div
                    key={row.antennaId}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "200px 1fr",
                      borderBottom: "1px solid var(--color-border-subtle)",
                      minHeight: "44px",
                      position: "relative",
                    }}
                  >
                    {/* Row Label */}
                    <div
                      style={{
                        padding: "8px 12px",
                        fontSize: "12px",
                        color: "var(--color-text)",
                        borderRight: "1px solid var(--color-border)",
                        backgroundColor: "var(--color-panel)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        display: "flex",
                        alignItems: "center",
                      }}
                      title={row.antennaName}
                    >
                      {row.antennaName}
                    </div>

                    {/* Timeline Track */}
                    <div style={{ position: "relative", height: "44px", overflow: "hidden" }}>
                      {/* Contacts on this antenna */}
                      {rowContacts.map((contact) => {
                        const hasConflict = conflictingContactIds.has(contact.id);
                        const contactPos = computePosition(contact.start_at, contact.end_at);

                        // Setup window if exists
                        const hasSetup =
                          contact.setup_start_at &&
                          new Date(contact.setup_start_at).getTime() < new Date(contact.start_at).getTime();
                        const setupPos = hasSetup
                          ? computePosition(contact.setup_start_at, contact.start_at)
                          : null;

                        return (
                          <React.Fragment key={contact.id}>
                            {/* Setup block */}
                            {setupPos && setupPos.isVisible && (
                              <div
                                style={{
                                  position: "absolute",
                                  left: setupPos.left,
                                  width: setupPos.width,
                                  top: "6px",
                                  height: "32px",
                                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                                  border: "1px dashed var(--color-border)",
                                  borderRight: "none",
                                  borderRadius: "4px 0 0 4px",
                                  fontSize: "9px",
                                  color: "var(--color-text-dim)",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  zIndex: 5,
                                  pointerEvents: "none",
                                }}
                              >
                                Setup
                              </div>
                            )}

                            {/* Contact block */}
                            {contactPos.isVisible && (
                              <div
                                onClick={() => setSelectedContact(contact)}
                                style={{
                                  position: "absolute",
                                  left: contactPos.left,
                                  width: contactPos.width,
                                  top: "6px",
                                  height: "32px",
                                  backgroundColor: hasConflict
                                    ? "rgba(255, 127, 138, 0.25)"
                                    : "rgba(139, 128, 255, 0.25)",
                                  border: `1px solid ${
                                    hasConflict ? "var(--color-danger)" : getContactColor(contact)
                                  }`,
                                  borderRadius: hasSetup ? "0 4px 4px 0" : "4px",
                                  padding: "2px 6px",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  gap: "4px",
                                  zIndex: 10,
                                  overflow: "hidden",
                                  transition: "transform 0.1s ease, box-shadow 0.1s ease",
                                }}
                                title={`${contact.satellite_id} (${contact.band}) - Status: ${contact.status}${
                                  hasConflict ? " [CONFLICT]" : ""
                                }`}
                              >
                                <span
                                  style={{
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    color: "var(--color-pure-white)",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {contact.satellite_id}
                                </span>

                                <span
                                  style={{
                                    fontSize: "9px",
                                    backgroundColor: "rgba(0, 0, 0, 0.3)",
                                    padding: "1px 4px",
                                    borderRadius: "2px",
                                    color: "var(--color-text-muted)",
                                  }}
                                >
                                  {contact.band}
                                </span>
                              </div>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Selected Contact Modal */}
      <ContactDetailModal
        contact={selectedContact}
        job={jobs.find((j) => j.id === selectedContact?.job_id)}
        station={stations.find((s) => s.id === selectedContact?.station_id)}
        opportunity={opportunities.find((o) => o.id === selectedContact?.opportunity_id)}
        onClose={() => setSelectedContact(null)}
        onStartTransfer={onStartTransfer}
        canStartTransfer={canStartTransfer}
      />
    </div>
  );
};
