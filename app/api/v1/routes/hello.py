from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/hello", tags=["hello"])


class HelloResponse(BaseModel):
    message: str


@router.get("")
def hello() -> HelloResponse:
    """Endpoint de démonstration Hello World."""
    return HelloResponse(message="Hello World")
