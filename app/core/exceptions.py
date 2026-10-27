"""Exceptions métier de l'application.

Elles sont traduites en réponses HTTP par les handlers de `app.main`.
"""

import uuid


class ConversationNotFoundError(LookupError):
    """La conversation demandée n'existe pas."""

    def __init__(self, conversation_id: uuid.UUID) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"Conversation {conversation_id} introuvable")


class AssistantUnavailableError(RuntimeError):
    """Le service IA est mal configuré (clé absente, configuration invalide)."""


class AssistantProviderError(RuntimeError):
    """Le fournisseur IA a échoué (réseau, quota, réponse invalide)."""
