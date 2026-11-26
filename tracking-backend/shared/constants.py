from __future__ import annotations

from enum import StrEnum


class MilestoneStatus(StrEnum):
    """Non-technical milestone status labels for shipment journeys."""

    COMPLETED = "Completed"
    IN_PROGRESS = "In Progress"
    PENDING = "Pending"


class TerrestrialCoverageStatus(StrEnum):
    """Coverage state for single-vessel terrestrial AIS tracking."""

    IN_RANGE = "in_terrestrial_range"
    OUT_OF_RANGE = "out_of_terrestrial_range"


# Fixed 8-step normalized shipment journey order
EIGHT_STEP_JOURNEY: tuple[str, ...] = (
    "Gate-Out Empty",
    "Gate-In Full",
    "Loaded",
    "Vessel Departure",
    "Vessel Arrival",
    "Container Unloaded",
    "Gate-Out Full",
    "Gate-In Empty",
)


def build_health_payload(
    service_name: str,
    app_env: str,
    dependencies: dict[str, str],
) -> dict:
    """Build a uniform health response dictionary for any microservice."""
    all_up = all(state == "up" for state in dependencies.values()) if dependencies else True
    return {
        "service": service_name,
        "status": "healthy" if all_up else "degraded",
        "environment": app_env,
        "dependencies": dependencies,
    }