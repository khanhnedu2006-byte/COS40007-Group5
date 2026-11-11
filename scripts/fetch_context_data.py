"""Download extra map data for Hanoi (run on your own computer with normal internet).

Only the Python standard library is needed. Files go to data/raw/context/ (about 0.6–0.9 GB in total).
Already downloaded files are skipped, so you can run it again after an error.

    python scripts/fetch_context_data.py

Sources (all free):
- WorldPop 2020 population, 100 m (CC BY 4.0)                     -> people living around a point
- ESA WorldCover 2021 land cover, 10 m (CC BY 4.0)                -> built-up / trees / cropland / water
- Copernicus DEM GLO-30 elevation, 30 m (free licence)            -> hills block the signal
- OpenStreetMap major roads and points of interest (ODbL)         -> busy places, where operators invest
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "context"
UA = {"User-Agent": "COS40007-Group5-speedmap/0.1"}

RASTERS = [
    ("worldpop_vnm_2020.tif", [
        "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/VNM/vnm_ppp_2020_UNadj.tif",
        "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/VNM/vnm_ppp_2020.tif",
    ]),
    *[(f"worldcover_{t}.tif", [f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"])
      for t in ("N18E105", "N21E105")],
    *[(f"dem_{t}.tif", [f"https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_00_DEM/Copernicus_DSM_COG_10_{t}_00_DEM.tif"])
      for t in ("N20_00_E105", "N21_00_E105", "N20_00_E106", "N21_00_E106")],
]

OVERPASS_URLS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
BBOX = "20.54,105.35,21.41,106.08"  # nam, tây, bắc, đông (khung Hà Nội)
OSM_QUERIES = {
    "osm_roads.json": [f'[out:json][timeout:180];way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({BBOX});out geom;'],
}


def _quadrants(bbox: str, n: int = 3) -> list:
    """Chia khung Hà Nội thành n x n ô nhỏ để mỗi truy vấn Overpass nhẹ, ít bị quá thời gian."""
    s, w, nth, e = map(float, bbox.split(","))
    lats = [s + (nth - s) * i / n for i in range(n + 1)]
    lons = [w + (e - w) * i / n for i in range(n + 1)]
    return [f"{lats[i]:.4f},{lons[j]:.4f},{lats[i + 1]:.4f},{lons[j + 1]:.4f}" for i in range(n) for j in range(n)]


# Điểm dịch vụ: tách theo loại tag và theo 9 ô nhỏ, rồi gộp lại
OSM_QUERIES["osm_pois.json"] = [f'[out:json][timeout:90];nwr["{key}"]({box});out center;'
                                 for key in ("amenity", "shop", "office") for box in _quadrants(BBOX)]


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done, last = 0, -10
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            pct = int(done * 100 / total) if total else 0
            if total and pct >= last + 10:
                print(f"    {pct}% of {total / 1e6:.0f} MB", flush=True)
                last = pct
    tmp.replace(dest)


def fetch_rasters() -> list:
    failed = []
    for name, urls in RASTERS:
        dest = OUT / name
        if dest.exists():
            print(f"[skip] {name} already downloaded")
            continue
        for url in urls:
            print(f"[get ] {name} <- {url}", flush=True)
            try:
                download(url, dest)
                break
            except Exception as exc:  # thử link dự phòng nếu có
                print(f"    failed: {exc}")
        else:
            failed.append(name)
    return failed


def _overpass(query: str):
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(2):
        for url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(url, data=data, headers=UA)
                with urllib.request.urlopen(req, timeout=150) as resp:
                    return json.load(resp).get("elements", [])
            except Exception as exc:  # server Overpass bận: thử server khác, rồi thử lại cả vòng
                print(f"    {url.split('/')[2]} failed: {exc}", flush=True)
                time.sleep(3)
        time.sleep(15)
    return None


def fetch_osm() -> list:
    failed = []
    for name, queries in OSM_QUERIES.items():
        dest = OUT / name
        if dest.exists():
            print(f"[skip] {name} already downloaded")
            continue
        elements, ok = {}, True
        for i, query in enumerate(queries, 1):
            print(f"[get ] {name} part {i}/{len(queries)}", flush=True)
            part = _overpass(query)
            if part is None:
                ok = False
                break
            for el in part:  # bỏ trùng (một đối tượng có thể có cả amenity và shop)
                elements[f"{el['type']}/{el['id']}"] = el
            print(f"    {len(part):,} objects (total {len(elements):,})", flush=True)
        if ok:
            dest.write_text(json.dumps({"elements": list(elements.values())}), encoding="utf-8")
        else:
            failed.append(name)
    return failed


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    failed = fetch_rasters() + fetch_osm()
    print()
    if failed:
        print("Not downloaded (run the script again later):", ", ".join(failed))
        sys.exit(1)
    print(f"All files are in {OUT}")
    print("Next: python scripts/run_pipeline.py --step context  (needs: pip install rasterio)")


if __name__ == "__main__":
    main()
