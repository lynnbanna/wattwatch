from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_ok = db.check_database()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=get_settings().version,
        database="ok" if db_ok else "unavailable",
    )
