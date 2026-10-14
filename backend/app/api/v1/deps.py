"""Shared request dependencies for the v1 API."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db import get_session
from app.models import Analysis

SessionDep = Annotated[Session, Depends(get_session)]


def load_analysis(session: Session, analysis_id: str) -> Analysis:
    try:
        UUID(analysis_id)
    except ValueError:
        analysis = None
    else:
        analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise ApiError(404, "analysis_not_found", "No analysis with this id.")
    return analysis
