import React from "react";
import type {
  AuthorizationStatus,
  ContactStatus,
  JobStatus,
  OperationStatus,
  Priority,
} from "../../api/types";

interface StatusBadgeProps {
  status:
    | JobStatus
    | ContactStatus
    | Priority
    | AuthorizationStatus
    | OperationStatus
    | "online"
    | "degraded"
    | "offline"
    | "connected"
    | "stale"
    | "disconnected"
    | "fresh"
    | "never_seen"
    | "available"
    | "communicating"
    | "fault"
    | "verified"
    | "delivered"
    | string;
  label?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label }) => {
  const displayLabel = label || status.replace(/_/g, " ");

  let className = "badge badge-muted";

  switch (status) {
    case "active":
    case "communicating":
    case "connected":
    case "fresh":
    case "running":
      className = "badge badge-active";
      break;

    case "completed":
    case "succeeded":
    case "delivered":
    case "verified":
    case "allowed":
    case "online":
    case "available":
      className = "badge badge-success";
      break;

    case "scheduled":
    case "confirmed":
    case "tentative":
      className = "badge badge-scheduled";
      break;

    case "emergency":
    case "fault":
    case "failed":
    case "verification_failed":
    case "denied":
    case "revoked":
    case "offline":
    case "disconnected":
      className = "badge badge-emergency";
      break;

    case "high":
    case "blocked":
    case "degraded":
    case "stale":
    case "expired":
      className = "badge badge-warning";
      break;

    case "routine":
    case "pending":
    case "queued":
    case "cancelled":
    case "never_seen":
    default:
      className = "badge badge-muted";
      break;
  }

  return (
    <span className={className} data-testid={`badge-${status}`}>
      {displayLabel}
    </span>
  );
};
