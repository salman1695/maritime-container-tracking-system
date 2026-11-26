from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    """Payload used to create a new audit log entry."""

    service_name: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=120)
    reference_value: str | None = Field(default=None, max_length=120)
    status_code: int = Field(default=200)
    latency_ms: int | None = Field(default=None, ge=0)
    details: str | None = Field(default=None)


class AuditLogResponse(BaseModel):
    """Serialized audit log record returned by the API."""

    id: int
    service_name: str
    action: str
    reference_value: str | None
    status_code: int
    latency_ms: int | None
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}