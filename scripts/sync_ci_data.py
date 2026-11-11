"""Refresh CI's explicit snapshot from the current canonical Hanoi training table."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from speedmap.data.catalog import sync_ci_snapshot

if __name__ == "__main__":
    manifest = sync_ci_snapshot()
    print(f"Synced {manifest['rows']:,} rows, {manifest['first_quarter']} to {manifest['last_quarter']}, SHA-256 {manifest['sha256']}")
