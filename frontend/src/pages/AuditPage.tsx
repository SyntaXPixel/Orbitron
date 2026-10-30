import React, { useState, useMemo } from "react";
import { useOutletContext } from "react-router-dom";
import { Search } from "lucide-react";
import type { Snapshot } from "../api/types";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { EmptyState } from "../components/feedback/EmptyState";
import { formatDateTime } from "../utils/time";

interface ContextType {
  snapshot?: Snapshot;
}

export const AuditPage: React.FC = () => {
  const { snapshot } = useOutletContext<ContextType>();
  const auditEntries = snapshot?.audit || [];

  const [searchTerm, setSearchTerm] = useState<string>("");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");
  const [resourceFilter, setResourceFilter] = useState<string>("all");

  // Distinct resource types
  const resourceTypes = useMemo(() => {
    const set = new Set<string>();
    auditEntries.forEach((a) => {
      if (a.resource_type) set.add(a.resource_type);
    });
    return Array.from(set).sort();
  }, [auditEntries]);

  // Filtered entries
  const filteredEntries = useMemo(() => {
    return auditEntries.filter((item) => {
      if (outcomeFilter !== "all" && item.outcome !== outcomeFilter) return false;
      if (resourceFilter !== "all" && item.resource_type !== resourceFilter) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return (
          item.action.toLowerCase().includes(term) ||
          item.actor_name.toLowerCase().includes(term) ||
          item.message.toLowerCase().includes(term) ||
          (item.resource_id && item.resource_id.toLowerCase().includes(term))
        );
      }
      return true;
    });
  }, [auditEntries, outcomeFilter, resourceFilter, searchTerm]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Operational Audit & Security Log</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Immutable log of operational decisions, scheduling runs, security validations, and administrative actions.
        </p>
      </div>

      {/* Filters */}
      <div
        className="panel"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          padding: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: "30px", fontSize: "13px", width: "220px" }}
              placeholder="Search actions, actors..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="Search audit entries"
            />
            <Search
              size={15}
              color="var(--color-text-dim)"
              style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)" }}
            />
          </div>

          <select
            className="form-select"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            style={{ fontSize: "12px", padding: "6px 10px" }}
            aria-label="Filter by outcome"
          >
            <option value="all">All Outcomes</option>
            <option value="allowed">Allowed</option>
            <option value="denied">Denied</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
          </select>

          <select
            className="form-select"
            value={resourceFilter}
            onChange={(e) => setResourceFilter(e.target.value)}
            style={{ fontSize: "12px", padding: "6px 10px" }}
            aria-label="Filter by resource type"
          >
            <option value="all">All Resource Types</option>
            {resourceTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div style={{ fontSize: "12px", color: "var(--color-text-dim)" }}>
          Showing {filteredEntries.length} of {auditEntries.length} entries
        </div>
      </div>

      {/* Audit Table */}
      {filteredEntries.length === 0 ? (
        <EmptyState message="No audit records match these filters." />
      ) : (
        <div className="table-container">
          <table className="op-table">
            <thead>
              <tr>
                <th>Timestamp & Clock</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Outcome</th>
                <th>Decision Message</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <div>{formatDateTime(entry.timestamp)}</div>
                    <div style={{ fontSize: "10px", color: "var(--color-text-dim)" }}>
                      Clock: <code>{entry.clock_basis}</code>
                    </div>
                  </td>
                  <td>
                    <strong>{entry.actor_name}</strong>
                  </td>
                  <td>
                    <code>{entry.action}</code>
                  </td>
                  <td>
                    <span>{entry.resource_type}</span>
                    {entry.resource_id && (
                      <div style={{ fontSize: "11px", color: "var(--color-text-dim)" }}>
                        ID: <code>{entry.resource_id}</code>
                      </div>
                    )}
                  </td>
                  <td>
                    <StatusBadge status={entry.outcome} />
                  </td>
                  <td style={{ color: "var(--color-text)", maxWidth: "340px", wordBreak: "break-word" }}>
                    {entry.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
