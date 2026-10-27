from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("")
def health() -> HealthResponse:
    """Liveness : l'application répond (pas de vérification de la base)."""
    return HealthResponse(status="ok")
