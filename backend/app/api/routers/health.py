"""Unauthenticated liveness probe.

Deliberately exempt from ``require_api_token`` -- used as the handoff smoke
check and as an unauthenticated liveness probe for local tooling.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Response shape for the liveness probe."""

    status: str


@router.get("/health", summary="Liveness probe")
async def get_health() -> HealthStatus:
    """Return a simple OK status. Never requires the bearer token."""
    return HealthStatus(status="ok")
