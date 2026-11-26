from __future__ import annotations

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import AuditLog
from app.schemas import AuditLogCreate, AuditLogResponse
import httpx

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database tables on startup and dispose resources on shutdown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Audit & Health Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Check service health along with PostgreSQL and Redis connectivity."""
    db_ok = False
    redis_ok = False

    # Verify PostgreSQL connection
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Verify Redis connection
    redis_client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
    try:
        pong = await redis_client.ping()
        redis_ok = bool(pong)
    except Exception:
        redis_ok = False
    finally:
        await redis_client.aclose()

    overall_status = "healthy" if (db_ok and redis_ok) else "degraded"
    return {
        "service": settings.service_name,
        "status": overall_status,
        "environment": settings.app_env,
        "dependencies": {
            "postgres": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
    }


@app.post("/api/v1/audit-logs", response_model=AuditLogResponse, status_code=201)
async def create_audit_log(
    payload: AuditLogCreate,
    db: AsyncSession = Depends(get_db),
) -> AuditLog:
    """Create and persist a new audit log record."""
    log_entry = AuditLog(**payload.model_dump())
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)
    return log_entry


@app.get("/api/v1/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    """Return recent audit log entries ordered by newest first."""
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())

@app.get("/api/v1/system/health")
async def system_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Aggregate health status of audit_health_service, Postgres, Redis, and other services."""
    base_health = await health_check(db=db)
    service_endpoints = {
        "api_gateway": "http://127.0.0.1:8000/health",
        "shipment_service": "http://127.0.0.1:8002/health",
        "vessel_service": "http://127.0.0.1:8003/health",
        "history_alert_service": "http://127.0.0.1:8004/health",
    }

    microservices_status: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in service_endpoints.items():
            try:
                resp = await client.get(url)
                microservices_status[name] = "up" if resp.status_code == 200 else "down"
            except Exception:
                microservices_status[name] = "down"

    return {
        "audit_health_service": base_health,
        "microservices": microservices_status,
    }