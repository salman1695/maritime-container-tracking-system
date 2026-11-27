from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import JourneyMilestone
from shared.constants import EIGHT_STEP_JOURNEY, MilestoneStatus

EVENT_CODE_MAP: dict[str, str] = {
    "GTOT": "Gate-Out Empty",
    "GTIN": "Gate-In Full",
    "LOAD": "Loaded",
    "DEPA": "Vessel Departure",
    "POL": "Vessel Departure",
    "ARRI": "Vessel Arrival",
    "POD": "Vessel Arrival",
    "DISC": "Container Unloaded",
    "UNLD": "Container Unloaded",
    "AVPU": "Gate-Out Full",
    "GTID": "Gate-In Empty",
}


def _extract_location_name(loc: Any) -> str | None:
    """Extract location name from a SafeCube location dict or string."""
    if isinstance(loc, str) and loc.strip():
        return loc.strip()
    if isinstance(loc, dict):
        for key in ("name", "locode", "country"):
            val = loc.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_vessel_name(vessel: Any) -> str | None:
    """Extract vessel name from a SafeCube vessel dict or string."""
    if isinstance(vessel, str) and vessel.strip():
        return vessel.strip()
    if isinstance(vessel, dict):
        name = vessel.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _parse_dt(value: Any) -> datetime | None:
    """Safely parse ISO datetime strings into datetime objects."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def build_eight_step_timeline(raw_events: list[dict[str, Any]]) -> list[JourneyMilestone]:
    """Normalize SafeCube events into the fixed 8-step journey timeline."""
    matched_by_step: dict[str, dict[str, Any]] = {}

    for ev in raw_events:
        if not isinstance(ev, dict):
            continue
        code = str(ev.get("eventCode") or ev.get("event_code") or "").strip().upper()
        step_name = EVENT_CODE_MAP.get(code)
        if not step_name:
            continue

        existing = matched_by_step.get(step_name)
        is_actual = bool(ev.get("isActual", ev.get("is_actual", False)))
        if existing is None or (
            is_actual and not bool(existing.get("isActual", existing.get("is_actual", False)))
        ):
            matched_by_step[step_name] = ev

    actual_indices = [
        idx
        for idx, step_name in enumerate(EIGHT_STEP_JOURNEY)
        if step_name in matched_by_step
        and bool(
            matched_by_step[step_name].get(
                "isActual", matched_by_step[step_name].get("is_actual", False)
            )
        )
    ]
    last_actual_idx = max(actual_indices) if actual_indices else -1

    timeline: list[JourneyMilestone] = []
    for idx, step_name in enumerate(EIGHT_STEP_JOURNEY):
        ev = matched_by_step.get(step_name, {})
        event_dt = _parse_dt(ev.get("date"))
        is_actual = bool(ev.get("isActual", ev.get("is_actual", False)))
        has_event = bool(ev)

        if has_event and is_actual:
            status = MilestoneStatus.COMPLETED
            is_estimated = False
        elif idx == last_actual_idx + 1 and has_event:
            status = MilestoneStatus.IN_PROGRESS
            is_estimated = not is_actual
        else:
            status = MilestoneStatus.PENDING
            is_estimated = not is_actual if has_event else False

        timeline.append(
            JourneyMilestone(
                step_number=idx + 1,
                name=step_name,
                status=status,
                event_date=event_dt,
                is_estimated=is_estimated,
                location=_extract_location_name(ev.get("location")),
                vessel_name=_extract_vessel_name(ev.get("vessel")),
            )
        )

    return timeline