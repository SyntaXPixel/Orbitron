"""Metrics computation for evaluation replay matching public SchedulerMetrics."""

from __future__ import annotations

from typing import Any, Dict, List
from simulation.contracts import SchedulerMetrics
from simulation.model.progress import parse_utc


def compute_evaluation_metrics(
    all_jobs: List[Dict[str, Any]],
    delivery_events: List[Dict[str, Any]],
    resource_conflicts: int,
    scheduling_duration_ms: int,
    bookings_changed: int,
) -> SchedulerMetrics:
    """Calculate exact SchedulerMetrics from evaluation replay execution records."""
    requested_bytes = sum(j.get("data_bytes", 0) for j in all_jobs)

    # Track delivered bytes before deadline for each job
    delivered_before_deadline_map: Dict[str, int] = {j["id"]: 0 for j in all_jobs}

    for dev in delivery_events:
        job_id = dev["job_id"]
        delivered_at_dt = parse_utc(dev["delivered_at"])
        deadline_dt = parse_utc(dev["deadline_at"])

        if delivered_at_dt <= deadline_dt:
            delivered_before_deadline_map[job_id] = (
                delivered_before_deadline_map.get(job_id, 0) + dev.get("bytes_transferred", 0)
            )

    delivered_before_deadline_bytes = sum(delivered_before_deadline_map.values())
    total_jobs = len(all_jobs)

    on_time_jobs = 0
    urgent_jobs = 0
    urgent_on_time_jobs = 0

    for job in all_jobs:
        job_id = job["id"]
        is_urgent = job.get("priority") == "emergency"
        if is_urgent:
            urgent_jobs += 1

        is_completed_on_time = delivered_before_deadline_map.get(job_id, 0) >= job.get("data_bytes", 0)
        if is_completed_on_time:
            on_time_jobs += 1
            if is_urgent:
                urgent_on_time_jobs += 1

    return SchedulerMetrics(
        requested_bytes=requested_bytes,
        delivered_before_deadline_bytes=delivered_before_deadline_bytes,
        total_jobs=total_jobs,
        on_time_jobs=on_time_jobs,
        urgent_jobs=urgent_jobs,
        urgent_on_time_jobs=urgent_on_time_jobs,
        resource_conflicts=resource_conflicts,
        scheduling_duration_ms=scheduling_duration_ms,
        bookings_changed=bookings_changed,
    )

