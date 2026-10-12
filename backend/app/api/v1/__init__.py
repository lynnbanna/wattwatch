from fastapi import APIRouter

from app.api.v1 import health, roof_analysis

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(roof_analysis.router)
