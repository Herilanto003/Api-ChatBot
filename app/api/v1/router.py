from fastapi import APIRouter

from app.api.v1.routes import chat, conversations, health, hello

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(hello.router)
api_router.include_router(chat.router)
api_router.include_router(conversations.router)

__all__ = ["api_router"]
