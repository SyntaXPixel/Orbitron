import React, { useState, useMemo, useEffect } from "react";
import { useOutletContext, Link } from "react-router-dom";
import { PlusCircle, Send, AlertTriangle, CheckCircle, Search } from "lucide-react";
import type { Priority, Session, Snapshot } from "../api/types";
import { useCreateJobMutation } from "../api/mutations";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { ReasonList } from "../components/feedback/ReasonList";
import { EmptyState } from "../components/feedback/EmptyState";
import { ErrorPanel } from "../components/feedback/ErrorPanel";
import { formatBytes } from "../utils/format";
import { formatDateTime, formatUtcDateTime, formatUtcToLocalInput, parseLocalInputToUtc } from "../utils/time";

interface ContextType {
  snapshot?: Snapshot;
  session?: Session;
}

export const RequestsPage: React.FC = () => {
  const { snapshot, session } = useOutletContext<ContextType>();
  const createJobMutation = useCreateJobMutation();

  const satellites = snapshot?.satellites || [];
  const jobs = snapshot?.jobs || [];
  const simulationTime = snapshot?.meta?.simulation_time;
  const user = session?.user;

  // Filter permitted satellites: user's own organization unless network_admin
  const permittedSatellites = useMemo(() => {
    if (!user) return satellites;
    if (user.role === "network_admin") return satellites;
    return satellites.filter((s) => s.owner_org_id === user.organization_id);
  }, [satellites, user]);

  // Form State
  const [satelliteId, setSatelliteId] = useState<string>("");
  const [dataValue, setDataValue] = useState<number>(500);
  const [dataUnit, setDataUnit] = useState<"MB" | "GB">("MB");
  const [deadlineLocal, setDeadlineLocal] = useState<string>("");
  const [priority, setPriority] = useState<Priority>("routine");
  const [allowSplit, setAllowSplit] = useState<boolean>(true);

  const [formError, setFormError] = useState<string | null>(null);
  const [submittedJobId, setSubmittedJobId] = useState<string | null>(null);

  // Filters for table
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");

  // Initialize satelliteId
  useEffect(() => {
    if (!satelliteId && permittedSatellites.length > 0) {
      setSatelliteId(permittedSatellites[0].id);
    }
  }, [permittedSatellites, satelliteId]);

  // Initialize deadline relative to simulation time: default sim_time + 4 hours
  useEffect(() => {
    if (simulationTime && !deadlineLocal) {
      const defaultDate = new Date(new Date(simulationTime).getTime() + 4 * 60 * 60 * 1000);
      setDeadlineLocal(formatUtcToLocalInput(defaultDate.toISOString()));
    }
  }, [simulationTime, deadlineLocal]);

  // Selected satellite info for onboard data check
  const selectedSat = permittedSatellites.find((s) => s.id === satelliteId);
  const requestedBytes = Math.round(dataValue * (dataUnit === "GB" ? 1_000_000_000 : 1_000_000));
  const hasOnboardDataWarning = selectedSat && requestedBytes > selectedSat.onboard_bytes;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmittedJobId(null);

    if (!satelliteId) {
      setFormError("Satellite selection is required.");
      return;
    }

    if (dataValue <= 0 || isNaN(dataValue)) {
      setFormError("Data volume must be a positive number.");
      return;
    }

    if (requestedBytes > 1_000_000_000_000) {
      setFormError("Maximum request volume cannot exceed 1,000,000,000,000 bytes (1 TB).");
      return;
    }

    const deadlineUtc = parseLocalInputToUtc(deadlineLocal);
    if (!deadlineUtc) {
      setFormError("A valid deadline date and time is required.");
      return;
    }

    if (simulationTime) {
      const deadlineMs = new Date(deadlineUtc).getTime();
      const simMs = new Date(simulationTime).getTime();
      if (deadlineMs <= simMs) {
        setFormError("Deadline must be later than the current operational simulation time.");
        return;
      }
    }

    try {
      const created = await createJobMutation.mutateAsync({
        satellite_id: satelliteId,
        data_bytes: requestedBytes,
        deadline_at: deadlineUtc,
        priority,
        allow_split: allowSplit,
      });
      setSubmittedJobId(created.id);
    } catch {
      // Captured by mutation error state
    }
  };

  // Filtered jobs
  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (statusFilter !== "all" && job.status !== statusFilter) return false;
      if (priorityFilter !== "all" && job.priority !== priorityFilter) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return job.id.toLowerCase().includes(term) || job.satellite_id.toLowerCase().includes(term);
      }
      return true;
    });
  }, [jobs, statusFilter, priorityFilter, searchTerm]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Downlink Delivery Requests</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Submit authoritative satellite payload downlink requests with delivery deadlines, priority classes, and multi-contact splitting.
        </p>
      </div>

      {/* Request Creation Form */}
      <div className="panel" style={{ borderLeft: "4px solid var(--color-accent)" }}>
        <h3 style={{ marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <PlusCircle size={18} color="var(--color-accent)" />
          New Downlink Job Request
        </h3>

        {submittedJobId && (
          <div
            style={{
              padding: "10px 14px",
              backgroundColor: "var(--color-success-subtle)",
              border: "1px solid var(--color-success)",
              borderRadius: "var(--radius-control)",
              marginBottom: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "13px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--color-success)" }}>
              <CheckCircle size={16} />
              <span>
                Job <strong>{submittedJobId}</strong> submitted successfully to backend operations.
              </span>
            </div>
            <Link to="/schedule" className="btn btn-ghost" style={{ fontSize: "11px", padding: "4px 8px" }}>
              View Schedule →
            </Link>
          </div>
        )}

        {formError && (
          <div
            style={{
              padding: "10px 14px",
              backgroundColor: "var(--color-danger-subtle)",
              border: "1px solid var(--color-danger)",
              borderRadius: "var(--radius-control)",
              marginBottom: "16px",
              color: "var(--color-danger)",
              fontSize: "13px",
            }}
            role="alert"
          >
            {formError}
          </div>
        )}

        {createJobMutation.error && (
          <ErrorPanel error={createJobMutation.error} title="Submission Rejected by Backend" />
        )}

        <form onSubmit={handleSubmit}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "16px",
            }}
          >
            {/* Satellite select */}
            <div className="form-group">
              <label className="form-label" htmlFor="satellite-select">
                Target Satellite
              </label>
              <select
                id="satellite-select"
                className="form-select"
                value={satelliteId}
                onChange={(e) => setSatelliteId(e.target.value)}
                disabled={createJobMutation.isPending}
                required
              >
                {permittedSatellites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.id}) — Onboard: {formatBytes(s.onboard_bytes)}
                  </option>
                ))}
              </select>
            </div>

            {/* Data Volume */}
            <div className="form-group">
              <label className="form-label" htmlFor="data-volume">
                Payload Volume
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  id="data-volume"
                  type="number"
                  min="1"
                  className="form-input"
                  style={{ flex: 1 }}
                  value={dataValue}
                  onChange={(e) => setDataValue(Number(e.target.value))}
                  disabled={createJobMutation.isPending}
                  required
                />
                <select
                  className="form-select"
                  style={{ width: "80px" }}
                  value={dataUnit}
                  onChange={(e) => setDataUnit(e.target.value as "MB" | "GB")}
                  disabled={createJobMutation.isPending}
                  aria-label="Data unit"
                >
                  <option value="MB">MB</option>
                  <option value="GB">GB</option>
                </select>
              </div>
              <div className="form-help" style={{ marginTop: "4px" }}>
                Canonical: {formatBytes(requestedBytes)}
              </div>
            </div>

            {/* Deadline */}
            <div className="form-group">
              <label className="form-label" htmlFor="deadline-input">
                Delivery Deadline (Operational)
              </label>
              <input
                id="deadline-input"
                type="datetime-local"
                className="form-input"
                value={deadlineLocal}
                onChange={(e) => setDeadlineLocal(e.target.value)}
                disabled={createJobMutation.isPending}
                required
              />
              <div className="form-help" style={{ marginTop: "4px" }}>
                Relative to operational simulation time
              </div>
            </div>

            {/* Priority */}
            <div className="form-group">
              <label className="form-label" htmlFor="priority-select">
                Priority Class
              </label>
              <select
                id="priority-select"
                className="form-select"
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
                disabled={createJobMutation.isPending}
              >
                <option value="routine">Routine</option>
                <option value="high">High</option>
                <option value="emergency">Emergency (Immediate replan)</option>
              </select>
            </div>
          </div>

          {hasOnboardDataWarning && (
            <div
              style={{
                marginTop: "12px",
                padding: "8px 12px",
                backgroundColor: "var(--color-warning-subtle)",
                borderRadius: "var(--radius-control)",
                color: "var(--color-warning)",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <AlertTriangle size={15} />
              <span>
                Requested volume ({formatBytes(requestedBytes)}) exceeds current onboard telemetry (
                {formatBytes(selectedSat?.onboard_bytes)}). Backend validation may reject if data is not generated in time.
              </span>
            </div>
          )}

          {/* Split Checkbox & Submit */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginTop: "20px",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "13px" }}>
              <input
                type="checkbox"
                checked={allowSplit}
                onChange={(e) => setAllowSplit(e.target.checked)}
                disabled={createJobMutation.isPending}
              />
              <span>Allow multi-pass contact splitting across antennas</span>
            </label>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={createJobMutation.isPending}
            >
              <Send size={14} />
              <span>{createJobMutation.isPending ? "Submitting..." : "Submit Downlink Job"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Requests Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <h3>Active & Historical Downlink Jobs ({jobs.length})</h3>

          {/* Table Filters */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <div style={{ position: "relative" }}>
              <input
                type="text"
                className="form-input"
                style={{ paddingLeft: "30px", fontSize: "12px", width: "160px" }}
                placeholder="Search job or sat..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                aria-label="Search jobs"
              />
              <Search
                size={14}
                color="var(--color-text-dim)"
                style={{ position: "absolute", left: "9px", top: "50%", transform: "translateY(-50%)" }}
              />
            </div>

            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ fontSize: "12px", padding: "4px 8px" }}
              aria-label="Filter by job status"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="scheduled">Scheduled</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="blocked">Blocked</option>
              <option value="cancelled">Cancelled</option>
            </select>

            <select
              className="form-select"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              style={{ fontSize: "12px", padding: "4px 8px" }}
              aria-label="Filter by job priority"
            >
              <option value="all">All Priorities</option>
              <option value="routine">Routine</option>
              <option value="high">High</option>
              <option value="emergency">Emergency</option>
            </select>
          </div>
        </div>

        {filteredJobs.length === 0 ? (
          <EmptyState message="No requests match these filters." />
        ) : (
          <div className="table-container">
            <table className="op-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Satellite</th>
                  <th>Priority</th>
                  <th>Requested</th>
                  <th>Delivered</th>
                  <th>Remaining</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>Decisions / Reasons</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <code>{job.id}</code>
                    </td>
                    <td>
                      <strong>{job.satellite_id}</strong>
                    </td>
                    <td>
                      <StatusBadge status={job.priority} />
                    </td>
                    <td>{formatBytes(job.requested_bytes)}</td>
                    <td style={{ color: "var(--color-success)" }}>
                      {formatBytes(job.delivered_bytes)}
                    </td>
                    <td style={{ color: job.remaining_bytes > 0 ? "var(--color-warning)" : "var(--color-text-dim)" }}>
                      {formatBytes(job.remaining_bytes)}
                    </td>
                    <td title={`UTC: ${formatUtcDateTime(job.deadline_at)}`}>
                      {formatDateTime(job.deadline_at)}
                    </td>
                    <td>
                      <StatusBadge status={job.status} />
                    </td>
                    <td>
                      <ReasonList reasons={job.reasons} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
