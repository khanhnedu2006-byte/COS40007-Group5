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
    mode: Literal["demo", "model"]
    model_loaded: bool
    model_version: str | None
    tower_count: int


class PredictionResponse(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    download_mbps: float = Field(ge=0, allow_inf_nan=False)
    download_low: float = Field(ge=0, allow_inf_nan=False)
    download_high: float = Field(ge=0, allow_inf_nan=False)
    upload_mbps: float = Field(ge=0, allow_inf_nan=False)
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    quality_level: Literal["Poor", "Fair", "Good", "Excellent"]
    theory_mbps: float = Field(ge=0, allow_inf_nan=False)
    local_effect_mbps: float = Field(allow_inf_nan=False)
    nearest_towers: list[NearestTower] = Field(min_length=1, max_length=3)
    source: Literal["demo", "model"]
    model_version: str
    interval_kind: Literal["illustrative", "conformal"]
    confidence_level: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_interval(self):
        if not self.download_low <= self.download_mbps <= self.download_high:
            raise ValueError("Download interval must contain the estimate.")
        return self
