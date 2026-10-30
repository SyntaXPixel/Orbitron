import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { EvaluationPage } from "../pages/EvaluationPage";
import { mockSnapshot } from "./mocks/fixtures";
import type { Evaluation } from "../api/types";

// Mock router outlet context
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => ({
      snapshot: testSnapshot,
      session: { user: { role: "network_admin" } },
      setActiveOperation: vi.fn(),
    }),
  };
});

let testSnapshot = mockSnapshot;

describe("Evaluation Benchmark & Zero Baseline Handling (Plan Section 11.7 & 16.11)", () => {
  it("handles a zero baseline cleanly without producing Infinity or NaN", () => {
    const evalWithZeroBaseline: Evaluation = {
      id: "eval-zero-base",
      scenario_id: "scenario-001",
      workload_id: "wl-01",
      event_trace_id: "evt-01",
      status: "completed",
      fifo: {
        requested_bytes: 1_000_000_000,
        delivered_before_deadline_bytes: 0, // Zero baseline
        total_jobs: 5,
        on_time_jobs: 0, // Zero baseline
        urgent_jobs: 2,
        urgent_on_time_jobs: 0, // Zero baseline
        resource_conflicts: 3,
        scheduling_duration_ms: 10,
        bookings_changed: 0,
      },
      optimized: {
        requested_bytes: 1_000_000_000,
        delivered_before_deadline_bytes: 800_000_000,
        total_jobs: 5,
        on_time_jobs: 4,
        urgent_jobs: 2,
        urgent_on_time_jobs: 2,
        resource_conflicts: 0,
        scheduling_duration_ms: 45,
        bookings_changed: 2,
      },
      reasons: [],
    };

    testSnapshot = {
      ...mockSnapshot,
      evaluations: [evalWithZeroBaseline],
    };

    renderWithProviders(<EvaluationPage />);

    // Should display the metrics table
    expect(screen.getByText(/Scheduler Evaluation & FIFO Benchmark/i)).toBeInTheDocument();
    expect(screen.getByText("Total Requested Data")).toBeInTheDocument();

    // Zero baseline metrics should not contain Infinity or NaN
    const tableText = screen.getByRole("table").textContent || "";
    expect(tableText).not.toContain("Infinity");
    expect(tableText).not.toContain("NaN");
    expect(tableText).toContain("Baseline zero");
  });

  it("displays empty state when no evaluation has been run", () => {
    testSnapshot = {
      ...mockSnapshot,
      evaluations: [],
    };

    renderWithProviders(<EvaluationPage />);
    expect(screen.getByText(/Run an evaluation to see measured results./i)).toBeInTheDocument();
  });
});
