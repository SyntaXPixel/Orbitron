import React from "react";
import { useOutletContext } from "react-router-dom";
import { Play } from "lucide-react";
import type { Operation, Session, Snapshot } from "../api/types";
import { useRunEvaluationMutation } from "../api/mutations";
import { StatusBadge } from "../components/feedback/StatusBadge";
import { ReasonList } from "../components/feedback/ReasonList";
import { EmptyState } from "../components/feedback/EmptyState";
import { ErrorPanel } from "../components/feedback/ErrorPanel";
import { formatBytes } from "../utils/format";

interface ContextType {
  snapshot?: Snapshot;
  session?: Session;
  setActiveOperation?: (op: Operation) => void;
}

export const EvaluationPage: React.FC = () => {
  const { snapshot, session, setActiveOperation } = useOutletContext<ContextType>();
  const runEvaluationMutation = useRunEvaluationMutation();

  const scenario = snapshot?.scenario;
  const evaluations = snapshot?.evaluations || [];
  const latestEvaluation = evaluations[evaluations.length - 1] || null;
  const isAdmin = session?.user?.role === "network_admin";

  const handleRunEvaluation = async () => {
    if (!scenario?.id) return;
    try {
      const op = await runEvaluationMutation.mutateAsync({ scenario_id: scenario.id });
      if (setActiveOperation) setActiveOperation(op);
    } catch (err) {
      console.error("Evaluation run failed", err);
    }
  };

  const fifo = latestEvaluation?.fifo;
  const opt = latestEvaluation?.optimized;

  // Comparison helper that calculates percentage improvement or absolute diff
  const computeImprovement = (fifoVal: number, optVal: number, _higherIsBetter = true) => {
    if (fifoVal === optVal) return "0% (Equal)";
    if (fifoVal === 0) {
      const diff = optVal - fifoVal;
      return `${diff > 0 ? "+" : ""}${diff} (Baseline zero)`;
    }
    const pct = ((optVal - fifoVal) / Math.abs(fifoVal)) * 100;
    const sign = pct > 0 ? "+" : "";
    return `${sign}${pct.toFixed(1)}%`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Scheduler Evaluation & FIFO Benchmark</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Empirical comparison between the proposed multi-antenna constraint scheduler and naive FIFO baseline across identical scenario workloads and disruption traces.
        </p>
      </div>

      {runEvaluationMutation.error && (
        <ErrorPanel error={runEvaluationMutation.error} title="Evaluation Run Failed" />
      )}

      {/* Scenario Overview Card */}
      <div className="panel" style={{ borderLeft: "4px solid var(--color-accent)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h3 style={{ margin: 0 }}>
              Evaluation Scenario: {scenario ? scenario.name : "No Scenario Loaded"}
            </h3>
            <div style={{ fontSize: "12px", color: "var(--color-text-dim)", marginTop: "4px" }}>
              {scenario ? (
                <>
                  Seed: <code>{scenario.seed}</code> | Start: {new Date(scenario.start_at).toLocaleTimeString()} – End:{" "}
                  {new Date(scenario.end_at).toLocaleTimeString()}
                </>
              ) : (
                "Simulation scenario must be configured to run evaluation."
              )}
            </div>
          </div>

          {isAdmin && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRunEvaluation}
              disabled={runEvaluationMutation.isPending || !scenario?.ready_for_evaluation}
              title={
                !scenario?.ready_for_evaluation
                  ? "Scenario is not marked ready for evaluation"
                  : "Run FIFO vs Optimized comparative benchmark"
              }
            >
              <Play size={14} />
              <span>{runEvaluationMutation.isPending ? "Executing Evaluation..." : "Run Evaluation"}</span>
            </button>
          )}
        </div>
      </div>

      {/* Evaluation Results */}
      {!latestEvaluation ? (
        <EmptyState message="Run an evaluation to see measured results." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
              Evaluation: <code>{latestEvaluation.id}</code> | Workload: <code>{latestEvaluation.workload_id}</code> | Event Trace:{" "}
              <code>{latestEvaluation.event_trace_id}</code>
            </div>
            <StatusBadge status={latestEvaluation.status} />
          </div>

          {latestEvaluation.reasons && latestEvaluation.reasons.length > 0 && (
            <ReasonList reasons={latestEvaluation.reasons} />
          )}

          {fifo && opt ? (
            <div className="table-container">
              <table className="op-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>FIFO Baseline</th>
                    <th>Proposed Optimized Scheduler</th>
                    <th>Measured Improvement</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>
                      <strong>Total Requested Data</strong>
                    </td>
                    <td>{formatBytes(fifo.requested_bytes)}</td>
                    <td>{formatBytes(opt.requested_bytes)}</td>
                    <td>Identical Inputs</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Delivered Before Deadlines</strong>
                    </td>
                    <td>{formatBytes(fifo.delivered_before_deadline_bytes)}</td>
                    <td style={{ color: "var(--color-success)", fontWeight: 600 }}>
                      {formatBytes(opt.delivered_before_deadline_bytes)}
                    </td>
                    <td style={{ color: "var(--color-success)", fontWeight: 600 }}>
                      {computeImprovement(fifo.delivered_before_deadline_bytes, opt.delivered_before_deadline_bytes, true)}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Jobs Completed On-Time</strong>
                    </td>
                    <td>
                      {fifo.on_time_jobs} / {fifo.total_jobs} (
                      {fifo.total_jobs > 0 ? `${((fifo.on_time_jobs / fifo.total_jobs) * 100).toFixed(1)}%` : "N/A"})
                    </td>
                    <td style={{ color: "var(--color-pure-white)", fontWeight: 600 }}>
                      {opt.on_time_jobs} / {opt.total_jobs} (
                      {opt.total_jobs > 0 ? `${((opt.on_time_jobs / opt.total_jobs) * 100).toFixed(1)}%` : "N/A"})
                    </td>
                    <td>{computeImprovement(fifo.on_time_jobs, opt.on_time_jobs, true)}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Urgent Jobs Completed On-Time</strong>
                    </td>
                    <td>
                      {fifo.urgent_on_time_jobs} / {fifo.urgent_jobs} (
                      {fifo.urgent_jobs > 0
                        ? `${((fifo.urgent_on_time_jobs / fifo.urgent_jobs) * 100).toFixed(1)}%`
                        : "N/A"})
                    </td>
                    <td style={{ color: "var(--color-pure-white)", fontWeight: 600 }}>
                      {opt.urgent_on_time_jobs} / {opt.urgent_jobs} (
                      {opt.urgent_jobs > 0
                        ? `${((opt.urgent_on_time_jobs / opt.urgent_jobs) * 100).toFixed(1)}%`
                        : "N/A"})
                    </td>
                    <td>
                      {fifo.urgent_jobs > 0
                        ? computeImprovement(fifo.urgent_on_time_jobs, opt.urgent_on_time_jobs, true)
                        : "Not applicable"}
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Resource Conflicts</strong>
                    </td>
                    <td style={{ color: fifo.resource_conflicts > 0 ? "var(--color-danger)" : undefined }}>
                      {fifo.resource_conflicts}
                    </td>
                    <td style={{ color: opt.resource_conflicts > 0 ? "var(--color-danger)" : "var(--color-success)" }}>
                      {opt.resource_conflicts}
                    </td>
                    <td>{computeImprovement(fifo.resource_conflicts, opt.resource_conflicts, false)}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Scheduling Time</strong>
                    </td>
                    <td>{fifo.scheduling_duration_ms} ms</td>
                    <td>{opt.scheduling_duration_ms} ms</td>
                    <td>{computeImprovement(fifo.scheduling_duration_ms, opt.scheduling_duration_ms, false)}</td>
                  </tr>
                  <tr>
                    <td>
                      <strong>Bookings Changed (Rescheduled)</strong>
                    </td>
                    <td>{fifo.bookings_changed}</td>
                    <td>{opt.bookings_changed}</td>
                    <td>{computeImprovement(fifo.bookings_changed, opt.bookings_changed, false)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ color: "var(--color-text-dim)", fontSize: "13px" }}>
              {latestEvaluation.status === "running"
                ? "Evaluation is currently running on the backend..."
                : "Evaluation results incomplete or failed for one algorithm."}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
