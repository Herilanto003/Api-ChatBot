import pytest
from httpx import AsyncClient

from app.core.config import get_settings


async def test_openapi_exposes_chatbot_routes(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths["/api/v1/chat"]) == {"post"}
    assert set(paths["/api/v1/conversations"]) == {"get"}
    assert set(paths["/api/v1/conversations/{conversation_id}"]) == {"get"}
    assert set(paths["/api/v1/conversations/{conversation_id}/messages"]) == {"get"}


async def test_swagger_ui_is_available(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200


async def test_response_schemas(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/chat",
        json={"message": "Bonjour", "conversation_id": None},
    )
    assert created.status_code == 200
    body = created.json()
    assert set(body) == {"conversation_id", "response", "created_at"}
    conversation_id = body["conversation_id"]

    listed = (await client.get("/api/v1/conversations")).json()
    assert set(listed[0]) == {"id", "title", "created_at", "updated_at"}

    details = (await client.get(f"/api/v1/conversations/{conversation_id}")).json()
    assert set(details) == {"id", "title", "created_at", "updated_at"}

    messages = (await client.get(f"/api/v1/conversations/{conversation_id}/messages")).json()
    assert len(messages) == 2
    assert set(messages[0]) == {"id", "role", "content", "created_at"}
    assert {message["role"] for message in messages} == {"user", "assistant"}


async def test_health_and_hello_still_work(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/health")).json() == {"status": "ok"}
    assert (await client.get("/api/v1/hello")).json() == {"message": "Hello World"}


async def test_api_key_is_never_exposed(client: AsyncClient) -> None:
    api_key = get_settings().openrouter_api_key
    if not api_key:
        pytest.skip("Aucune clé OpenRouter configurée dans cet environnement.")

    for path in ("/openapi.json", "/api/v1/health", "/api/v1/conversations"):
        response = await client.get(path)
        assert api_key not in response.text
