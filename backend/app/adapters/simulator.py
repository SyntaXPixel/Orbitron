from typing import Dict, Any, Optional

class SimulatorAdapter:
    @classmethod
    def get_status(cls, last_heartbeat_at_iso: Optional[str]) -> str:
        if not last_heartbeat_at_iso:
            return "disconnected"
        return "connected"
