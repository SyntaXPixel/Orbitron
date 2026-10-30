import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { RecoveryPage } from "../pages/RecoveryPage";
import { mockSnapshot } from "./mocks/fixtures";
import type { DisruptionEvent, ScheduleChange } from "../api/types";

let currentSnapshot = mockSnapshot;

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => ({
      snapshot: currentSnapshot,
      session: { user: { role: "network_admin" } },
      setActiveOperation: vi.fn(),
    }),
  };
});

describe("Recovery & Disruption Events (Plan Section 11.5 & 16)", () => {
  it("renders disruption events and distinguishes rain vs outage", () => {
    const rainEvent: DisruptionEvent = {
      id: "evt-rain-01",
      type: "rain",
      station_id: "gs-b-001",
      capacity_factor: 0.4,
      status: "applied",
      occurred_at: "2026-10-31T08:10:00Z",
      operation_id: "op-rain-01",
      reasons: [],
    };

    currentSnapshot = {
      ...mockSnapshot,
      events: [rainEvent],
    };

    renderWithProviders(<RecoveryPage />);
    expect(screen.getByText("RAIN")).toBeInTheDocument();
    expect(screen.getAllByText("40%").length).toBeGreaterThanOrEqual(1);
  });

  it("renders before and after schedule change states with 'New Assignment' and 'Unassigned'", () => {
    const changes: ScheduleChange[] = [
      {
        id: "chg-01",
        schedule_version: 4,
        job_id: "job-new-101",
        old_contact_ids: [], // No old contact -> New Assignment
        new_contact_ids: ["contact-assigned-01"],
        reasons: [],
        created_at: "2026-10-31T08:12:00Z",
      },
      {
        id: "chg-02",
        schedule_version: 4,
        job_id: "job-dropped-102",
        old_contact_ids: ["contact-old-02"],
        new_contact_ids: [], // No new contact -> Unassigned
        reasons: [
          {
            code: "WEATHER_DEGRADED",
            message: "Link capacity degraded below required threshold.",
            resource_ids: ["gs-b-001"],
          },
        ],
        created_at: "2026-10-31T08:12:00Z",
      },
    ];

    currentSnapshot = {
      ...mockSnapshot,
      schedule_changes: changes,
    };

    renderWithProviders(<RecoveryPage />);
    expect(screen.getByText("New Assignment")).toBeInTheDocument();
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("[WEATHER_DEGRADED]")).toBeInTheDocument();
  });
});
