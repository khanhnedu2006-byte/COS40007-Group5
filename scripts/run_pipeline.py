"""Run the whole pipeline without notebooks (once every module is implemented).

Usage (from the project root):
    python scripts/run_pipeline.py --step all
    python scripts/run_pipeline.py --step towers
Steps: towers, context, features, baselines, hybrid, all
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from speedmap import config  # noqa: E402


def run_towers():
    from speedmap.data import towers

    raw = towers.load_opencellid()
    hanoi = towers.add_osm_masts(towers.filter_hanoi(raw), towers.load_osm_masts())
    config.TOWERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    hanoi.to_csv(config.TOWERS_FILE, index=False)
    print(f"{len(hanoi):,} towers -> {config.TOWERS_FILE}  {hanoi['source'].value_counts().to_dict()}")
    cells = towers.cell_table(towers.filter_cells(raw))
    cells.to_csv(config.CELLS_FILE, index=False)
    print(f"{len(cells):,} cells -> {config.CELLS_FILE}")


def run_context():
    from speedmap.data.context import build_context_grid, save_context_grid

    layers = build_context_grid()
    if not layers:
        raise SystemExit("No context data found: run python scripts/fetch_context_data.py first")
    save_context_grid(layers)
    print(f"{len(layers)} layers {sorted(layers)} -> {config.CONTEXT_GRID_FILE}")


def run_features(*, include_physics: bool = False):
    from speedmap.data import ookla, towers
    from speedmap.features.build import build_tile_table, build_training_table, pool_tiles

    clean = ookla.clean(ookla.load_raw())
    config.OOKLA_CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(config.OOKLA_CLEAN_FILE, index=False)
    hanoi_towers, cells = towers.load_towers(), towers.load_cells()
    config.TILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not include_physics:
        print("Physics skipped for baselines; theory_mbps is intentionally empty.")
    tiles = build_tile_table(clean, hanoi_towers, cells, include_physics=include_physics)
    tiles.to_csv(config.TILES_FILE, index=False)
    print(f"{len(tiles):,} tiles -> {config.TILES_FILE}")
    train = build_training_table(clean, hanoi_towers, cells, pool_tiles(clean), include_physics=include_physics)
    train.to_csv(config.TRAIN_FILE, index=False)
    print(f"{len(train):,} rows -> {config.TRAIN_FILE}")
    from speedmap.data.catalog import sync_ci_snapshot

    manifest = sync_ci_snapshot()
    print(f"CI snapshot updated: {manifest['rows']:,} rows, SHA-256 {manifest['sha256']}")


def run_baselines():
    from speedmap.training import train_baselines

    train_baselines()


def run_hybrid():
    # TODO: giống notebook 06
    raise NotImplementedError


STEPS = {"towers": run_towers, "context": run_context, "features": run_features, "baselines": run_baselines, "hybrid": run_hybrid}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", default="all", choices=[*STEPS, "all"])
    parser.add_argument("--include-physics", action="store_true",
                        help="Attempt the theory feature during --step features (unfinished physics warns).")
    args = parser.parse_args()
    for name, step in STEPS.items():
        if args.step in (name, "all"):
            print(f"== {name}")
            if name == "features":
                step(include_physics=args.include_physics)
            else:
                step()


if __name__ == "__main__":
    main()
