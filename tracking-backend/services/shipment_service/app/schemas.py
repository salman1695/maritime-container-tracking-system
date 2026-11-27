from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from shared.constants import MilestoneStatus


class ShipmentTrackRequest(BaseModel):
    """Input payload for tracking a shipment by BL/MBL or container number."""

    tracking_number: str = Field(..., min_length=4, max_length=64)
    sealine: str | None = Field(default=None, max_length=64)


class JourneyMilestone(BaseModel):
    """Normalized milestone inside the 8-step shipment journey."""

    step_number: int = Field(..., ge=1, le=8)
    name: str
    status: MilestoneStatus
    event_date: datetime | None = None
    is_estimated: bool = False
    location: str | None = None
    vessel_name: str | None = None


class ContainerItem(BaseModel):
    """Normalized container details for single or multi-container shipments."""

    container_number: str
    size_type: str | None = None
    current_status: MilestoneStatus = MilestoneStatus.PENDING
    last_location: str | None = None
    last_event_date: datetime | None = None


class MapPoint(BaseModel):
    """Geographic coordinate used to render SafeCube route/location pins."""

    label: str
    point_type: Literal["origin", "current", "destination", "waypoint"]
    latitude: float
    longitude: float
    timestamp: datetime | None = None


class ShipmentMapData(BaseModel):
    """Map payload supporting the View map action on the shipment page."""

    provider: str = "safecube"
    map_url: str | None = None
    points: list[MapPoint] = Field(default_factory=list)


class ShipmentTrackResponse(BaseModel):
    """Complete normalized shipment response returned to clients."""

    tracking_number: str
    tracking_type: Literal["bl_mbl", "container"]
    sealine: str | None = None
    origin: str | None = None
    destination: str | None = None
    vessel_name: str | None = None
    voyage_number: str | None = None
    etd: datetime | None = None
    eta: datetime | None = None
    container_count: int = 0
    cached: bool = False
    milestones: list[JourneyMilestone] = Field(default_factory=list)
    containers: list[ContainerItem] = Field(default_factory=list)
    map_data: ShipmentMapData = Field(default_factory=ShipmentMapData)