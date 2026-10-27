from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationRead(BaseModel):
    """Métadonnées d'une conversation (sans ses messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None = Field(default=None, description="Titre facultatif de la conversation.")
    created_at: datetime
    updated_at: datetime
