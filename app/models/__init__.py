"""Modèles SQLAlchemy.

Important : chaque module de modèles doit être importé ici pour être enregistré
dans `Base.metadata` (sinon Alembic ne le voit pas).
"""

from app.models.conversation import Conversation
from app.models.message import Message

__all__ = ["Conversation", "Message"]
