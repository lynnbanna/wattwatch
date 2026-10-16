from fastapi import APIRouter

from app.api.v1 import analyses, energy, health, roof_analysis, roof_measurements, solar

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(roof_analysis.router)
router.include_router(roof_measurements.router)
router.include_router(analyses.router)
router.include_router(solar.router)
router.include_router(energy.router)
