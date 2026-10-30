/**
 * Orbitron Time Utilities
 * Handles Server Time vs Simulation Time and UTC/Local presentation.
 */

export function getBrowserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "Local";
  }
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return String(isoString);
  }
}

export function formatUtcDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toISOString().replace(".000Z", "Z");
  } catch {
    return String(isoString);
  }
}

export function formatTimeOnly(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return String(isoString);
  }
}

export function parseLocalInputToUtc(localString: string): string {
  // Input from <input type="datetime-local"> is "YYYY-MM-DDTHH:mm"
  if (!localString) return "";
  const d = new Date(localString);
  if (isNaN(d.getTime())) return "";
  return d.toISOString();
}

export function formatUtcToLocalInput(utcIso: string): string {
  if (!utcIso) return "";
  const d = new Date(utcIso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const mins = pad(d.getMinutes());
  return `${year}-${month}-${day}T${hours}:${mins}`;
}

/**
 * Approaching deadline check per plan Section 11.2:
 * "an incomplete, non-cancelled job with a deadline within the next 30 simulation minutes"
 */
export function isApproachingDeadline(
  deadlineIso: string,
  simulationTimeIso: string,
  thresholdMs = 30 * 60 * 1000
): boolean {
  try {
    const deadline = new Date(deadlineIso).getTime();
    const simTime = new Date(simulationTimeIso).getTime();
    if (isNaN(deadline) || isNaN(simTime)) return false;
    const diff = deadline - simTime;
    return diff > 0 && diff <= thresholdMs;
  } catch {
    return false;
  }
}

export function isPastDeadline(deadlineIso: string, simulationTimeIso: string): boolean {
  try {
    const deadline = new Date(deadlineIso).getTime();
    const simTime = new Date(simulationTimeIso).getTime();
    if (isNaN(deadline) || isNaN(simTime)) return false;
    return deadline <= simTime;
  } catch {
    return false;
  }
}
