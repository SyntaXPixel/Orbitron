"""Service command dispatcher and handler."""

from __future__ import annotations

import base64
import logging
from typing import Any, Callable, Dict, Optional
from simulation.contracts import CommandAckRequest, ServiceCommand

logger = logging.getLogger(__name__)


class CommandDispatcher:
    """Dispatches and acknowledges service commands received from backend /service/work."""

    def __init__(self):
        self._handlers: Dict[str, Callable[[ServiceCommand], CommandAckRequest]] = {}

    def register_handler(self, kind: str, handler: Callable[[ServiceCommand], CommandAckRequest]) -> None:
        self._handlers[kind] = handler

    def dispatch(self, cmd: ServiceCommand) -> CommandAckRequest:
        """Route command to registered handler."""
        handler = self._handlers.get(cmd.kind)
        if not handler:
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=cmd.scenario_id,
                status="failed",
                result={},
                reasons=[{"code": "UNKNOWN_COMMAND", "message": f"No handler registered for command kind '{cmd.kind}'"}],
            )

        try:
            return handler(cmd)
        except Exception as exc:
            logger.exception("Error executing command %s (%s): %s", cmd.id, cmd.kind, exc)
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=cmd.scenario_id,
                status="failed",
                result={},
                reasons=[{"code": "HANDLER_ERROR", "message": str(exc)}],
            )

