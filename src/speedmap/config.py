"""Shared settings for the whole project. Change values here, not inside other modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Thư mục dữ liệu
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
ARTIFACTS_MODELS = ROOT / "artifacts" / "models"
ARTIFACTS_REPORTS = ROOT / "artifacts" / "reports"

# File dữ liệu
OOKLA_RAW_FILE = DATA_RAW / "ookla_hanoi_mobile.csv"
OPENCELLID_RAW_FILE = DATA_RAW / "452.csv.gz"
OSM_TOWERS_RAW_FILE = DATA_RAW / "osm_comm_towers.csv"
OOKLA_CLEAN_FILE = DATA_INTERIM / "ookla_clean.csv"
TOWERS_FILE = DATA_INTERIM / "hanoi_towers.csv"
CELLS_FILE = DATA_INTERIM / "hanoi_cells.csv"
TRAIN_FILE = DATA_PROCESSED / "hanoi_train.csv"
TILES_FILE = DATA_PROCESSED / "hanoi_tiles.csv"
HANOI_BOUNDARY_FILE = ROOT / "data" / "reference" / "hanoi_boundary.geojson"
CONTEXT_GRID_FILE = ROOT / "data" / "reference" / "hanoi_context_grid.npz"
CONTEXT_GRID_RES_DEG = 0.001  # ~110 m x 104 m

# Khu vực Hà Nội: khung bao để lọc nhanh, ranh giới thật nằm trong HANOI_BOUNDARY_FILE
HANOI_BBOX = {"lat_min": 20.54, "lat_max": 21.41, "lon_min": 105.35, "lon_max": 106.08}
HANOI_CENTER = (21.0285, 105.8542)

RANDOM_SEED = 42

# Làm sạch dữ liệu
MAX_LATENCY_MS = 500
MIN_TESTS_FOR_EVAL = 3
MIN_TOWER_SAMPLES = 2
TOWER_RADIOS = ("LTE", "NR")  # cell di động hiện đại, gộp chung thành "trạm"; không phân biệt công nghệ
TOWER_MERGE_DECIMALS = 3
TOWER_BUFFER_KM = 5
OSM_MIN_GAP_M = 200  # chỉ thêm cột OSM cách trạm OpenCelliD gần nhất trên 200 m (tránh trùng)  # giữ cả trạm ngoài ranh giới nhưng cách biên dưới 5 km

# Bảng mỗi ô một dòng (hanoi_tiles.csv)
POOL_QUARTERS = 4  # gộp các quý gần nhất để giảm nhiễu
RELIABILITY_LEVELS = [(3, "low"), (10, "medium"), (float("inf"), "high")]  # theo tổng số test của ô  # làm tròn toạ độ (~100 m) để gộp các cell thành một trạm

# Đặc trưng trạm
TOWER_SEARCH_RADIUS_M = 3000
NEAREST_TOWERS_IN_POPUP = 3

# Ước lượng theo vùng quanh điểm click (độ chính xác cao hơn dự đoán từng ô, xem docs/data_contract.md)
AREA_RADIUS_M = 1500
AREA_MIN_TILES = 5  # ít hơn số ô Ookla này trong vùng thì lấy thêm điểm lưới
AREA_GRID_STEP_M = 300

# Giả định cho mô hình 3GPP (nhà mạng không công bố, dùng giá trị điển hình)
# Một cấu hình chung cho mọi trạm (giá trị điển hình của trạm hiện đại)
TOWER_PHYSICS = {"freq_ghz": 3.5, "bandwidth_mhz": 100, "tx_power_dbm": 46}
UE_HEIGHT_M = 1.5
NOISE_FIGURE_DB = 7
MIN_DISTANCE_M = 10
MAX_SPECTRAL_EFFICIENCY = 7.4  # bit/s/Hz, giới hạn thực tế của 256-QAM

# Đánh giá
SPATIAL_BLOCK_KM = 2.0
CV_FOLDS = 5
CALIBRATION_SHARE = 0.2
CONFIDENCE_LEVEL = 0.80

# Mức chất lượng theo download (Mbps), xem mục 5.1 của spec
QUALITY_LEVELS = [(15, "Poor"), (100, "Fair"), (200, "Good"), (float("inf"), "Excellent")]

# Hợp đồng dữ liệu giữa phần dữ liệu và phần model, xem docs/data_contract.md
TARGET_COLUMN = "download_mbps"
SECONDARY_TARGETS = ["upload_mbps", "latency_ms"]
WEIGHT_COLUMN = "sample_weight"
GROUP_COLUMN = "block_id"
# Đặc trưng trạm (tower_features.py)
TOWER_FEATURES = ["dist_nearest_tower_m", "towers_500m", "towers_1km", "theory_mbps"]
# Đặc trưng hạ tầng và đô thị (point_features.py)
INFRA_FEATURES = ["cells_1km", "cells_2km", "operators_1km", "center_km"]
# Mức độ sử dụng quanh điểm, từ số thiết bị Ookla của các ô (không dùng tốc độ -> không rò nhãn)
ACTIVITY_RADII_M = [1000, 2000, 5000]
ACTIVITY_FEATURES = ["own_devices"] + [f"devices_{r // 1000}km" for r in ACTIVITY_RADII_M] + ["tiles_1km", "tiles_2km"]
# Bối cảnh khu vực: dân số, đất xây dựng, cây, ruộng, nước, độ cao, đường lớn, điểm dịch vụ (context_features.py)
CONTEXT_FEATURES = ["population_500m", "population_1km", "builtup_500m", "builtup_1km", "trees_1km", "cropland_1km",
                    "water_1km", "elevation_m", "slope_deg", "roads_km_1km", "pois_1km"]
# Các cột được phép trống khi chưa có dữ liệu nguồn
OPTIONAL_FEATURES = ["theory_mbps"] + CONTEXT_FEATURES
FEATURE_COLUMNS = ["latitude", "longitude"] + TOWER_FEATURES + INFRA_FEATURES + ACTIVITY_FEATURES + CONTEXT_FEATURES


def quality_level(download_mbps: float) -> str:
    for upper, name in QUALITY_LEVELS:
        if download_mbps < upper:
            return name
    return QUALITY_LEVELS[-1][1]


def inside_hanoi(lat: float, lon: float) -> bool:
    """True if the point is inside the Hanoi administrative boundary."""
    from speedmap.data.boundary import contains

    return bool(contains(lat, lon)[0])
