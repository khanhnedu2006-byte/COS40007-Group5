"""Shared double-click launcher. Only uses the standard library before setup."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from speedmap.runtime import resolve_mode  # noqa: E402

WEB_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000/api/health"


def fingerprint(*paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def environment_fingerprint(root, info, *paths):
    identity = json.dumps({"python": info, "project": str(root.resolve())}, sort_keys=True)
    return hashlib.sha256((fingerprint(*paths) + identity).encode()).hexdigest()


def require_model(root, env):
    model_dir = root / "artifacts" / "models" / env.get("SPEEDMAP_MODEL_NAME", "regional")
    run = env.get("SPEEDMAP_MODEL_RUN")
    if not run:
        latest = model_dir / "LATEST"
        if not latest.is_file():
            raise RuntimeError(
                f"No trained model is available: {latest}\n"
                "Run python scripts/train_baselines.py, or use demo.bat for now."
            )
        run = latest.read_text(encoding="utf-8").strip()
    if not run:
        raise RuntimeError("The model's LATEST file is empty. Select a saved model run first.")
    required = [model_dir / run / "model.joblib", model_dir / run / "metadata.json",
                root / "data" / "interim" / "hanoi_towers.csv",
                root / "data" / "interim" / "hanoi_cells.csv",
                root / "data" / "processed" / "hanoi_tiles.csv",
                root / "data" / "reference" / "hanoi_context_grid.npz"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Real-model files are missing:\n  " + "\n  ".join(missing))


def run_setup(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def python_info(python, cwd):
    """Probe without importing installed packages; broken copied venvs return None."""
    code = (
        "import json, struct, sys; print(json.dumps({"
        "'version': list(sys.version_info[:3]), 'base': sys.base_prefix, "
        "'prefix': sys.prefix, 'executable': sys.executable, "
        "'bits': struct.calcsize('P') * 8, 'abi': sys.implementation.cache_tag}))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", code], cwd=cwd, text=True, capture_output=True,
            check=False, timeout=15,
        )
        info = json.loads(result.stdout) if result.returncode == 0 else None
        if isinstance(info, dict) and {"version", "base", "prefix", "executable", "bits", "abi"} <= info.keys():
            return info
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def compatible_environment(root, info):
    if info is None:
        return False
    env = root.resolve() / ".venv"
    cfg = env / "pyvenv.cfg"
    if not cfg.is_file():
        return False
    settings = dict(line.split("=", 1) for line in cfg.read_text(encoding="utf-8").splitlines() if "=" in line)
    settings = {key.strip(): value.strip() for key, value in settings.items()}
    created_version = settings.get("version", settings.get("version_info", "")).split(".")[:2]
    return (
        info["version"][:2] == list(sys.version_info[:2])
        and created_version == [str(part) for part in sys.version_info[:2]]
        and info["bits"] == struct.calcsize("P") * 8
        and Path(info["base"]).resolve() == Path(sys.base_prefix).resolve()
        and Path(info["prefix"]).resolve() == env
    )


def preserve_environment(root):
    """Keep the old directory as a backup, after validating both absolute paths."""
    root = root.resolve()
    source = root / ".venv"
    if source.resolve() != source or source.is_symlink():
        raise RuntimeError("The .venv path is redirected. Use a normal project-local virtual environment.")
    name = f".venv.backup-{time.strftime('%Y%m%d-%H%M%S')}"
    backup = root / name
    counter = 1
    while backup.exists():
        backup = root / f"{name}-{counter}"
        counter += 1
    if source.parent != root or backup.resolve().parent != root:
        raise RuntimeError("Environment paths must stay inside the project directory.")
    source.rename(backup)
    print(f"Saved the old Python environment as {backup.name}.", flush=True)


def ensure_environment(root):
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    info = python_info(python, root) if python.is_file() else None
    if not compatible_environment(root, info):
        if (root / ".venv").exists() or (root / ".venv").is_symlink():
            preserve_environment(root)
        print(f"Creating a fresh Python {sys.version_info.major}.{sys.version_info.minor} environment...", flush=True)
        run_setup([sys.executable, "-m", "venv", str(root / ".venv")], root)
        info = python_info(python, root)
        if not compatible_environment(root, info):
            raise RuntimeError("Could not create a working Python environment. Check your Python installation.")
    return python, info


def prepare(root, mode, node, npm, setup_backend=True, setup_frontend=True):
    version = subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
    major, minor = (int(part) for part in version.split(".")[:2])
    if not ((major == 22 and minor >= 13) or major >= 24):
        raise RuntimeError("Install Node.js 22.13+ in the Node 22 release line, or Node.js 24+.")
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    state = root / ".run"
    state.mkdir(exist_ok=True)
    if setup_backend:
        python, info = ensure_environment(root)
        requirement = root / ("requirements-model.txt" if mode == "model" else "requirements-app.txt")
        dependency_hash = environment_fingerprint(
            root, info, root / "requirements-app.txt", requirement, root / "pyproject.toml",
        )
        stamp = state / f"python-{mode}.sha256"
        installed = subprocess.run(
            [str(python), "-c", "import fastapi, uvicorn, speedmap"],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0
        if not installed or not stamp.is_file() or stamp.read_text() != dependency_hash:
            print("Installing backend dependencies (first run or requirements changed)...", flush=True)
            run_setup([str(python), "-m", "ensurepip", "--upgrade"], root)
            run_setup([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], root)
            run_setup([str(python), "-m", "pip", "install", "-r", str(requirement)], root)
            run_setup([str(python), "-m", "pip", "install", "-e", ".", "--no-deps"], root)
            stamp.write_text(dependency_hash)

    frontend = root / "frontend"
    vite = frontend / "node_modules" / "vite" / "bin" / "vite.js"
    if setup_frontend:
        frontend_identity = str(frontend.resolve()) + version + platform.system() + platform.machine()
        dependency_hash = hashlib.sha256((
            fingerprint(frontend / "package.json", frontend / "package-lock.json") + frontend_identity
        ).encode()).hexdigest()
        stamp = state / "frontend.sha256"
        if not vite.is_file() or not stamp.is_file() or stamp.read_text() != dependency_hash:
            print("Installing frontend dependencies (first run or lockfile changed)...", flush=True)
            command = [npm, "ci", "--no-fund", "--no-audit"]
            if os.name == "nt":
                command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
            run_setup(command, frontend)
            stamp.write_text(dependency_hash)
    return python, vite


def port_in_use(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def health(url=API_URL):
    with urlopen(url, timeout=2) as response:
        return json.load(response)


def verify_mode(status, mode):
    if status.get("mode") != mode:
        raise RuntimeError(
            f"An existing backend is in {status.get('mode', 'another')} mode, not {mode} mode.\n"
            "Close its launcher or backend terminal, then double-click again."
        )
    if not status.get("ready"):
        raise RuntimeError("The backend could not load its predictor. Check its log for missing data, physics code or model dependencies.")


def wait_ready(process, url, mode, log_path, frontend=False):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"A service exited during startup. Read {log_path}")
        try:
            status = health(url)
        except (OSError, URLError, ValueError):
            time.sleep(0.25)
            continue
        verify_mode(status, mode)
        if frontend:
            with urlopen(WEB_URL, timeout=2) as response:
                if "Hanoi Signal" not in response.read().decode("utf-8"):
                    raise RuntimeError("Port 5173 is serving another website. Close it before launching Hanoi Signal.")
        return
    raise RuntimeError(f"Startup timed out. Read {log_path}")


def stop_processes(processes):
    # These are direct Python/Node children, not shell process trees or unrelated servers.
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def keep_running():
    input("\nKeep this window open. Press Enter to stop the services started here.\n")


def launch(mode, no_browser=False, smoke_test=False):
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or later is required.")
    if struct.calcsize("P") * 8 != 64:
        raise RuntimeError("Install 64-bit Python 3.11 or later (including 3.14). The scientific dependencies need a 64-bit runtime.")
    print(f"Using Python {sys.version.split()[0]} (64-bit): {sys.executable}", flush=True)
    env = os.environ.copy()
    mode = resolve_mode(mode, ROOT / "artifacts" / "models",
                        env.get("SPEEDMAP_MODEL_NAME", "regional"), env.get("SPEEDMAP_MODEL_RUN"))
    env["SPEEDMAP_MODE"] = mode
    if mode == "model":
        require_model(ROOT, env)
    elif mode == "data":
        required = [ROOT / "data" / "interim" / "hanoi_towers.csv", ROOT / "data" / "processed" / "hanoi_tiles.csv"]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError("Current Hanoi data files are missing:\n  " + "\n  ".join(missing))
        print("Using current Ookla observations and tower data for spatial estimates.", flush=True)
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Node.js and npm were not found. Install Node.js 22.13+ and launch again.")

    # Never replace an unrelated service or silently reuse the other prediction mode.
    reuse_backend = port_in_use(8000)
    reuse_frontend = port_in_use(5173)
    if reuse_backend:
        try:
            verify_mode(health(), mode)
        except (OSError, URLError, ValueError) as exc:
            raise RuntimeError("Port 8000 is occupied by another service. Close it and try again.") from exc
    if reuse_frontend:
        try:
            with urlopen(WEB_URL, timeout=2) as response:
                if "Hanoi Signal" not in response.read().decode("utf-8"):
                    raise ValueError("Different website")
        except (OSError, URLError, ValueError) as exc:
            raise RuntimeError("Port 5173 is occupied by another website. Close it and try again.") from exc

    processes, logs = [], []
    try:
        if not reuse_backend or not reuse_frontend:
            python, vite = prepare(ROOT, mode, node, npm, not reuse_backend, not reuse_frontend)
        if not reuse_backend:
            backend_log = ROOT / ".run" / f"backend-{mode}.log"
            logs.append(backend_log.open("w", encoding="utf-8"))
            process = subprocess.Popen(
                [str(python), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT, env=env, stdout=logs[-1], stderr=subprocess.STDOUT,
            )
            processes.append(process)
            print(f"Starting {mode} backend... Log: {backend_log}", flush=True)
            wait_ready(process, API_URL, mode, backend_log)
        if not reuse_frontend:
            frontend_log = ROOT / ".run" / "frontend.log"
            logs.append(frontend_log.open("w", encoding="utf-8"))
            process = subprocess.Popen(
                [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
                cwd=ROOT / "frontend", env=env, stdout=logs[-1], stderr=subprocess.STDOUT,
            )
            processes.append(process)
            print(f"Starting web app... Log: {frontend_log}", flush=True)
            wait_ready(process, WEB_URL + "/api/health", mode, frontend_log, frontend=True)
        verify_mode(health(WEB_URL + "/api/health"), mode)
        print(f"\nHanoi Signal is ready in {mode} mode: {WEB_URL}", flush=True)
        if not no_browser and not smoke_test:
            webbrowser.open(WEB_URL)
        if processes and not smoke_test:
            keep_running()
    finally:
        stop_processes(processes)
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["actual", "data", "demo", "model"])
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help="Start, verify readiness, then stop owned services.")
    args = parser.parse_args()
    try:
        launch(args.mode, args.no_browser, args.smoke_test)
    except KeyboardInterrupt:
        print("\nStopped.")
    except EOFError:
        print("\nThe launcher needs an interactive console. Double-click demo.bat or start.bat.", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
