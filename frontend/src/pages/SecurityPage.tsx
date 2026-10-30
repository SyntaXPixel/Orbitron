import React, { useState } from "react";
import { useOutletContext } from "react-router-dom";
import {
  ShieldCheck,
  Play,
  Lock,
  KeyRound,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { Operation, Session, Snapshot } from "../api/types";
import { useCreateTransferMutation, useRunSecurityCheckMutation } from "../api/mutations";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { ReasonList } from "../components/feedback/ReasonList";
import { EmptyState } from "../components/feedback/EmptyState";
import { ErrorPanel } from "../components/feedback/ErrorPanel";
import { formatBytes, formatPercentage } from "../utils/format";

interface ContextType {
  snapshot?: Snapshot;
  session?: Session;
  setActiveOperation?: (op: Operation) => void;
}

export const SecurityPage: React.FC = () => {
  const { snapshot, session, setActiveOperation } = useOutletContext<ContextType>();
  const createTransferMutation = useCreateTransferMutation();
  const runSecurityCheckMutation = useRunSecurityCheckMutation();

  const transfers = snapshot?.transfers || [];
  const securityChecks = snapshot?.security_checks || [];
  const contacts = snapshot?.contacts || [];
  const organizations = snapshot?.organizations || [];
  const isAdmin = session?.user?.role === "network_admin";

  const [selectedContactId, setSelectedContactId] = useState<string>("");
  const [selectedTestCase, setSelectedTestCase] = useState<
    "expired_authorization" | "wrong_station" | "tampered_payload"
  >("tampered_payload");

  // Eligible contacts for transfer (confirmed contacts)
  const eligibleContacts = contacts.filter((c) => c.status === "confirmed" || c.status === "active");

  React.useEffect(() => {
    if (!selectedContactId && eligibleContacts.length > 0) {
      setSelectedContactId(eligibleContacts[0].id);
    }
  }, [eligibleContacts, selectedContactId]);

  const handleStartTransfer = async () => {
    if (!selectedContactId) return;
    try {
      const op = await createTransferMutation.mutateAsync({ contact_id: selectedContactId });
      if (setActiveOperation) setActiveOperation(op);
    } catch (err) {
      console.error("Start transfer failed", err);
    }
  };

  const handleRunSecurityCheck = async () => {
    if (!selectedContactId) return;
    try {
      const op = await runSecurityCheckMutation.mutateAsync({
        test_case: selectedTestCase,
        contact_id: selectedContactId,
      });
      if (setActiveOperation) setActiveOperation(op);
    } catch (err) {
      console.error("Security check failed", err);
    }
  };

  const getOrgName = (orgId: string) => organizations.find((o) => o.id === orgId)?.name || orgId;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Secure Ground-Station Sharing & Evidence</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          End-to-end encrypted payload transfers through untrusted partner gateways. Cryptographic verification of plaintext hashes and scoped contact authorization.
        </p>
      </div>

      {createTransferMutation.error && (
        <ErrorPanel error={createTransferMutation.error} title="Transfer Rejection" />
      )}

      {runSecurityCheckMutation.error && (
        <ErrorPanel error={runSecurityCheckMutation.error} title="Security Check Failed" />
      )}

      {/* Security Demonstration Controls */}
      <div className="panel" style={{ borderLeft: "4px solid var(--color-success)" }}>
        <h3 style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
          <ShieldCheck size={18} color="var(--color-success)" />
          Encrypted Transfer & Verification Controls
        </h3>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "16px",
            alignItems: "flex-end",
          }}
        >
          {/* Contact select */}
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label" htmlFor="contact-select">
              Select Scheduled Contact
            </label>
            <select
              id="contact-select"
              className="form-select"
              value={selectedContactId}
              onChange={(e) => setSelectedContactId(e.target.value)}
              disabled={createTransferMutation.isPending || runSecurityCheckMutation.isPending}
            >
              {eligibleContacts.length === 0 ? (
                <option value="">No confirmed contacts available</option>
              ) : (
                eligibleContacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} — Sat: {c.satellite_id} @ {c.station_id} ({c.band})
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Test Case Select (Admin) */}
          {isAdmin && (
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label" htmlFor="test-case-select">
                Security Demonstration Check
              </label>
              <select
                id="test-case-select"
                className="form-select"
                value={selectedTestCase}
                onChange={(e) => setSelectedTestCase(e.target.value as any)}
                disabled={runSecurityCheckMutation.isPending}
              >
                <option value="tampered_payload">Modified Encrypted Payload (Integrity Failure)</option>
                <option value="expired_authorization">Expired Authorization Token (Unauthorized)</option>
                <option value="wrong_station">Wrong Ground Station Scope (Scope Mismatch)</option>
              </select>
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleStartTransfer}
              disabled={createTransferMutation.isPending || !selectedContactId}
            >
              <Lock size={14} />
              <span>{createTransferMutation.isPending ? "Starting..." : "Start Secure Transfer"}</span>
            </button>

            {isAdmin && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleRunSecurityCheck}
                disabled={runSecurityCheckMutation.isPending || !selectedContactId}
              >
                <Play size={14} />
                <span>{runSecurityCheckMutation.isPending ? "Running Check..." : "Run Security Check"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Security architecture notice */}
        <div
          style={{
            marginTop: "16px",
            padding: "10px 14px",
            backgroundColor: "var(--color-panel-raised)",
            borderRadius: "var(--radius-control)",
            fontSize: "12px",
            color: "var(--color-text-muted)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <KeyRound size={16} color="var(--color-accent)" />
          <span>
            <strong>Architecture Notice:</strong> Demo configuration: partner gateway was not provisioned a payload decryption key. The browser only inspects verified metadata and does not receive decryption keys or raw payload bytes.
          </span>
        </div>
      </div>

      {/* Active & Historical Transfers Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <h3>Transfers & Delivery Evidence ({transfers.length})</h3>

        {transfers.length === 0 ? (
          <EmptyState message="No secure transfer has been started." />
        ) : (
          <div className="table-container">
            <table className="op-table">
              <thead>
                <tr>
                  <th>Transfer ID</th>
                  <th>Contact</th>
                  <th>Owner Org</th>
                  <th>Partner Station</th>
                  <th>Progress</th>
                  <th>Transfer State</th>
                  <th>Integrity</th>
                  <th>Owner Decryption</th>
                  <th>Hashes</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((tx) => (
                  <tr key={tx.id}>
                    <td>
                      <code>{tx.id}</code>
                    </td>
                    <td>
                      <code>{tx.contact_id}</code>
                    </td>
                    <td>{getOrgName(tx.owner_org_id)}</td>
                    <td>{tx.partner_station_id}</td>
                    <td>
                      <div style={{ fontSize: "11px" }}>
                        {formatBytes(tx.forwarded_bytes)} / {formatBytes(tx.total_bytes)} (
                        {formatPercentage(tx.forwarded_bytes, tx.total_bytes)})
                      </div>
                      <div
                        style={{
                          width: "80px",
                          height: "4px",
                          backgroundColor: "var(--color-border)",
                          borderRadius: "2px",
                          overflow: "hidden",
                          marginTop: "4px",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${(tx.forwarded_bytes / (tx.total_bytes || 1)) * 100}%`,
                            backgroundColor:
                              tx.status === "failed" ? "var(--color-danger)" : "var(--color-success)",
                          }}
                        />
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={tx.status} />
                    </td>
                    <td>
                      <StatusBadge status={tx.integrity_status} />
                    </td>
                    <td>
                      <StatusBadge status={tx.owner_decryption_status} />
                    </td>
                    <td>
                      <div style={{ fontSize: "10px", fontFamily: "var(--font-mono)" }}>
                        {tx.ciphertext_sha256 ? (
                          <div title={`Ciphertext: ${tx.ciphertext_sha256}`}>
                            CT: {tx.ciphertext_sha256.slice(0, 8)}...
                          </div>
                        ) : (
                          <span style={{ color: "var(--color-text-dim)" }}>No hash</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Security Demonstration Checks Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <h3>Demonstration Security Checks ({securityChecks.length})</h3>

        {securityChecks.length === 0 ? (
          <EmptyState message="No security test cases executed yet." />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
            {securityChecks.map((check) => {
              const isPassed = check.passed === true;
              const isFailed = check.passed === false;

              return (
                <div
                  key={check.id}
                  className="panel-raised"
                  style={{
                    borderLeft: `4px solid ${
                      isPassed ? "var(--color-success)" : isFailed ? "var(--color-danger)" : "var(--color-border)"
                    }`,
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <strong style={{ fontSize: "13px", color: "var(--color-pure-white)" }}>
                      Test Case: {check.test_case.replace(/_/g, " ").toUpperCase()}
                    </strong>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {isPassed && (
                        <span className="badge badge-success">
                          <CheckCircle2 size={12} /> Expected Rejection Verified
                        </span>
                      )}
                      {isFailed && (
                        <span className="badge badge-emergency">
                          <XCircle size={12} /> Check Failed
                        </span>
                      )}
                      {check.passed === null && <StatusBadge status={check.status} />}
                    </div>
                  </div>

                  <div style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                    <div>
                      <strong>Expected:</strong> {check.expected_outcome}
                    </div>
                    {check.observed_outcome && (
                      <div style={{ marginTop: "4px" }}>
                        <strong>Observed:</strong> {check.observed_outcome}
                      </div>
                    )}
                  </div>

                  {check.reasons && check.reasons.length > 0 && <ReasonList reasons={check.reasons} />}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
