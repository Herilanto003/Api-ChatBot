"""Agent conversationnel LangChain adossé à OpenRouter.

L'agent est construit une seule fois (cache `lru_cache`) et réutilisé pour
toutes les requêtes. La clé API n'est jamais journalisée ni renvoyée au client.
"""

import logging
import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Protocol

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openrouter import ChatOpenRouter

from app.core.config import get_settings
from app.core.exceptions import AssistantProviderError, AssistantUnavailableError
from app.models.message import Message
from app.tools.weather import get_information_weather

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a helpful assistant"


class Assistant(Protocol):
    """Contrat minimal utilisé par la couche service."""

    async def reply(self, history: Sequence[Message]) -> str: ...


def to_langchain_messages(history: Sequence[Message]) -> list[BaseMessage]:
    """Convertit l'historique PostgreSQL en messages LangChain.

    Seuls les rôles `user` et `assistant` existent en base (contrainte CHECK).
    """
    messages: list[BaseMessage] = []
    for message in history:
        if message.role == "user":
            messages.append(HumanMessage(content=message.content))
        else:
            messages.append(AIMessage(content=message.content))
    return messages


def extract_text(message: Any) -> str:
    """Normalise `AIMessage.content` (chaîne ou liste de blocs) en texte."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


def sanitize_secret(text: str) -> str:
    """Masque la clé OpenRouter avant toute journalisation."""
    secret = os.environ.get("OPENROUTER_API_KEY")
    if secret:
        return text.replace(secret, "***")
    return text


class OpenRouterAgent:
    """Implémentation LangChain de l'assistant (agent + outil météo)."""

    def __init__(self, *, model: str, max_tokens: int | None = None) -> None:
        # `create_agent` accepte aussi une chaîne, mais passer un modèle
        # explicite est le seul moyen de plafonner `max_tokens` : sans plafond,
        # OpenRouter provisionne le contexte maximal et refuse la requête
        # (« PaymentRequired ») dès que les crédits ne suffisent pas.
        chat_model = ChatOpenRouter(
            model=model.split("openrouter:", 1)[-1],
            max_tokens=max_tokens,
        )
        self._agent = create_agent(
            model=chat_model,
            tools=[get_information_weather],
            system_prompt=SYSTEM_PROMPT,
        )

    async def reply(self, history: Sequence[Message]) -> str:
        messages = to_langchain_messages(history)
        if not messages:
            raise AssistantProviderError("Aucun message à transmettre à l'assistant.")

        try:
            result = await self._agent.ainvoke({"messages": messages})
        except Exception as exc:
            # Le détail (réseau, quota, modèle retiré…) reste dans les logs
            # serveur, clé API masquée et texte tronqué.
            logger.warning(
                "Échec de l'appel OpenRouter (%s) : %s",
                type(exc).__name__,
                sanitize_secret(str(exc))[:500],
            )
            logger.debug("Détail de l'erreur OpenRouter", exc_info=True)
            raise AssistantProviderError("Le fournisseur IA a échoué.") from exc

        output = result.get("messages") if isinstance(result, dict) else None
        if not output:
            raise AssistantProviderError("Réponse invalide du fournisseur IA.")

        answer = extract_text(output[-1])
        if not answer:
            raise AssistantProviderError("Réponse vide du fournisseur IA.")
        return answer


@lru_cache
def get_assistant() -> Assistant:
    """Construit l'agent une seule fois pour tout le processus."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise AssistantUnavailableError(
            "OPENROUTER_API_KEY n'est pas configurée : l'assistant est indisponible."
        )

    # `create_agent("openrouter:...")` laisse `langchain-openrouter` lire la clé
    # depuis l'environnement : on la garantit sans jamais l'exposer.
    os.environ.setdefault("OPENROUTER_API_KEY", settings.openrouter_api_key)

    try:
        return OpenRouterAgent(
            model=settings.openrouter_model,
            max_tokens=settings.openrouter_max_tokens,
        )
    except Exception as exc:
        logger.exception("Initialisation de l'agent LangChain impossible")
        raise AssistantUnavailableError("Configuration de l'assistant invalide.") from exc
