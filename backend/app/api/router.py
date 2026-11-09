from fastapi import APIRouter
from backend.app.api.endpoints import health, datasets, scenarios, sensors, telemetry, quality, diagnostics, ml, recommendations, adaptation

from backend.app.api.endpoints import domain_shift_07, investigator_v1, virtual_sensor_research, field_evidence, transfer_trace_15
api_router = APIRouter()
api_router.include_router(investigator_v1.router)
api_router.include_router(virtual_sensor_research.router)
api_router.include_router(domain_shift_07.router)
api_router.include_router(field_evidence.router)
api_router.include_router(transfer_trace_15.router)
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(datasets.router, tags=["Datasets"])
api_router.include_router(scenarios.router, tags=["Scenarios"])
api_router.include_router(sensors.router, tags=["Sensors"])
api_router.include_router(telemetry.router, tags=["Telemetry"])
api_router.include_router(quality.router, tags=["Data Quality"])
api_router.include_router(diagnostics.router, tags=["Diagnostics"])
api_router.include_router(ml.router, tags=["Virtual Sensor & ML"])
api_router.include_router(recommendations.router, tags=["Sensor Recommendations & Research"])
api_router.include_router(adaptation.router, tags=["Domain Adaptation (CSIRO)"])
