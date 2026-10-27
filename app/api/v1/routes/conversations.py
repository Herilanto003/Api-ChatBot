import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import DbSession
from app.schemas.conversation import ConversationRead
from app.schemas.message import MessageRead
from app.services.conversations import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])

LimitQuery = Annotated[
    int,
    Query(ge=1, le=100, description="Nombre maximum d'éléments retournés (1 à 100)."),
]
OffsetQuery = Annotated[
    int,
    Query(ge=0, description="Nombre d'éléments à ignorer (pagination)."),
]
ConversationIdPath = Annotated[
    uuid.UUID,
    Path(description="Identifiant UUID de la conversation."),
]


@router.get(
    "",
    summary="Lister les conversations",
    description=(
        "Retourne les métadonnées des conversations (sans le contenu des messages), "
        "triées par date de dernière modification décroissante."
    ),
)
async def list_conversations(
    session: DbSession,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
) -> list[ConversationRead]:
    conversations = await ConversationService(session).list_conversations(
        limit=limit,
        offset=offset,
    )
    return [ConversationRead.model_validate(conversation) for conversation in conversations]


@router.get(
    "/{conversation_id}/messages",
    summary="Lister les messages d'une conversation",
    description=(
        "Retourne les messages d'une conversation, dans l'ordre chronologique "
        "(du plus ancien au plus récent)."
    ),
    responses={404: {"description": "Conversation introuvable."}},
)
async def list_messages(
    session: DbSession,
    conversation_id: ConversationIdPath,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> list[MessageRead]:
    messages = await ConversationService(session).list_messages(
        conversation_id,
        limit=limit,
        offset=offset,
    )
    return [MessageRead.model_validate(message) for message in messages]


@router.get(
    "/{conversation_id}",
    summary="Consulter une conversation",
    description=(
        "Retourne les métadonnées d'une conversation (identifiant, titre et dates). "
        "Les messages sont disponibles via `GET /conversations/{conversation_id}/messages`."
    ),
    responses={404: {"description": "Conversation introuvable."}},
)
async def get_conversation(
    session: DbSession,
    conversation_id: ConversationIdPath,
) -> ConversationRead:
    conversation = await ConversationService(session).get_conversation(conversation_id)
    return ConversationRead.model_validate(conversation)
