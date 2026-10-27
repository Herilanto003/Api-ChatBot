from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant"]


class MessageRead(BaseModel):
    """Message d'une conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole = Field(description="Auteur du message : `user` ou `assistant`.")
    content: str
    created_at: datetime
