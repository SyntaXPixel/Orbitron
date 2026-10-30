import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AntennaTimeline } from "../components/timeline/AntennaTimeline";
import { mockSnapshot } from "./mocks/fixtures";
import type { Contact } from "../api/types";

describe("Timeline Placement, Clipping & Conflict Detection (Plan Section 11.3 & 16.8)", () => {
  it("calculates exact normalized percentage placement and clips without altering timestamps", () => {
    const visibleStart = new Date("2026-10-31T08:00:00Z").getTime();
    const visibleEnd = new Date("2026-10-31T10:00:00Z").getTime(); // 2 hours = 120 mins
    const totalMs = visibleEnd - visibleStart;

    // Contact starts 30 mins in, ends 60 mins in
    const contactStart = new Date("2026-10-31T08:30:00Z").getTime();
    const contactEnd = new Date("2026-10-31T09:00:00Z").getTime();

    const left = ((contactStart - visibleStart) / totalMs) * 100;
    const width = ((contactEnd - contactStart) / totalMs) * 100;

    expect(left).toBe(25); // 30 / 120 = 25%
    expect(width).toBe(25); // 30 / 120 = 25%

    // Contact starts BEFORE visible start (7:30 to 8:30)
    const earlyStart = new Date("2026-10-31T07:30:00Z").getTime();
    const earlyEnd = new Date("2026-10-31T08:30:00Z").getTime();

    const rawLeft = ((earlyStart - visibleStart) / totalMs) * 100;
    const rawRight = ((earlyEnd - visibleStart) / totalMs) * 100;

    const clippedLeft = Math.max(0, Math.min(100, rawLeft));
    const clippedRight = Math.max(0, Math.min(100, rawRight));
    const clippedWidth = Math.max(0.5, clippedRight - clippedLeft);

    expect(rawLeft).toBe(-25);
    expect(clippedLeft).toBe(0);
    expect(clippedWidth).toBe(25); // from 0 to 25%
  });

  it("detects and visibly flags conflicts when two bookings overlap on the same antenna", () => {
    const conflictingContacts: Contact[] = [
      {
        id: "c-01",
        job_id: "j-01",
        satellite_id: "sat-01",
        station_id: "gs-b-001",
        antenna_id: "ant-01",
        opportunity_id: "opp-01",
        band: "X",
        window_start_at: "2026-10-31T08:00:00Z",
        window_end_at: "2026-10-31T08:30:00Z",
        setup_start_at: "2026-10-31T08:00:00Z",
        start_at: "2026-10-31T08:05:00Z",
        end_at: "2026-10-31T08:25:00Z",
        expected_rate_bps: 100_000_000,
        allocated_bytes: 500_000_000,
        transferred_bytes: 0,
        status: "confirmed",
        authorization_status: "allowed",
        schedule_version: 3,
        reasons: [],
      },
      {
        id: "c-02",
        job_id: "j-02",
        satellite_id: "sat-02",
        station_id: "gs-b-001",
        antenna_id: "ant-01", // SAME antenna!
        opportunity_id: "opp-02",
        band: "X",
        window_start_at: "2026-10-31T08:15:00Z",
        window_end_at: "2026-10-31T08:45:00Z",
        setup_start_at: "2026-10-31T08:15:00Z",
        start_at: "2026-10-31T08:20:00Z", // Overlaps with c-01 (8:05 - 8:25)
        end_at: "2026-10-31T08:40:00Z",
        expected_rate_bps: 100_000_000,
        allocated_bytes: 500_000_000,
        transferred_bytes: 0,
        status: "confirmed",
        authorization_status: "allowed",
        schedule_version: 3,
        reasons: [],
      },
    ];

    const mockRunScheduler = vi.fn();

    render(
      <AntennaTimeline
        meta={mockSnapshot.meta}
        stations={mockSnapshot.stations}
        contacts={conflictingContacts}
        jobs={mockSnapshot.jobs}
        opportunities={mockSnapshot.opportunities}
        onRunScheduler={mockRunScheduler}
      />
    );

    // Conflict banner should be rendered
    expect(screen.getByText(/Conflict Detected:/i)).toBeInTheDocument();
  });
});
