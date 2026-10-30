import sys
from pathlib import Path
from typing import Dict, Any, Optional

repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

_override_security = None

def set_security_override(override_module):
    global _override_security
    _override_security = override_module

def get_security_module():
    if _override_security is not None:
        return _override_security
    try:
        import security.api as sec_api
        return sec_api
    except (ImportError, ModuleNotFoundError, AttributeError):
        return None

class SecurityAdapter:
    @classmethod
    def is_available(cls) -> bool:
        mod = get_security_module()
        if mod is None:
            return False
        return hasattr(mod, "capabilities") and hasattr(mod, "evaluate_contact")

    @classmethod
    def capabilities(cls) -> Dict[str, Any]:
        mod = get_security_module()
        if not cls.is_available():
            raise RuntimeError("SECURITY_UNAVAILABLE")
        return mod.capabilities()

    @classmethod
    def evaluate_contact(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        mod = get_security_module()
        if not cls.is_available():
            raise RuntimeError("SECURITY_UNAVAILABLE")
        return mod.evaluate_contact(context=context)
