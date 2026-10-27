import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    """Accès aux messages PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def history(self, conversation_id: uuid.UUID) -> Sequence[Message]:
        """Historique complet d'une conversation, dans l'ordre chronologique."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def list_for_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()

    async def add(
        self,
        *,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Message:
        # `created_at` est fixé côté application : le `now()` PostgreSQL est
        # l'heure de *début de transaction*, donc le message utilisateur et la
        # réponse de l'assistant (même transaction) auraient un horodatage
        # identique et l'ordre chronologique ne serait plus garanti.
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        self.session.add(message)
        await self.session.flush()
        return message
