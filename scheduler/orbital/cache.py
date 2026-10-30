"""In-memory cache for orbital calculations and Skyfield objects."""

from __future__ import annotations

import threading
from typing import Any
from skyfield.api import EarthSatellite, load
from skyfield.timelib import Timescale


_lock = threading.RLock()
_timescale: Timescale | None = None
_satellite_cache: dict[tuple[str, str, str], EarthSatellite] = {}
_MAX_CACHE_SIZE = 1000


def get_timescale() -> Timescale:
    """Return the cached offline Skyfield TimeScale object (builtin=True, no downloads)."""
    global _timescale
    if _timescale is None:
        with _lock:
            if _timescale is None:
                _timescale = load.timescale(builtin=True)
    return _timescale


def get_cached_satellite(satellite_id: str, line1: str, line2: str) -> EarthSatellite:
    """Return or create a cached Skyfield EarthSatellite object."""
    key = (satellite_id, line1, line2)
    with _lock:
        if key in _satellite_cache:
            return _satellite_cache[key]

        ts = get_timescale()
        sat = EarthSatellite(line1, line2, satellite_id, ts)

        if len(_satellite_cache) >= _MAX_CACHE_SIZE:
            # Evict first 100 items
            keys_to_evict = list(_satellite_cache.keys())[:100]
            for k in keys_to_evict:
                del _satellite_cache[k]

        _satellite_cache[key] = sat
        return sat


def clear_cache() -> None:
    """Clear cached satellites for clean test isolation."""
    with _lock:
        _satellite_cache.clear()
