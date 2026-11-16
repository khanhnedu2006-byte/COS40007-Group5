"""Checks for installed commands and configurable data paths."""

import os
import subprocess
import sys


def test_project_root_override_works_outside_repository(tmp_path):
    root = tmp_path / "project-data"
    env = {**os.environ, "SPEEDMAP_ROOT": str(root)}
    result = subprocess.run(
        [sys.executable, "-c", "from speedmap import config; print(config.TRAIN_FILE)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(root / "data" / "processed" / "hanoi_train.csv")


def test_pipeline_module_is_available_outside_repository(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "speedmap.cli.run_pipeline", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--step" in result.stdout
