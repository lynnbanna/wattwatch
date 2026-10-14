from fastapi import APIRouter

from app.api.v1 import analyses, health, roof_analysis, roof_measurements

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(roof_analysis.router)
router.include_router(roof_measurements.router)
router.include_router(analyses.router)
