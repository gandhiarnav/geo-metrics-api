"""Pydantic v2 schemas for API requests, responses, and error envelopes."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_type: str
    feature_count: int
    crs: str
    status: str
    created_at: datetime.datetime
    processed_at: datetime.datetime | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class FileListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FileResponse]


class MeasurementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_index: int
    geometry_type: str
    status: str = Field(validation_alias="measurement_status")
    area_sq_m: float | None = None
    length_m: float | None = None
    perimeter_m: float | None = None
    geodesic_area_sq_m: float | None = None
    geodesic_length_m: float | None = None
    measurement_crs: str | None = None
    message: str | None = None


class UnitsSchema(BaseModel):
    area: str = "sq_m"
    length: str = "m"


class MeasurementSummarySchema(BaseModel):
    feature_count: int
    measured_count: int
    not_applicable_count: int
    unsupported_count: int
    error_count: int
    total_area_sq_m: float
    total_length_m: float


class MeasurementsResponse(BaseModel):
    file_id: str
    source_crs: str
    units: UnitsSchema = Field(default_factory=UnitsSchema)
    summary: MeasurementSummarySchema
    total: int
    limit: int
    offset: int
    measurements: list[MeasurementItem]


class FeatureItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_index: int
    geometry_type: str
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source_crs: str
    created_at: datetime.datetime


class FeaturesResponse(BaseModel):
    file_id: str
    total: int
    limit: int
    offset: int
    features: list[FeatureItem]
