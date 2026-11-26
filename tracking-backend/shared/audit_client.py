from __future__ import annotations

import httpx


async def send_audit_log(
    audit_service_url: str,
    service_name: str,
    action: str,
    reference_value: str | None = None,
    status_code: int = 200,
    latency_ms: int | None = None,
    details: str | None = None,
) -> None:
    """Send an audit event to audit_health_service without breaking caller flow."""
    payload = {
        "service_name": service_name,
        "action": action,
        "reference_value": reference_value,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "details": details,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{audit_service_url.rstrip('/')}/api/v1/audit-logs", json=payload)
    except Exception:
        # Never fail primary business requests if audit logging is temporarily unreachable
        pass