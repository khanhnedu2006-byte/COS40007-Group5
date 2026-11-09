"""Download points of interest (shops, restaurants, schools, offices...) in Hanoi from Overture Maps.

Replaces the OpenStreetMap POI download when the Overpass servers time out. Overture Places
(CDLA Permissive 2.0) is stored as GeoParquet on Amazon S3; DuckDB reads only the part around Hanoi.

    pip install duckdb        (already in requirements.txt)
    python scripts/fetch_places.py
Output: data/raw/context/overture_places.json  {"elements": [{"lat", "lon", "category"}, ...]}
"""
import json
import time
from pathlib import Path

import duckdb

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "context" / "overture_places.json"
BUCKET = "s3://overturemaps-us-west-2/release"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 20.54, 21.41, 105.35, 106.08


def latest_release(con) -> str:
    # Tìm bản phát hành mới nhất đang có trên S3 (Overture chỉ giữ vài bản gần nhất)
    files = con.execute(f"SELECT file FROM glob('{BUCKET}/*/theme=places/type=place/*')").fetchall()
    releases = sorted({f[0].split("/release/")[1].split("/")[0] for f in files})
    if not releases:
        raise SystemExit("No Overture release found on S3")
    return releases[-1]


def main() -> None:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    t0 = time.time()
    release = latest_release(con)
    print(f"Overture release {release}, reading places around Hanoi ...", flush=True)
    source = f"read_parquet('{BUCKET}/{release}/theme=places/type=place/*', hive_partitioning=1)"
    # Tên cột loại địa điểm thay đổi giữa các bản Overture: chọn cột nào đang có
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()}
    if "basic_category" in cols:
        category = "basic_category"
    elif "taxonomy" in cols:
        category = "taxonomy.primary"
    elif "categories" in cols:
        category = "categories.primary"
    else:
        category = "NULL"
    rows = con.execute(f"""
        SELECT (bbox.ymin + bbox.ymax) / 2 AS lat,
               (bbox.xmin + bbox.xmax) / 2 AS lon,
               CAST({category} AS VARCHAR) AS category
        FROM {source}
        WHERE bbox.xmin BETWEEN {LON_MIN} AND {LON_MAX}
          AND bbox.ymin BETWEEN {LAT_MIN} AND {LAT_MAX}
    """).fetchall()
    elements = [{"lat": round(a, 6), "lon": round(b, 6), "category": c} for a, b, c in rows]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": f"Overture Maps places {release}", "elements": elements}), encoding="utf-8")
    print(f"{len(elements):,} places -> {OUT}  ({time.time() - t0:.0f} s)")
    print("Next: python scripts/run_pipeline.py --step context  then  --step features")


if __name__ == "__main__":
    main()
