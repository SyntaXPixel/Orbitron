import { describe, it, expect } from "vitest";
import {
  formatBytes,
  formatRate,
  formatDuration,
  formatCapacityFactor,
  formatPercentage,
} from "../utils/format";
import {
  isApproachingDeadline,
  isPastDeadline,
  parseLocalInputToUtc,
  formatUtcToLocalInput,
} from "../utils/time";

describe("Formatting and Unit Conversions (Plan Section 5.3)", () => {
  it("formats byte values following the 1 MB = 1,000,000 bytes and 1 GB = 1,000,000,000 bytes standard", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(1_000)).toBe("1 KB");
    expect(formatBytes(1_000_000)).toBe("1 MB");
    expect(formatBytes(500_000_000)).toBe("500 MB");
    expect(formatBytes(1_000_000_000)).toBe("1 GB");
    expect(formatBytes(2_500_000_000)).toBe("2.5 GB");
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
  });

  it("formats data rates where 1 Mbps = 1,000,000 bits per second", () => {
    expect(formatRate(0)).toBe("0 bps");
    expect(formatRate(1_000)).toBe("1 kbps");
    expect(formatRate(1_000_000)).toBe("1 Mbps");
    expect(formatRate(150_000_000)).toBe("150 Mbps");
    expect(formatRate(1_000_000_000)).toBe("1 Gbps");
  });

  it("formats duration into human-readable intervals", () => {
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(120)).toBe("2m 0s");
    expect(formatDuration(3600)).toBe("1h 0m");
    expect(formatDuration(3665)).toBe("1h 1m");
  });

  it("formats weather capacity factor into percentages", () => {
    expect(formatCapacityFactor(1.0)).toBe("100%");
    expect(formatCapacityFactor(0.4)).toBe("40%");
    expect(formatCapacityFactor(0.75)).toBe("75%");
    expect(formatCapacityFactor(null)).toBe("—");
  });

  it("calculates percentage with edge cases safely", () => {
    expect(formatPercentage(50, 100)).toBe("50%");
    expect(formatPercentage(0, 0)).toBe("0%");
    expect(formatPercentage(5, 0)).toBe("0%");
    expect(formatPercentage(200, 100)).toBe("100%");
  });
});

describe("Time & Deadline Conversions (Plan Section 5.4 & 11.2)", () => {
  it("converts local datetime input string to valid UTC ISO 8601 ending in Z", () => {
    const localInput = "2026-10-31T14:30";
    const utcIso = parseLocalInputToUtc(localInput);
    expect(utcIso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    const roundTripped = formatUtcToLocalInput(utcIso);
    expect(roundTripped).toBe(localInput);
  });

  it("correctly flags jobs approaching deadline within 30 simulation minutes", () => {
    const simTime = "2026-10-31T08:00:00Z";

    // 15 simulation minutes in future -> within 30 mins
    const deadlineIn15Min = "2026-10-31T08:15:00Z";
    expect(isApproachingDeadline(deadlineIn15Min, simTime)).toBe(true);

    // Exactly 30 simulation minutes in future -> within 30 mins
    const deadlineIn30Min = "2026-10-31T08:30:00Z";
    expect(isApproachingDeadline(deadlineIn30Min, simTime)).toBe(true);

    // 45 simulation minutes in future -> NOT approaching
    const deadlineIn45Min = "2026-10-31T08:45:00Z";
    expect(isApproachingDeadline(deadlineIn45Min, simTime)).toBe(false);

    // Already passed simulation time -> NOT approaching (it's overdue)
    const passedDeadline = "2026-10-31T07:55:00Z";
    expect(isApproachingDeadline(passedDeadline, simTime)).toBe(false);
    expect(isPastDeadline(passedDeadline, simTime)).toBe(true);
  });
});
