"""Startup mode, artifact and cleanup checks without downloading dependencies."""
import json
import subprocess
from unittest.mock import Mock

import pytest

from scripts import launch


def test_missing_real_model_is_reported_instead_of_using_demo(tmp_path):
    with pytest.raises(RuntimeError, match="No trained model"):
        launch.require_model(tmp_path, {})


def test_explicit_model_run_does_not_need_latest_pointer(tmp_path):
    root = tmp_path / "School project with spaces"
    run = root / "artifacts" / "models" / "hybrid" / "approved-run"
    run.mkdir(parents=True)
    (run / "model.joblib").touch()
    (run / "metadata.json").write_text("{}")
    towers = root / "data" / "interim" / "hanoi_towers.csv"
    towers.parent.mkdir(parents=True)
    towers.touch()
    launch.require_model(root, {"SPEEDMAP_MODEL_RUN": "approved-run"})
    towers.unlink()
    with pytest.raises(RuntimeError, match="hanoi_towers.csv"):
        launch.require_model(root, {"SPEEDMAP_MODEL_RUN": "approved-run"})


def test_existing_demo_cannot_be_reused_as_real_model():
    with pytest.raises(RuntimeError, match="not model mode"):
        launch.verify_mode({"mode": "demo", "ready": True}, "model")
    with pytest.raises(RuntimeError, match="could not load"):
        launch.verify_mode({"mode": "model", "ready": False}, "model")


def test_dependency_fingerprint_changes_with_requirements(tmp_path):
    requirement = tmp_path / "requirements.txt"
    requirement.write_text("fastapi\n")
    before = launch.fingerprint(requirement)
    requirement.write_text("fastapi\nuvicorn\n")
    assert launch.fingerprint(requirement) != before


def test_cleanup_waits_for_owned_processes_and_kills_only_if_needed():
    backend, frontend = Mock(), Mock()
    backend.poll.return_value = None
    frontend.poll.return_value = None
    frontend.wait.side_effect = [subprocess.TimeoutExpired("node", 5), 0]
    launch.stop_processes([backend, frontend])
    backend.terminate.assert_called_once()
    frontend.terminate.assert_called_once()
    backend.kill.assert_not_called()
    frontend.kill.assert_called_once()


def test_reusing_ready_services_opens_browser_without_setup_or_termination(monkeypatch):
    monkeypatch.setattr(launch, "port_in_use", lambda port: True)
    monkeypatch.setattr(launch.shutil, "which", lambda name: name)
    monkeypatch.setattr(launch, "health", lambda *args: {"mode": "demo", "ready": True})
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"<title>Hanoi Signal</title>"
    monkeypatch.setattr(launch, "urlopen", lambda *args, **kwargs: response)
    prepare, popen, browser = Mock(), Mock(), Mock()
    monkeypatch.setattr(launch, "prepare", prepare)
    monkeypatch.setattr(launch.subprocess, "Popen", popen)
    monkeypatch.setattr(launch.webbrowser, "open", browser)
    launch.launch("demo")
    prepare.assert_not_called()
    popen.assert_not_called()
    browser.assert_called_once_with(launch.WEB_URL)


def test_startup_failure_stops_already_started_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "ROOT", tmp_path)
    (tmp_path / ".run").mkdir()
    monkeypatch.setattr(launch, "port_in_use", lambda port: False)
    monkeypatch.setattr(launch.shutil, "which", lambda name: name)
    monkeypatch.setattr(launch, "prepare", lambda *args: ("python", "vite.js"))
    backend = Mock()
    backend.poll.return_value = None
    monkeypatch.setattr(launch.subprocess, "Popen", Mock(side_effect=[backend, OSError("frontend failed")]))
    monkeypatch.setattr(launch, "wait_ready", lambda *args, **kwargs: None)
    with pytest.raises(OSError, match="frontend failed"):
        launch.launch("demo", no_browser=True)
    backend.terminate.assert_called_once()


def test_reused_frontend_never_has_its_dependencies_reinstalled(tmp_path, monkeypatch):
    monkeypatch.setattr(launch.subprocess, "check_output", lambda *args, **kwargs: "v22.17.0")
    setup = Mock()
    monkeypatch.setattr(launch, "run_setup", setup)
    launch.prepare(tmp_path, "demo", "node", "npm", setup_backend=False, setup_frontend=False)
    setup.assert_not_called()


def test_waiting_for_failed_model_does_not_open_a_demo(monkeypatch, tmp_path):
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(launch, "health", lambda *args: json.loads('{"mode":"model","ready":false}'))
    with pytest.raises(RuntimeError, match="could not load"):
        launch.wait_ready(process, launch.API_URL, "model", tmp_path / "model.log")
