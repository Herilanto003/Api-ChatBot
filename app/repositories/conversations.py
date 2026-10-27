import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    """Accès aux conversations PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list(self, *, limit: int, offset: int) -> Sequence[Conversation]:
        stmt = (
            select(Conversation)
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.created_at.desc(),
                Conversation.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()

    async def create(self, *, title: str | None) -> Conversation:
        conversation = Conversation(title=title)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        """Met à jour `updated_at` avec l'horloge de la base."""
        conversation.updated_at = func.now()
