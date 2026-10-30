"""Checkpoint persistence and reconciliation with authoritative backend state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ControllerCheckpoint(BaseModel):
    """Local persisted state for fleet controller."""
    scenario_id: str
    last_tick_event_id: Optional[str] = None
    last_tick_sequence: int = 0
    last_tick_simulation_time: Optional[str] = None
    satellite_generation_counters: Dict[str, int] = Field(default_factory=dict)
    contact_progress_counters: Dict[str, int] = Field(default_factory=dict)
    station_sequences: Dict[str, int] = Field(default_factory=dict)
    pending_uncertain_messages: List[Dict[str, Any]] = Field(default_factory=list)


class CheckpointManager:
    """Manages saving, restoring, and reconciling local simulation checkpoints."""

    def __init__(self, checkpoints_dir: Path):
        self.checkpoints_dir: Path = checkpoints_dir
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, scenario_id: str) -> Path:
        return self.checkpoints_dir / f"{scenario_id}.json"

    def save(self, checkpoint: ControllerCheckpoint) -> None:
        """Persist checkpoint atomically to disk."""
        path = self._file_path(checkpoint.scenario_id)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)

    def load(self, scenario_id: str) -> Optional[ControllerCheckpoint]:
        """Load checkpoint if existing for this scenario."""
        path = self._file_path(scenario_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ControllerCheckpoint(**data)
        except Exception:
            return None

    def reconcile(
        self,
        local_checkpoint: ControllerCheckpoint,
        backend_checkpoints: Dict[str, Any],
    ) -> ControllerCheckpoint:
        """Reconcile local state against authoritative backend checkpoints."""
        # Align with backend accepted generation counters if backend has higher/authoritative
        bg_counters = backend_checkpoints.get("satellite_generation_counters", {})
        for sat_id, bg_val in bg_counters.items():
            current_val = local_checkpoint.satellite_generation_counters.get(sat_id, 0)
            local_checkpoint.satellite_generation_counters[sat_id] = max(current_val, bg_val)

        # Restore last accepted tick sequence
        bg_seq = backend_checkpoints.get("last_tick_sequence")
        if bg_seq is not None:
            local_checkpoint.last_tick_sequence = max(local_checkpoint.last_tick_sequence, bg_seq)

        bg_sim_time = backend_checkpoints.get("last_tick_simulation_time")
        if bg_sim_time:
            local_checkpoint.last_tick_simulation_time = bg_sim_time

        return local_checkpoint
