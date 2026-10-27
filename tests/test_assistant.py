"""Tests unitaires de la couche assistant (sans réseau ni base)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.config import get_settings
from app.core.exceptions import AssistantProviderError
from app.models.message import Message
from app.services.assistant import (
    SYSTEM_PROMPT,
    OpenRouterAgent,
    extract_text,
    sanitize_secret,
    to_langchain_messages,
)
from app.tools.weather import get_information_weather


def test_to_langchain_messages_maps_roles_and_content() -> None:
    history = [
        Message(role="user", content="Bonjour"),
        Message(role="assistant", content="Salut"),
    ]

    messages = to_langchain_messages(history)

    assert [type(message) for message in messages] == [HumanMessage, AIMessage]
    assert [message.content for message in messages] == ["Bonjour", "Salut"]


def test_extract_text_handles_string_and_blocks() -> None:
    assert extract_text(AIMessage(content="  Bonjour  ")) == "Bonjour"
    assert (
        extract_text(
            AIMessage(
                content=[
                    {"type": "text", "text": "Bonjour "},
                    {"type": "text", "text": "!"},
                ]
            )
        )
        == "Bonjour !"
    )


def test_required_model_and_system_prompt_are_configured() -> None:
    settings = get_settings()
    # Modèle gratuit de remplacement : le `:free` de MiniMax a été retiré.
    assert settings.openrouter_model == "openrouter:nvidia/nemotron-3.5-lightning:free"
    assert settings.openrouter_max_tokens == 2048
    assert SYSTEM_PROMPT == "You are a helpful assistant"


def test_weather_tool_is_reused() -> None:
    assert get_information_weather.name == "get_information_weather"
    assert get_information_weather.description == "Return weather information for a valid city"


def test_agent_can_be_built_offline(monkeypatch) -> None:
    """L'agent doit se construire avec le modèle imposé, sans appel réseau."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    settings = get_settings()

    agent = OpenRouterAgent(
        model=settings.openrouter_model,
        max_tokens=settings.openrouter_max_tokens,
    )

    assert agent is not None


def test_sanitize_secret_hides_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-value")

    assert sanitize_secret("erreur sk-or-secret-value ici") == "erreur *** ici"
    assert sanitize_secret("sans secret") == "sans secret"


async def test_provider_error_is_logged_without_api_key(caplog, monkeypatch) -> None:
    """Un échec fournisseur doit produire un 502 sans fuiter la clé."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-value")
    agent = OpenRouterAgent(model="openrouter:test/model:free", max_tokens=64)

    class FailingAgent:
        async def ainvoke(self, _payload):
            raise RuntimeError("upstream a rejeté sk-or-secret-value")

    agent._agent = FailingAgent()

    with caplog.at_level("WARNING"), pytest.raises(AssistantProviderError) as excinfo:
        await agent.reply([Message(role="user", content="Bonjour")])

    assert "sk-or-secret-value" not in caplog.text
    assert "sk-or-secret-value" not in str(excinfo.value)
    assert "RuntimeError" in caplog.text
