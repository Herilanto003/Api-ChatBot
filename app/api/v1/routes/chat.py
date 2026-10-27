from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant import Assistant, get_assistant
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

AssistantDep = Annotated[Assistant, Depends(get_assistant)]


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Envoyer un message à l'assistant",
    description=(
        "Persiste le message de l'utilisateur, transmet l'historique complet de la "
        "conversation (dans l'ordre chronologique) à l'agent LangChain adossé à "
        "OpenRouter, puis enregistre la réponse de l'assistant.\n\n"
        "- Sans `conversation_id` : une nouvelle conversation est créée.\n"
        "- Avec un `conversation_id` inconnu : `404`.\n"
        "- En cas d'échec du fournisseur IA : `502`, sans réponse fictive ni message "
        "utilisateur orphelin.\n"
        "- Assistant non configuré (clé absente) : `503`."
    ),
    responses={
        404: {"description": "Conversation introuvable."},
        502: {"description": "Le fournisseur IA a échoué ou renvoyé une réponse invalide."},
        503: {"description": "L'assistant IA n'est pas configuré ou est indisponible."},
    },
)
async def send_message(
    payload: ChatRequest,
    session: DbSession,
    assistant: AssistantDep,
) -> ChatResponse:
    conversation, message = await ChatService(session, assistant).send_message(
        payload.message,
        payload.conversation_id,
    )
    return ChatResponse(
        conversation_id=conversation.id,
        response=message.content,
        created_at=message.created_at,
    )
