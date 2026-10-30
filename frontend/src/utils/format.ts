/**
 * Unit conversions per Orbitron plan:
 * 1 MB = 1,000,000 bytes
 * 1 GB = 1,000,000,000 bytes
 * 1 Mbps = 1,000,000 bits per second
 */

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return "—";
  if (bytes < 0) return "0 B";

  if (bytes >= 1_000_000_000) {
    const gb = bytes / 1_000_000_000;
    return `${Number(gb.toFixed(2))} GB`;
  }
  if (bytes >= 1_000_000) {
    const mb = bytes / 1_000_000;
    return `${Number(mb.toFixed(2))} MB`;
  }
  if (bytes >= 1_000) {
    const kb = bytes / 1_000;
    return `${Number(kb.toFixed(2))} KB`;
  }
  return `${bytes} B`;
}

export function formatRate(bps: number | null | undefined): string {
  if (bps === null || bps === undefined || isNaN(bps)) return "—";
  if (bps < 0) return "0 bps";

  if (bps >= 1_000_000_000) {
    const gbps = bps / 1_000_000_000;
    return `${Number(gbps.toFixed(2))} Gbps`;
  }
  if (bps >= 1_000_000) {
    const mbps = bps / 1_000_000;
    return `${Number(mbps.toFixed(2))} Mbps`;
  }
  if (bps >= 1_000) {
    const kbps = bps / 1_000;
    return `${Number(kbps.toFixed(2))} kbps`;
  }
  return `${bps} bps`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "—";
  const abs = Math.abs(seconds);
  const m = Math.floor(abs / 60);
  const s = Math.floor(abs % 60);
  if (m === 0) return `${s}s`;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}

export function formatCapacityFactor(factor: number | null | undefined): string {
  if (factor === null || factor === undefined || isNaN(factor)) return "—";
  return `${Math.round(factor * 100)}%`;
}

export function formatPercentage(part: number, total: number): string {
  if (!total || total <= 0 || isNaN(part) || isNaN(total)) return "0%";
  const p = Math.min(100, Math.max(0, (part / total) * 100));
  return `${Number(p.toFixed(1))}%`;
}
