"""CLI for predicting satellite contact opportunities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scheduler.api import predict_opportunities


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict satellite contact opportunities")
    parser.add_argument(
        "--catalog",
        "-c",
        required=True,
        type=Path,
        help="Path to catalogue JSON file (containing satellites, stations, orbit_definitions)",
    )
    parser.add_argument(
        "--horizon",
        required=True,
        type=Path,
        help="Path to horizon JSON file (containing from_at and to_at)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to write opportunities JSON (default: stdout)",
    )

    args = parser.parse_args()

    try:
        with open(args.catalog, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        with open(args.horizon, "r", encoding="utf-8") as f:
            horizon = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Error reading input files: {exc}\n")
        return 1

    try:
        opportunities = predict_opportunities(catalog=catalog, horizon=horizon)
    except Exception as exc:
        sys.stderr.write(f"Prediction error: {exc}\n")
        return 2

    output_json = json.dumps(opportunities, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json + "\n")
            print(f"Opportunities written to {args.output} ({len(opportunities)} windows)")
        except Exception as exc:
            sys.stderr.write(f"Error writing output file: {exc}\n")
            return 3
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
