import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository


class ConversationService:
    """Consultation des conversations et de leurs messages (lecture seule)."""

    def __init__(self, session: AsyncSession) -> None:
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def list_conversations(self, *, limit: int, offset: int) -> Sequence[Conversation]:
        return await self.conversations.list(limit=limit, offset=offset)

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[Message]:
        await self.get_conversation(conversation_id)
        return await self.messages.list_for_conversation(
            conversation_id,
            limit=limit,
            offset=offset,
        )
