from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Message envoyé à l'assistant."""

    message: str = Field(
        min_length=1,
        max_length=10_000,
        description="Message de l'utilisateur (les espaces de début et de fin sont supprimés).",
        examples=["Explique-moi FastAPI"],
    )
    conversation_id: UUID | None = Field(
        default=None,
        description=(
            "Conversation existante à poursuivre. "
            "Omis ou `null` : une nouvelle conversation est créée."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le message ne doit pas être vide.")
        return value


class ChatResponse(BaseModel):
    """Réponse de l'assistant, persistée dans la conversation."""

    conversation_id: UUID = Field(description="Identifiant de la conversation utilisée.")
    response: str = Field(description="Réponse finale générée par l'assistant.")
    created_at: datetime = Field(description="Date de création du message assistant.")
