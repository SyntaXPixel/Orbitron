"""CLI for validating orbital catalogue definitions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scheduler.orbital.propagation import propagate_satellites
from scheduler.orbital.tle import validate_orbit_definition


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate orbital catalogue fixture")
    parser.add_argument(
        "--catalog",
        "-c",
        required=True,
        type=Path,
        help="Path to catalogue JSON file",
    )
    parser.add_argument(
        "--at",
        type=str,
        help="Optional ISO timestamp to test satellite propagation",
    )

    args = parser.parse_args()

    try:
        with open(args.catalog, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Error reading catalog file: {exc}\n")
        return 1

    satellites = catalog.get("satellites", [])
    stations = catalog.get("stations", [])
    orbit_definitions = catalog.get("orbit_definitions", [])

    print(f"Catalog contains {len(satellites)} satellites, {len(stations)} stations, {len(orbit_definitions)} orbit definitions.")

    # Validate each orbit definition
    orbit_errors = 0
    for idx, odef in enumerate(orbit_definitions):
        sat_id = odef.get("satellite_id", f"index-{idx}")
        try:
            validate_orbit_definition(odef)
            print(f"  [OK] Satellite '{sat_id}' orbit definition validated.")
        except Exception as exc:
            sys.stderr.write(f"  [ERROR] Satellite '{sat_id}' invalid: {exc}\n")
            orbit_errors += 1

    if orbit_errors > 0:
        sys.stderr.write(f"Validation failed with {orbit_errors} orbital errors.\n")
        return 2

    if args.at:
        try:
            positions = propagate_satellites(orbit_definitions, args.at)
            print(f"Propagated {len(positions)} satellites at {args.at}:")
            for pos in positions:
                p = pos["position"]
                print(f"  {pos['satellite_id']}: lat={p['latitude_deg']} lon={p['longitude_deg']} alt={p['altitude_km']} km")
        except Exception as exc:
            sys.stderr.write(f"Propagation error: {exc}\n")
            return 3

    print("All catalogue definitions validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
