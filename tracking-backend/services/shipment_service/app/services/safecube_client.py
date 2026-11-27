from __future__ import annotations

from typing import Any

import httpx

from app.schemas import (
    ContainerItem,
    MapPoint,
    ShipmentMapData,
    ShipmentTrackResponse,
)
from app.services.timeline_mapper import (
    _extract_location_name,
    _extract_vessel_name,
    _parse_dt,
    build_eight_step_timeline,
)
from shared.constants import MilestoneStatus


def _detect_shipment_type(tracking_number: str) -> tuple[str, str]:
    """Return (internal_type, safecube_shipment_type) for container vs BL/MBL."""
    cleaned = tracking_number.strip().upper()
    if len(cleaned) == 11 and cleaned[:4].isalpha() and cleaned[4:].isdigit():
        return ("container", "CT")
    return ("bl_mbl", "BL")


def _clean_sealine(sealine: str | None) -> str | None:
    """Normalize sealine SCAC code and ignore placeholder values like 'string'."""
    if not sealine:
        return None
    cleaned = sealine.strip().upper()
    if cleaned in {"", "STRING", "NULL", "NONE", "AUTO"}:
        return None
    return cleaned


def _resolve_container_status(
    raw_status: Any,
    actual_events: list[dict[str, Any]],
    all_events: list[dict[str, Any]],
) -> MilestoneStatus:
    """Resolve container status from its own events and SafeCube status."""
    status_str = str(raw_status or "").strip().upper()
    if status_str in {"DELIVERED", "COMPLETED", "GATE_IN_EMPTY"}:
        return MilestoneStatus.COMPLETED

    actual_codes = {
        str(ev.get("eventCode") or ev.get("event_code") or "").strip().upper()
        for ev in actual_events
    }
    if "GTID" in actual_codes:
        return MilestoneStatus.COMPLETED
    if actual_events or status_str in {"IN_TRANSIT", "ACTIVE", "LOADED"}:
        return MilestoneStatus.IN_PROGRESS
    if all_events:
        return MilestoneStatus.IN_PROGRESS
    return MilestoneStatus.PENDING


class SafeCubeClient:
    """Client for fetching shipment and container tracking data from SafeCube."""

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def fetch_shipment(
        self,
        tracking_number: str,
        sealine: str | None = None,
    ) -> ShipmentTrackResponse:
        """Fetch tracking data from SafeCube GET /shipment and normalize it."""
        normalized_ref = tracking_number.strip().upper()
        internal_type, primary_type = _detect_shipment_type(normalized_ref)
        fallback_type = "BL" if primary_type == "CT" else "CT"
        cleaned_sealine = _clean_sealine(sealine)

        headers = {
            "API_KEY": self.api_key,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            payload: dict[str, Any] = {}
            last_error: httpx.HTTPStatusError | None = None

            for candidate_type in (primary_type, fallback_type):
                params: dict[str, str] = {
                    "shipmentNumber": normalized_ref,
                    "shipmentType": candidate_type,
                    "route": "true",
                    "ais": "true",
                }
                if cleaned_sealine:
                    params["sealine"] = cleaned_sealine

                response = await client.get(
                    f"{self.base_url}/shipment",
                    params=params,
                    headers=headers,
                )
                if response.status_code in (400, 404):
                    last_error = httpx.HTTPStatusError(
                        message=f"SafeCube {response.status_code} for type {candidate_type}",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                raw_json = response.json()
                payload = raw_json if isinstance(raw_json, dict) else {}
                break
            else:
                if last_error is not None:
                    raise last_error

        return self._normalize_payload(
            tracking_number=normalized_ref,
            tracking_type=internal_type,
            sealine=cleaned_sealine,
            raw_data=payload,
        )

    def _normalize_payload(
        self,
        tracking_number: str,
        tracking_type: str,
        sealine: str | None,
        raw_data: dict[str, Any],
    ) -> ShipmentTrackResponse:
        """Convert SafeCube v2 /shipment JSON into ShipmentTrackResponse."""
        metadata = raw_data.get("metadata") if isinstance(raw_data.get("metadata"), dict) else {}
        route = raw_data.get("route") if isinstance(raw_data.get("route"), dict) else {}
        vessels = raw_data.get("vessels") if isinstance(raw_data.get("vessels"), list) else []
        raw_containers = (
            raw_data.get("containers") if isinstance(raw_data.get("containers"), list) else []
        )

        pol = route.get("pol") if isinstance(route.get("pol"), dict) else {}
        pod = route.get("pod") if isinstance(route.get("pod"), dict) else {}

        origin = _extract_location_name(pol.get("location"))
        destination = _extract_location_name(pod.get("location"))
        etd = _parse_dt(pol.get("date"))
        eta = _parse_dt(pod.get("date"))

        all_events: list[dict[str, Any]] = []
        containers: list[ContainerItem] = []
        voyage_number: str | None = None

        for c_obj in raw_containers:
            if not isinstance(c_obj, dict):
                continue
            c_num = str(c_obj.get("number") or "").strip().upper()
            c_events = c_obj.get("events") if isinstance(c_obj.get("events"), list) else []
            dict_events = [ev for ev in c_events if isinstance(ev, dict)]
            all_events.extend(dict_events)

            actual_events = [
                ev for ev in dict_events if bool(ev.get("isActual", ev.get("is_actual", False)))
            ]
            latest_ev = actual_events[-1] if actual_events else (dict_events[-1] if dict_events else {})

            if not voyage_number:
                for ev in reversed(dict_events):
                    if ev.get("voyage"):
                        voyage_number = str(ev["voyage"]).strip()
                        break

            if c_num:
                containers.append(
                    ContainerItem(
                        container_number=c_num,
                        size_type=c_obj.get("sizeType") or c_obj.get("isoCode"),
                        current_status=_resolve_container_status(
                            c_obj.get("status"),
                            actual_events=actual_events,
                            all_events=dict_events,
                        ),
                        last_location=_extract_location_name(latest_ev.get("location")) or origin,
                        last_event_date=_parse_dt(latest_ev.get("date")) or etd,
                    )
                )

        milestones = build_eight_step_timeline(all_events)

        primary_vessel = vessels[0] if vessels and isinstance(vessels[0], dict) else {}
        vessel_name = _extract_vessel_name(primary_vessel)
        if not vessel_name:
            for ev in reversed(all_events):
                v_name = _extract_vessel_name(ev.get("vessel"))
                if v_name:
                    vessel_name = v_name
                    break

        points: list[MapPoint] = []
        route_data = raw_data.get("routeData") if isinstance(raw_data.get("routeData"), dict) else {}
        segments = (
            route_data.get("routeSegments")
            if isinstance(route_data.get("routeSegments"), list)
            else []
        )
        coords_list: list[dict[str, Any]] = []
        for seg in segments:
            if isinstance(seg, dict) and isinstance(seg.get("path"), list):
                coords_list.extend([pt for pt in seg["path"] if isinstance(pt, dict)])

        total_pts = len(coords_list)
        for idx, pt in enumerate(coords_list):
            lat = pt.get("lat")
            lng = pt.get("lng")
            if lat is None or lng is None:
                continue
            if idx == 0:
                ptype = "origin"
                label = origin or "Origin"
            elif idx == total_pts - 1:
                ptype = "destination"
                label = destination or "Destination"
            else:
                ptype = "waypoint"
                label = f"Waypoint {idx}"
            points.append(
                MapPoint(
                    label=label,
                    point_type=ptype,  # type: ignore[arg-type]
                    latitude=float(lat),
                    longitude=float(lng),
                )
            )

        resolved_sealine = sealine or metadata.get("sealine")
        api_type = str(metadata.get("shipmentType") or "").upper()
        resolved_tracking_type = "container" if api_type == "CT" else tracking_type

        return ShipmentTrackResponse(
            tracking_number=tracking_number,
            tracking_type=resolved_tracking_type,  # type: ignore[arg-type]
            sealine=str(resolved_sealine).upper() if resolved_sealine else None,
            origin=origin,
            destination=destination,
            vessel_name=vessel_name,
            voyage_number=voyage_number,
            etd=etd,
            eta=eta,
            container_count=len(containers),
            cached=False,
            milestones=milestones,
            containers=containers,
            map_data=ShipmentMapData(
                provider="safecube",
                map_url=None,
                points=points,
            ),
        )