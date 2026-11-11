"""Canonical Hanoi inputs shared by the application, inference and training."""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from speedmap import config
from speedmap.data.boundary import contains
from speedmap.data.towers import load_towers


def data_paths():
    return {"towers": config.TOWERS_FILE, "training": config.TRAIN_FILE,
            "tiles": config.TILES_FILE, "boundary": config.HANOI_BOUNDARY_FILE}


def file_digest(path):
    # Git may convert text line endings on Windows; this is the same data version.
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def data_fingerprints():
    return {name: file_digest(path) for name, path in data_paths().items() if Path(path).is_file()}


def verify_fingerprints(expected):
    if not isinstance(expected, dict) or "towers" not in expected:
        raise ValueError("The model has no tower-data provenance. Fit and save a model using the current dataset.")
    for name, digest in expected.items():
        path = data_paths().get(name)
        if path is None or not Path(path).is_file() or file_digest(path) != digest:
            raise ValueError(f"The saved model's {name} data differs from the current dataset. Retrain or select a matching model run.")


def load_tower_table(path=None):
    path = Path(path) if path is not None else config.TOWERS_FILE
    towers = load_towers(path)
    required = {"tower_id", "latitude", "longitude"}
    if towers.empty or not required.issubset(towers.columns):
        raise ValueError(f"{path} must contain tower_id, latitude and longitude, with at least one row.")
    coords = towers[["latitude", "longitude"]].apply(pd.to_numeric, errors="coerce")
    if (not np.isfinite(coords.to_numpy()).all() or not coords["latitude"].between(-90, 90).all()
            or not coords["longitude"].between(-180, 180).all()):
        raise ValueError(f"{path} contains invalid tower coordinates.")
    ids = towers["tower_id"].astype(str).str.strip()
    if towers["tower_id"].isna().any() or ids.eq("").any() or ids.duplicated().any():
        raise ValueError(f"{path} must contain present, unique tower IDs.")
    towers = towers.assign(latitude=coords["latitude"], longitude=coords["longitude"])
    if "source" not in towers:
        towers = towers.assign(source="estimated")
    towers["source"] = towers["source"].fillna("estimated").astype(str).str.strip().replace("", "estimated")
    return towers[["tower_id", "latitude", "longitude", "source"]].reset_index(drop=True)


def _validate_observations(table, path):
    columns = ["latitude", "longitude", "download_mbps", "upload_mbps", "latency_ms", "tests"]
    if table.empty or not {"quadkey", *columns}.issubset(table):
        raise ValueError(f"{path} is empty or missing required Hanoi observation columns.")
    values = table[columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError(f"{path} contains missing or non-finite observations.")
    if ((values["download_mbps"] <= 0).any() or (values["tests"] < 1).any()
            or (values[["upload_mbps", "latency_ms"]] < 0).any().any()):
        raise ValueError(f"{path} contains invalid speeds, latency or test counts.")
    if not contains(values["latitude"], values["longitude"]).all():
        raise ValueError(f"{path} contains observations outside Hanoi. Rebuild the canonical Hanoi tables.")
    if table["quadkey"].isna().any():
        raise ValueError(f"{path} contains missing tile IDs.")
    table[columns] = values
    return table


def load_tile_table(path=None):
    path = Path(path) if path is not None else config.TILES_FILE
    table = _validate_observations(pd.read_csv(path, dtype={"quadkey": "string"}), path)
    if table["quadkey"].duplicated().any():
        raise ValueError(f"{path} must have one row per tile.")
    for column in ["first_quarter", "last_quarter"]:
        if column not in table or not table[column].astype(str).str.fullmatch(r"\d{4}-[1-4]").all():
            raise ValueError(f"{path} must include valid {column} values.")
    return table


def load_training_table(path=None):
    path = Path(path) if path is not None else config.TRAIN_FILE
    table = _validate_observations(pd.read_csv(path, dtype={"quadkey": "string"}), path)
    columns = list(config.FEATURE_COLUMNS)
    columns += [config.WEIGHT_COLUMN, config.GROUP_COLUMN]
    if not {"quarter", *columns}.issubset(table):
        raise ValueError(f"{path} is missing shared training features.")
    required_columns = [column for column in columns if column not in config.OPTIONAL_FEATURES]
    optional = table[config.OPTIONAL_FEATURES].to_numpy(dtype=float)
    if not np.isfinite(table[required_columns].to_numpy(dtype=float)).all() or np.isinf(optional).any():
        raise ValueError(f"{path} contains invalid training features.")
    if not table["quarter"].astype(str).str.fullmatch(r"\d{4}-[1-4]").all():
        raise ValueError(f"{path} contains invalid quarter values.")
    if table.duplicated(["quadkey", "quarter"]).any():
        raise ValueError(f"{path} contains duplicate tile-quarter rows.")
    return table


def sync_ci_snapshot(destination=None):
    """Refresh the committed CI input from the canonical table, without changing it."""
    source = config.TRAIN_FILE
    table = load_training_table(source)
    destination = Path(destination) if destination is not None else config.ROOT / "data" / "ci" / "hanoi_train.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() == Path(source).resolve():
        raise ValueError("The CI destination must differ from the canonical training file.")
    shutil.copyfile(source, destination)
    manifest = {"schema_version": 1, "source": "data/processed/hanoi_train.csv",
                "sha256": file_digest(source), "rows": len(table),
                "first_quarter": table["quarter"].min(), "last_quarter": table["quarter"].max(),
                "data_fingerprints": data_fingerprints()}
    destination.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_ci_training_table(path):
    path = Path(path)
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise ValueError("CI dataset provenance is missing. Run python scripts/sync_ci_data.py.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != file_digest(path):
        raise ValueError("CI data differs from its manifest. Run python scripts/sync_ci_data.py.")
    if config.TRAIN_FILE.is_file() and file_digest(config.TRAIN_FILE) != manifest["sha256"]:
        raise ValueError("CI is using an older dataset. Run python scripts/sync_ci_data.py.")
    return load_training_table(path), manifest
