import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.repositories.conversations import ConversationRepository
from app.repositories.messages import MessageRepository
from app.services.assistant import Assistant

TITLE_MAX_LENGTH = 255


def _title_from(content: str) -> str:
    """Titre par défaut d'une conversation créée via `/chat`."""
    return content[:TITLE_MAX_LENGTH]


class ChatService:
    """Orchestration des échanges conversationnels.

    Le service possède la transaction : la couche assistant ne touche jamais
    à la session PostgreSQL.
    """

    def __init__(self, session: AsyncSession, assistant: Assistant) -> None:
        self.session = session
        self.assistant = assistant
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def send_message(
        self,
        content: str,
        conversation_id: uuid.UUID | None,
    ) -> tuple[Conversation, Message]:
        """Persiste l'échange complet et renvoie la réponse de l'assistant.

        En cas d'échec du fournisseur IA, la transaction est annulée : aucune
        réponse fictive n'est enregistrée et le message utilisateur n'est pas
        laissé orphelin.
        """
        if conversation_id is None:
            conversation = await self.conversations.create(title=_title_from(content))
        else:
            conversation = await self.conversations.get(conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(conversation_id)

        await self.messages.add(
            conversation_id=conversation.id,
            role="user",
            content=content,
        )
        # L'historique est relu après l'insertion : le nouveau message y figure
        # une seule fois, à sa place chronologique.
        history = await self.messages.history(conversation.id)

        try:
            answer = await self.assistant.reply(history)
        except Exception:
            await self.session.rollback()
            raise

        assistant_message = await self.messages.add(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
        )
        await self.conversations.touch(conversation)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(assistant_message)
        await self.session.refresh(conversation)
        return conversation, assistant_message
