"""The outlines an analysis currently uses: the user's corrections, or the model's."""

import hashlib
import json

from app.models import Analysis

Polygons = list[list[tuple[float, float]]]


def current_outlines(analysis: Analysis) -> tuple[Polygons, Polygons, bool]:
    """(roofs, obstacles, uses_corrections) as pixel polygons."""
    source = analysis.corrections or analysis.result
    roofs = [r["polygon_px"] for r in source["roofs"]]
    obstacles = [o["polygon_px"] for o in source["obstacles"]]
    return roofs, obstacles, analysis.corrections is not None


def outline_hash(roofs: Polygons, obstacles: Polygons) -> str:
    """Fingerprint of the outlines, to tell whether a design used the current ones."""
    payload = json.dumps([roofs, obstacles], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
