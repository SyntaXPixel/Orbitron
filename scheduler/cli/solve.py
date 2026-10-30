"""CLI for solving scheduling problems."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scheduler.api import solve_schedule


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve Orbitron scheduling problem")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Path to problem JSON file",
    )
    parser.add_argument(
        "--algorithm",
        "-a",
        default="optimized",
        choices=["fifo", "optimized"],
        help="Scheduling algorithm (default: optimized)",
    )
    parser.add_argument(
        "--time-limit",
        "-t",
        default=5,
        type=int,
        help="Solver time limit in seconds (default: 5)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to write result JSON (default: stdout)",
    )

    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            problem = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Error reading problem file: {exc}\n")
        return 1

    try:
        result = solve_schedule(
            problem=problem,
            algorithm=args.algorithm,
            time_limit_seconds=args.time_limit,
        )
    except Exception as exc:
        sys.stderr.write(f"Scheduling error: {exc}\n")
        return 2

    output_json = json.dumps(result, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json + "\n")
            print(f"Result written to {args.output}")
        except Exception as exc:
            sys.stderr.write(f"Error writing output file: {exc}\n")
            return 3
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
