import asyncio
import uuid
from datetime import datetime

from httpx import AsyncClient

from tests.conftest import FakeAssistant

CONVERSATIONS_URL = "/api/v1/conversations"


async def create_conversation(client: AsyncClient, message: str = "Bonjour") -> str:
    response = await client.post("/api/v1/chat", json={"message": message})
    assert response.status_code == 200
    return response.json()["conversation_id"]


async def test_list_conversations_is_empty_initially(client: AsyncClient) -> None:
    response = await client.get(CONVERSATIONS_URL)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_conversations_is_sorted_by_updated_at_desc(client: AsyncClient) -> None:
    conversation_ids = []
    for index in range(3):
        conversation_ids.append(await create_conversation(client, f"Message {index}"))
        await asyncio.sleep(0.01)

    response = await client.get(CONVERSATIONS_URL)

    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == list(reversed(conversation_ids))
    assert set(items[0]) == {"id", "title", "created_at", "updated_at"}

    # Un nouveau message sur la plus ancienne la fait remonter en tête.
    await client.post(
        "/api/v1/chat",
        json={"message": "Relance", "conversation_id": conversation_ids[0]},
    )
    response = await client.get(CONVERSATIONS_URL)
    assert [item["id"] for item in response.json()] == [
        conversation_ids[0],
        conversation_ids[2],
        conversation_ids[1],
    ]


async def test_list_conversations_pagination(client: AsyncClient) -> None:
    conversation_ids = []
    for index in range(3):
        conversation_ids.append(await create_conversation(client, f"Message {index}"))
        await asyncio.sleep(0.01)

    response = await client.get(CONVERSATIONS_URL, params={"limit": 2, "offset": 1})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        conversation_ids[1],
        conversation_ids[0],
    ]


async def test_list_conversations_rejects_invalid_pagination(client: AsyncClient) -> None:
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        response = await client.get(CONVERSATIONS_URL, params=params)
        assert response.status_code == 422


async def test_get_conversation_details(client: AsyncClient) -> None:
    conversation_id = await create_conversation(client, "Explique-moi FastAPI")

    response = await client.get(f"{CONVERSATIONS_URL}/{conversation_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "title", "created_at", "updated_at"}
    assert body["id"] == conversation_id
    assert body["title"] == "Explique-moi FastAPI"
    assert "messages" not in body


async def test_get_unknown_conversation_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"{CONVERSATIONS_URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation introuvable."}


async def test_invalid_conversation_id_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{CONVERSATIONS_URL}/pas-un-uuid")

    assert response.status_code == 422


async def test_messages_are_chronological(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
) -> None:
    conversation_id = await create_conversation(client, "Premier message")
    await client.post(
        "/api/v1/chat",
        json={"message": "Deuxième message", "conversation_id": conversation_id},
    )

    response = await client.get(f"{CONVERSATIONS_URL}/{conversation_id}/messages")

    assert response.status_code == 200
    messages = response.json()
    assert set(messages[0]) == {"id", "role", "content", "created_at"}
    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert [message["content"] for message in messages] == [
        "Premier message",
        fake_assistant.reply_text,
        "Deuxième message",
        fake_assistant.reply_text,
    ]
    timestamps = [datetime.fromisoformat(message["created_at"]) for message in messages]
    assert timestamps == sorted(timestamps)


async def test_messages_pagination(
    client: AsyncClient,
    fake_assistant: FakeAssistant,
) -> None:
    conversation_id = await create_conversation(client, "Premier message")
    await client.post(
        "/api/v1/chat",
        json={"message": "Deuxième message", "conversation_id": conversation_id},
    )

    response = await client.get(
        f"{CONVERSATIONS_URL}/{conversation_id}/messages",
        params={"limit": 2, "offset": 2},
    )

    assert response.status_code == 200
    assert [message["content"] for message in response.json()] == [
        "Deuxième message",
        fake_assistant.reply_text,
    ]


async def test_messages_of_unknown_conversation_return_404(client: AsyncClient) -> None:
    response = await client.get(f"{CONVERSATIONS_URL}/{uuid.uuid4()}/messages")

    assert response.status_code == 404
    assert response.json() == {"detail": "Conversation introuvable."}


async def test_conversations_are_isolated(client: AsyncClient) -> None:
    first_id = await create_conversation(client, "Conversation A")
    second_id = await create_conversation(client, "Conversation B")

    first_messages = (await client.get(f"{CONVERSATIONS_URL}/{first_id}/messages")).json()
    second_messages = (await client.get(f"{CONVERSATIONS_URL}/{second_id}/messages")).json()

    assert [message["content"] for message in first_messages][0] == "Conversation A"
    assert [message["content"] for message in second_messages][0] == "Conversation B"
    assert len(first_messages) == 2
    assert len(second_messages) == 2
