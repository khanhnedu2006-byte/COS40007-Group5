"""Typed public API contract; simulated data is always identified explicitly."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Tower(BaseModel):
    tower_id: int | str
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source: str = "opencellid"


class NearestTower(Tower):
    distance_m: float = Field(ge=0, allow_inf_nan=False)


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    ready: bool
    mode: Literal["demo", "data", "model"]
    model_loaded: bool
    model_version: str | None
    tower_count: int
    tower_data_source: Literal["dataset", "simulated"] | None = None
    observation_count: int | None = None
    data_period: str | None = None
    data_fingerprints: dict[str, str] = Field(default_factory=dict)


class DataSupport(BaseModel):
    tiles_used: int = Field(ge=1)
    tests: int = Field(ge=1)
    nearest_tile_distance_m: float = Field(ge=0, allow_inf_nan=False)
    latest_quarter: str


class PredictionResponse(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    area_download_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    area_quality_level: Literal["Poor", "Fair", "Good", "Excellent"] | None = None
    area_radius_m: float = Field(default=1500, gt=0, allow_inf_nan=False)
    area_points: int | None = Field(default=None, gt=0)
    area_ookla_tiles: int | None = Field(default=None, ge=0)
    area_grid_points: int = Field(default=0, ge=0)
    nearest_towers: list[NearestTower] = Field(min_length=1, max_length=3)
    source: Literal["demo", "data", "model"]
    model_name: Literal["knn", "random_forest", "simulated", "recorded"] = "recorded"
    model_version: str

    # Recorded-data clients retain their point-level fields for compatibility.
    download_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    download_low: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    download_high: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    upload_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    quality_level: Literal["Poor", "Fair", "Good", "Excellent"] | None = None
    theory_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    local_effect_mbps: float | None = Field(default=None, allow_inf_nan=False)
    interval_kind: Literal["illustrative", "conformal", "neighbour_spread"] | None = None
    confidence_level: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)
    data_support: DataSupport | None = None

    @model_validator(mode="after")
    def consistent_support(self):
        if self.source != "data" and self.area_download_mbps is None:
            raise ValueError("Regional model and demo responses require an area estimate")
        if self.area_download_mbps is not None and (
            self.area_points is None or self.area_ookla_tiles is None or self.area_quality_level is None
            or self.area_points != self.area_ookla_tiles + self.area_grid_points
        ):
            raise ValueError("Area point count must equal tile plus grid point counts")
        if (self.source == "demo") != (self.model_name == "simulated"):
            raise ValueError("Demo source must identify a simulated model")
        return self
