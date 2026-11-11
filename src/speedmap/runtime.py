"""Mode selection shared with the standard-library-only Windows bootstrap."""
from pathlib import Path


def resolve_mode(mode, models_dir, model_name="regional", run_id=None):
    if mode == "actual":
        return "model" if run_id or (Path(models_dir) / model_name / "LATEST").exists() else "data"
    if mode not in {"demo", "data", "model"}:
        raise ValueError("SPEEDMAP_MODE must be 'actual', 'data', 'demo' or 'model'.")
    return mode
