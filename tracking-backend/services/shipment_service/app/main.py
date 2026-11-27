from __future__ import annotations

import json
from pathlib import Path
import sys

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.schemas import ShipmentTrackRequest, ShipmentTrackResponse  # noqa: E402
from app.services.safecube_client import SafeCubeClient  # noqa: E402
from shared.constants import build_health_payload  # noqa: E402

settings = get_settings()
app = FastAPI(title="Shipment Tracking Service", version="0.1.0")


@app.get("/health")
async def health_check() -> dict:
    """Return health status for shipment_service."""
    return build_health_payload(
        service_name=settings.service_name,
        app_env=settings.app_env,
        dependencies={},
    )


@app.post("/api/v1/shipments/track", response_model=ShipmentTrackResponse)
async def track_shipment(
    payload: ShipmentTrackRequest,
    force_refresh: bool = Query(default=False),
) -> ShipmentTrackResponse:
    """Track a shipment by BL/MBL or container number with best-effort Redis caching."""
    ref_clean = payload.tracking_number.strip().upper()
    sealine_clean = payload.sealine.strip().upper() if payload.sealine else "AUTO"
    cache_key = f"shipment:{ref_clean}:{sealine_clean}"

    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1.5,
        socket_timeout=1.5,
    )

    try:
        # Read from Redis cache when available and not bypassed
        if not force_refresh:
            try:
                cached_raw = await redis_client.get(cache_key)
                if cached_raw:
                    cached_data = json.loads(cached_raw)
                    cached_data["cached"] = True
                    return ShipmentTrackResponse.model_validate(cached_data)
            except Exception:
                # Fall back to live SafeCube lookup if Redis is unreachable or timed out
                pass

        client = SafeCubeClient(
            base_url=settings.safecube_base_url,
            api_key=settings.safecube_api_key,
        )
        shipment = await client.fetch_shipment(
            tracking_number=ref_clean,
            sealine=payload.sealine,
        )

        # Best-effort cache write; never fail the tracking response if Redis is down
        try:
            await redis_client.setex(
                cache_key,
                settings.cache_ttl_seconds,
                shipment.model_dump_json(),
            )
        except Exception:
            pass

        return shipment
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"SafeCube API error: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach SafeCube API: {exc}",
        ) from exc
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            pass