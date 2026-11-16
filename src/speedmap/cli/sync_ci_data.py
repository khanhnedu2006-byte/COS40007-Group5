"""Refresh CI's explicit snapshot from the current canonical Hanoi training table."""

from speedmap.data.catalog import sync_ci_snapshot


def main():
    manifest = sync_ci_snapshot()
    print(
        f"Synced {manifest['rows']:,} rows, {manifest['first_quarter']} to {manifest['last_quarter']}, SHA-256 {manifest['sha256']}"
    )


if __name__ == "__main__":
    main()
