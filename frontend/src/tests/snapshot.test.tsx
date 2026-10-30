import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { OverviewPage } from "../pages/OverviewPage";
import { mockSnapshot } from "./mocks/fixtures";
import type { Satellite, Snapshot } from "../api/types";

let currentSnapshot: Snapshot = mockSnapshot;

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => ({
      snapshot: currentSnapshot,
    }),
  };
});

describe("Snapshot Data & Fleet Scalability (Plan Section 15 F20 & 16.9)", () => {
  it("handles empty satellite and station collections with meaningful messages", () => {
    currentSnapshot = {
      ...mockSnapshot,
      satellites: [],
      stations: [],
      jobs: [],
      contacts: [],
    };

    render(<OverviewPage />);
    expect(screen.getByText("No satellite records received yet.")).toBeInTheDocument();
    expect(screen.getByText("No ground station records configured yet.")).toBeInTheDocument();
  });

  it("renders 120 satellites cleanly in fleet catalogue (Acceptance Scenario F20)", () => {
    const fleet120: Satellite[] = Array.from({ length: 120 }, (_, i) => ({
      id: `sat-fleet-${String(i).padStart(3, "0")}`,
      name: `Constellation Node ${i + 1}`,
      owner_org_id: "org-fleet-a",
      supported_bands: ["X"],
      max_downlink_rate_bps: 100_000_000,
      max_parallel_contacts: 1,
      onboard_bytes: 1_000_000_000,
      operational_status: i % 10 === 0 ? "fault" : "available",
      telemetry_status: i % 5 === 0 ? "stale" : "fresh",
      position: {
        latitude_deg: (i * 3) % 90,
        longitude_deg: (i * 7) % 180,
        altitude_km: 500 + i,
        observed_at: "2026-10-31T08:00:00Z",
      },
      last_telemetry_at: "2026-10-31T08:00:00Z",
      source: "simulated",
      orbit_source: "synthetic",
      orbit_epoch_at: null,
    }));

    currentSnapshot = {
      ...mockSnapshot,
      satellites: fleet120,
    };

    render(<OverviewPage />);
    expect(screen.getByText("Satellite Fleet Catalogue (120)")).toBeInTheDocument();
    expect(screen.getByText("Constellation Node 1")).toBeInTheDocument();
    expect(screen.getByText("Constellation Node 120")).toBeInTheDocument();
  });

  it("handles missing position telemetry without assuming 0, 0 coordinates", () => {
    const satNoTelemetry: Satellite = {
      id: "sat-no-pos",
      name: "Dark Node 99",
      owner_org_id: "org-fleet-a",
      supported_bands: ["S"],
      max_downlink_rate_bps: 50_000_000,
      max_parallel_contacts: 1,
      onboard_bytes: 500_000_000,
      operational_status: "available",
      telemetry_status: "never_seen",
      position: null, // No position!
      last_telemetry_at: null,
      source: "simulated",
      orbit_source: "synthetic",
      orbit_epoch_at: null,
    };

    currentSnapshot = {
      ...mockSnapshot,
      satellites: [satNoTelemetry],
    };

    render(<OverviewPage />);
    expect(screen.getByText("Dark Node 99")).toBeInTheDocument();
    expect(screen.getByText("Never")).toBeInTheDocument();
  });
});
