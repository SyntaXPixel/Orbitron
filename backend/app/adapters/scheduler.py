import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure repository root is in sys.path so sibling packages (scheduler, etc.) can be imported
repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

_override_scheduler = None

def set_scheduler_override(override_module):
    global _override_scheduler
    _override_scheduler = override_module

def get_scheduler_module():
    if _override_scheduler is not None:
        return _override_scheduler
    try:
        import scheduler.api as sched_api
        return sched_api
    except (ImportError, ModuleNotFoundError, AttributeError):
        return None

class SchedulerAdapter:
    @classmethod
    def is_available(cls) -> bool:
        mod = get_scheduler_module()
        if mod is None:
            return False
        return (
            hasattr(mod, "predict_opportunities") and
            hasattr(mod, "solve_schedule") and
            hasattr(mod, "propagate_satellites")
        )

    @classmethod
    def predict_opportunities(cls, catalog: Dict[str, Any], horizon: Dict[str, Any]) -> List[Dict[str, Any]]:
        mod = get_scheduler_module()
        if not cls.is_available():
            raise RuntimeError("SCHEDULER_UNAVAILABLE")
        return mod.predict_opportunities(catalog=catalog, horizon=horizon)

    @classmethod
    def solve_schedule(cls, problem: Dict[str, Any], algorithm: str, time_limit_seconds: int = 5) -> Dict[str, Any]:
        mod = get_scheduler_module()
        if not cls.is_available():
            raise RuntimeError("SCHEDULER_UNAVAILABLE")
        return mod.solve_schedule(problem=problem, algorithm=algorithm, time_limit_seconds=time_limit_seconds)

    @classmethod
    def propagate_satellites(cls, orbit_definitions: List[Dict[str, Any]], at: str) -> List[Dict[str, Any]]:
        mod = get_scheduler_module()
        if not cls.is_available():
            raise RuntimeError("SCHEDULER_UNAVAILABLE")
        return mod.propagate_satellites(orbit_definitions=orbit_definitions, at=at)
