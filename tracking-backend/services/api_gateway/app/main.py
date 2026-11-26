from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi import FastAPI

# Allow importing the root `shared` package from any service directory
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from shared.constants import build_health_payload  # noqa: E402

SERVICE_NAME = os.getenv("SERVICE_NAME", "api_gateway")
APP_ENV = os.getenv("APP_ENV", "development")

app = FastAPI(title=f"{SERVICE_NAME} Health", version="0.1.0")


@app.get("/health")
async def health_check() -> dict:
    """Return standard health status for this microservice."""
    return build_health_payload(
        service_name=SERVICE_NAME,
        app_env=APP_ENV,
        dependencies={},
    )