"""Fixtures de test : schéma PostgreSQL isolé et assistant simulé.

Les tests n'utilisent jamais la clé OpenRouter ni le réseau : l'agent réel est
remplacé par `FakeAssistant` via `app.dependency_overrides[get_assistant]`.
Les données de développement (schéma `public`) ne sont jamais touchées : tout
se passe dans un schéma temporaire `test_<hex>` créé puis supprimé.
"""

import uuid
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Conversation, Message
from app.services.assistant import get_assistant

settings = get_settings()

TEST_SCHEMA = f"test_{uuid.uuid4().hex[:12]}"


class FakeAssistant:
    """Assistant déterministe : enregistre l'historique reçu, ne fait aucun appel."""

    def __init__(self) -> None:
        self.reply_text = "Réponse simulée de l'assistant."
        self.error: Exception | None = None
        self.calls: list[list[tuple[str, str]]] = []

    async def reply(self, history) -> str:
        self.calls.append([(message.role, message.content) for message in history])
        if self.error is not None:
            raise self.error
        return self.reply_text


@pytest.fixture(scope="session", autouse=True)
def test_schema() -> Iterator[None]:
    """Crée un schéma dédié et les tables, puis le supprime à la fin."""
    with psycopg.connect(settings.database_url, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{TEST_SCHEMA}"')

    engine = create_engine(
        settings.sync_database_url,
        connect_args={"options": f"-csearch_path={TEST_SCHEMA}"},
    )
    Base.metadata.create_all(engine)
    engine.dispose()

    try:
        yield
    finally:
        with psycopg.connect(settings.database_url, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE')


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        settings.async_database_url,
        connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
        poolclass=NullPool,
    )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Isole chaque test : tables vides avant et après."""
    async with session_factory() as session:
        await session.execute(delete(Message))
        await session.execute(delete(Conversation))
        await session.commit()
    try:
        yield
    finally:
        async with session_factory() as session:
            await session.execute(delete(Message))
            await session.execute(delete(Conversation))
            await session.commit()


@pytest.fixture
def fake_assistant() -> FakeAssistant:
    return FakeAssistant()


@pytest.fixture
def app(
    session_factory: async_sessionmaker[AsyncSession],
    fake_assistant: FakeAssistant,
) -> FastAPI:
    application = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_assistant] = lambda: fake_assistant
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # `raise_app_exceptions=False` : on teste le handler 500 comme un vrai client.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Session de vérification, indépendante de celle utilisée par l'API."""
    async with session_factory() as session:
        yield session
