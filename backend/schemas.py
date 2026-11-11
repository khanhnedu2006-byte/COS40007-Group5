"""Typed public API contract with explicit recorded, simulated and model sources."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from speedmap import config


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
    download_mbps: float = Field(ge=0, allow_inf_nan=False)
    download_low: float = Field(ge=0, allow_inf_nan=False)
    download_high: float = Field(ge=0, allow_inf_nan=False)
    upload_mbps: float = Field(ge=0, allow_inf_nan=False)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    quality_level: Literal["Poor", "Fair", "Good", "Excellent"]
    theory_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    local_effect_mbps: float | None = Field(default=None, allow_inf_nan=False)
    nearest_towers: list[NearestTower] = Field(min_length=1, max_length=3)
    source: Literal["demo", "data", "model"]
    model_version: str
    interval_kind: Literal["illustrative", "conformal", "neighbour_spread"]
    confidence_level: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)
    data_support: DataSupport | None = None
    area_radius_m: float = Field(default=config.AREA_RADIUS_M, gt=0, allow_inf_nan=False)
    area_download_mbps: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    area_quality_level: Literal["Poor", "Fair", "Good", "Excellent"] | None = None
    area_points: int | None = Field(default=None, ge=1)
    area_ookla_tiles: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered_interval(self):
        if not self.download_low <= self.download_mbps <= self.download_high:
            raise ValueError("Download interval must contain the estimate.")
        return self
