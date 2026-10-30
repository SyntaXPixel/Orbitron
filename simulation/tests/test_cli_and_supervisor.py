"""Tests for CLI prepare and runtime configuration."""

from simulation.cli.prepare import prepare_environment
from simulation.config import SimulationConfig


def test_cli_prepare_creates_directories_and_keys(tmp_path):
    runtime_dir = tmp_path / "runtime"
    credentials_file = tmp_path / "creds.json"
    credentials_file.write_text("{}", encoding="utf-8")

    code = prepare_environment(
        backend_url="http://localhost:8000/api/v1",
        credentials_file=str(credentials_file),
        runtime_dir=str(runtime_dir),
    )
    assert code == 0

    cfg = SimulationConfig.load(runtime_dir=runtime_dir)
    assert cfg.checkpoints_dir.exists()

    # Verify keys and sample files created for org-a and org-b
    for org in ("org-a", "org-b"):
        key_file = cfg.owner_keys_dir(org) / "payload.key"
        assert key_file.exists()
        assert len(key_file.read_bytes()) == 32

        sample_file = cfg.owner_samples_dir(org) / "sample_64k.bin"
        assert sample_file.exists()
        assert len(sample_file.read_bytes()) == cfg.sample_payload_size

    # Verify gateway buffer directories
    for st_num in (1, 2, 3):
        assert cfg.gateway_buffer_dir(f"station-{st_num:02d}").exists()

