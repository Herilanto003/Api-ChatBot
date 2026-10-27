import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AssistantProviderError, AssistantUnavailableError
from app.models import Conversation, Message
from app.services.assistant import get_assistant
from app.services.chat import ChatService
from tests.conftest import FakeAssistant

CHAT_URL = "/api/v1/chat"


async def test_first_message_creates_conversation(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    response = await client.post(CHAT_URL, json={"message": "  Explique-moi FastAPI  "})

    assert response.status_code == 200
    body = response.json()
    conversation_id = uuid.UUID(body["conversation_id"])
    assert body["response"] == fake_assistant.reply_text
    assert body["created_at"]

    conversation = await db_session.get(Conversation, conversation_id)
    assert conversation is not None
    # Le message est nettoyé de ses espaces avant persistance et sert de titre.
    assert conversation.title == "Explique-moi FastAPI"
    assert conversation.created_at is not None
    assert len(fake_assistant.calls) == 1


async def test_user_and_assistant_messages_are_persisted(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    response = await client.post(CHAT_URL, json={"message": "Bonjour"})
    conversation_id = response.json()["conversation_id"]

    messages = (await db_session.scalars(select(Message).order_by(Message.created_at))).all()

    assert [(message.role, message.content) for message in messages] == [
        ("user", "Bonjour"),
        ("assistant", fake_assistant.reply_text),
    ]
    assert all(str(message.conversation_id) == conversation_id for message in messages)
    assert messages[0].created_at < messages[1].created_at


async def test_second_message_reuses_conversation(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    first = await client.post(CHAT_URL, json={"message": "Bonjour"})
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        CHAT_URL,
        json={"message": "Suite de la discussion", "conversation_id": conversation_id},
    )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert len(fake_assistant.calls) == 2

    conversations = (await db_session.scalars(select(Conversation))).all()
    assert len(conversations) == 1

    messages = (await db_session.scalars(select(Message))).all()
    assert len(messages) == 4


async def test_history_is_complete_without_duplicate(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
) -> None:
    first = await client.post(CHAT_URL, json={"message": "Bonjour"})
    conversation_id = first.json()["conversation_id"]

    question = "Quel temps fait-il à Paris ?"
    await client.post(
        CHAT_URL,
        json={"message": question, "conversation_id": conversation_id},
    )

    assert fake_assistant.calls[0] == [("user", "Bonjour")]
    assert fake_assistant.calls[1] == [
        ("user", "Bonjour"),
        ("assistant", fake_assistant.reply_text),
        ("user", question),
    ]
    sent = [content for _, content in fake_assistant.calls[1]]
    assert sent.count(question) == 1


async def test_unknown_conversation_returns_404(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    unknown_id = uuid.uuid4()

    response = await client.post(
        CHAT_URL,
        json={"message": "Bonjour", "conversation_id": str(unknown_id)},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation introuvable."}
    assert fake_assistant.calls == []
    assert (await db_session.scalars(select(Conversation))).all() == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": None},
        {"message": 123},
        {"message": "Bonjour", "conversation_id": "pas-un-uuid"},
    ],
)
async def test_invalid_body_returns_422(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    payload: dict,
    db_session: AsyncSession,
) -> None:
    response = await client.post(CHAT_URL, json=payload)

    assert response.status_code == 422
    assert fake_assistant.calls == []
    assert (await db_session.scalars(select(Conversation))).all() == []


async def test_provider_error_persists_nothing(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    fake_assistant.error = AssistantProviderError("panne simulée")

    response = await client.post(CHAT_URL, json={"message": "Bonjour"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Le fournisseur IA est momentanément indisponible."}
    assert (await db_session.scalars(select(Conversation))).all() == []
    assert (await db_session.scalars(select(Message))).all() == []


async def test_provider_error_does_not_orphan_user_message(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
    db_session: AsyncSession,
) -> None:
    first = await client.post(CHAT_URL, json={"message": "Bonjour"})
    conversation_id = first.json()["conversation_id"]

    fake_assistant.error = AssistantProviderError("panne simulée")
    response = await client.post(
        CHAT_URL,
        json={"message": "Deuxième question", "conversation_id": conversation_id},
    )

    assert response.status_code == 502
    messages = (await db_session.scalars(select(Message).order_by(Message.created_at))).all()
    assert [(message.role, message.content) for message in messages] == [
        ("user", "Bonjour"),
        ("assistant", fake_assistant.reply_text),
    ]


async def test_assistant_unavailable_returns_503(
    app,
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    def unavailable_assistant():
        raise AssistantUnavailableError("OPENROUTER_API_KEY absente")

    app.dependency_overrides[get_assistant] = unavailable_assistant

    response = await client.post(CHAT_URL, json={"message": "Bonjour"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Le service IA est indisponible."}
    assert (await db_session.scalars(select(Conversation))).all() == []


async def test_unexpected_error_returns_generic_500(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(self, content, conversation_id):
        raise RuntimeError("détail interne à ne pas exposer")

    monkeypatch.setattr(ChatService, "send_message", boom)

    response = await client.post(CHAT_URL, json={"message": "Bonjour"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Une erreur interne est survenue."}
    assert "détail interne" not in response.text
