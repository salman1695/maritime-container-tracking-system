# Maritime & Container Tracking System

A commercial-grade shipment (BL/MBL and container) and terrestrial vessel tracking platform built on a modular microservice architecture. Designed for standalone tracking workflows as well as direct integration into **LogiTrack ERP** (`Job Details -> Shipment Tracking`).

## Current Progress & Roadmap Status

- **Phase 1 — Foundation, Docker Infra, Health & Audit Log:** **Completed** (`tracking_postgres` and `tracking_redis` Docker infrastructure, `shared/` package, and `audit_health_service` on `:8001` with `/health` and PostgreSQL audit logs).
- **Phase 2 — Shipment Tracking (SafeCube API):** **Completed** (BL/MBL and container lookup via `shipment_service` on `:8002`, Redis caching with `force_refresh`, normalized 8-step journey timeline, dynamic multi-container list, and route map coordinates).
- **Phase 3 — Vessel Tracking (AISStream — Terrestrial Only):** Next up (`vessel_service` on `:8003`).
- **Phase 4 — History & Real-Time Alerts (SafeCube Webhook):** Planned (`history_alert_service` on `:8004`).
- **Phase 5 — Frontend Application:** Planned (`tracking-frontend/`).
- **Phase 6 — LogiTrack ERP Integration & Hardening:** Planned (`api_gateway` on `:8000` and ERP tab integration).

## Core Capabilities

- **Shipment Tracking (SafeCube REST API & Webhooks):** Lookup by BL/MBL number or container number with optional/auto-detected sealine, origin-destination route details, ETD/ETA, dynamic container lists, map view payload, and a normalized 8-step journey timeline (`Completed`, `In Progress`, `Pending`).
- **Vessel Tracking (AISStream — Terrestrial Only):** Single-vessel lookup by vessel name, IMO, or MMSI providing live coordinates, speed, course, navigation status, port schedule, and explicit out-of-range detection when outside terrestrial AIS coverage.
- **History & Real-Time Alerts:** Deduplicated search history persisted in PostgreSQL and webhook-driven alerts for milestone updates and ETA changes.
- **Health Monitoring & Audit Trail:** Standardized `/health` endpoints across all microservices, centralized system health aggregation, and PostgreSQL audit logging for lookups, API calls, webhooks, and errors.

## System Architecture & Repository Structure

```text
Maritime & Container Tracking System/
├── README.md
├── tracking-backend/
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── shared/                   # Common constants, health builders & async audit helpers
│   └── services/
│       ├── api_gateway/          # Central entry point & routing (:8000)
│       ├── audit_health_service/ # System health aggregator & audit logs (:8001)
│       ├── shipment_service/     # SafeCube shipment & container tracking (:8002)
│       ├── vessel_service/       # AISStream terrestrial vessel telemetry (:8003)
│       └── history_alert_service/# Deduplicated history & webhook alerts (:8004)
└── tracking-frontend/            # Standalone & ERP-embeddable UI (Planned - Phase 5)