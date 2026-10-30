"""Tests for the scheduler command line interface tools."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_validate_catalog():
    """Verify validate_catalog CLI tool."""
    cmd = [
        sys.executable,
        "-m",
        "scheduler.cli.validate_catalog",
        "--catalog",
        "scheduler/fixtures/catalog.json",
        "--at",
        "2026-10-31T06:00:00Z",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "validated successfully" in proc.stdout


def test_cli_predict(tmp_path: Path):
    """Verify predict CLI tool outputs valid JSON opportunities."""
    out_file = tmp_path / "opps.json"
    cmd = [
        sys.executable,
        "-m",
        "scheduler.cli.predict",
        "--catalog",
        "scheduler/fixtures/catalog.json",
        "--horizon",
        "scheduler/fixtures/horizon.json",
        "--output",
        str(out_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert out_file.exists()

    with open(out_file, "r") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) > 0


def test_cli_solve(tmp_path: Path):
    """Verify solve CLI tool runs with both fifo and optimized."""
    for algo in ["fifo", "optimized"]:
        out_file = tmp_path / f"result_{algo}.json"
        cmd = [
            sys.executable,
            "-m",
            "scheduler.cli.solve",
            "--input",
            "scheduler/fixtures/problem.json",
            "--algorithm",
            algo,
            "--output",
            str(out_file),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0
        assert out_file.exists()

        with open(out_file, "r") as f:
            res = json.load(f)
        assert res["status"] == "feasible"
        assert res["metrics"]["algorithm_used"] in ("fifo", "optimized")
