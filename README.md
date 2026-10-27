# Chatbot API

API de chatbot — **FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Alembic**.

## Stack

| Composant | Rôle |
|---|---|
| FastAPI | API HTTP, docs OpenAPI |
| SQLAlchemy 2 (async) | ORM, sessions `AsyncSession` |
| asyncpg | Driver PostgreSQL asynchrone (runtime) |
| psycopg 3 | Driver PostgreSQL synchrone (Alembic offline) |
| Alembic | Migrations de schéma |
| LangChain | Agent conversationnel (`create_agent`) |
| OpenRouter | Fournisseur du modèle `nvidia/nemotron-3.5-lightning:free` |

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **Spécificité de ce poste** : la politique de contrôle d'application Windows
> bloque les DLL natives de SQLAlchemy. Installer la version pure Python :
>
> ```powershell
> $env:DISABLE_SQLALCHEMY_CEXT='1'
> pip install --no-binary sqlalchemy "sqlalchemy[asyncio]>=2.0"
> ```

## Configuration

```powershell
Copy-Item .env.example .env
# puis renseigner DATABASE_URL
```

Format attendu (le driver est ajouté automatiquement par `app/core/config.py`) :

```
DATABASE_URL="postgresql://user:password@localhost:5432/chatbot"
OPENROUTER_API_KEY="sk-or-..."
```

`OPENROUTER_MODEL` est facultatif. Valeur par défaut :
`openrouter:nvidia/nemotron-3.5-lightning:free` (gratuit, tool calling).

Le fichier `.env` est chargé par `python-dotenv` depuis la **racine du projet**
(`app/core/config.py`), quel que soit le répertoire depuis lequel l'application
est lancée. Les variables déjà définies dans le shell priment sur `.env`.

> **Changement de modèle** : `minimax/minimax-m3.1-flash:free` a été retiré par
> OpenRouter le 22/10/2026 (fin de la période de lancement), ce qui provoquait
> des `502`. Pour utiliser la variante payante, définir
> `OPENROUTER_MODEL=openrouter:minimax/minimax-m3.1-flash` ; `OPENROUTER_MAX_TOKENS`
> (défaut `2048`) doit rester plafonné, sinon OpenRouter refuse la requête
> (« PaymentRequired ») faute de crédits pour le contexte maximal.

## Base de données

Le schéma **n'est jamais** créé par l'application au démarrage : uniquement par Alembic.

```powershell
alembic upgrade head      # appliquer les migrations
alembic downgrade -1      # revenir d'une migration
alembic current           # version appliquée
alembic history           # historique
alembic revision --autogenerate -m "message"
```

### Modèle

- `conversations` : `id` (UUID), `title`, `created_at`, `updated_at`
- `messages` : `id` (UUID), `conversation_id` (FK → `conversations.id`, `ON DELETE CASCADE`),
  `role` (`user` | `assistant`), `content`, `created_at`

## Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/v1/chat` | Envoyer un message à l'assistant (crée ou poursuit une conversation) |
| `GET` | `/api/v1/conversations` | Lister les conversations (`limit`, `offset`), triées par `updated_at` décroissant |
| `GET` | `/api/v1/conversations/{conversation_id}` | Métadonnées d'une conversation |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Messages d'une conversation (`limit`, `offset`), ordre chronologique |

Exemple :

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{\"message\": \"Explique-moi FastAPI\", \"conversation_id\": null}'
```

```json
{
  "conversation_id": "7d7c6d11-34f2-4d1a-9e8a-1f8b5f09d120",
  "response": "FastAPI est un framework Python...",
  "created_at": "2026-10-27T12:00:00.123456+00:00"
}
```

Erreurs : `422` (corps invalide), `404` (conversation inconnue), `502` (fournisseur IA en
échec), `503` (assistant non configuré), `500` (erreur interne, message générique).
En cas d'échec IA, la transaction est annulée : aucune réponse fictive ni message
utilisateur orphelin n'est conservé.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

Les tests utilisent un schéma PostgreSQL temporaire (`test_<hex>`, créé puis supprimé)
et un assistant simulé : aucun appel réseau, aucune clé API requise. Le schéma `public`
n'est jamais modifié.

## Lancer en développement

```powershell
fastapi dev
# ou
uvicorn app.main:app --reload
```

- Docs : http://127.0.0.1:8000/docs
- Health : http://127.0.0.1:8000/api/v1/health
- Hello : http://127.0.0.1:8000/api/v1/hello

## Structure

```
app/
  main.py                  # app factory, lifespan, CORS, handlers d'erreurs
  core/
    config.py              # settings (pydantic-settings)
    exceptions.py          # exceptions métier (404 / 502 / 503)
  db/
    base.py                # DeclarativeBase + convention de nommage
    session.py             # engine async, session factory, get_db
  api/
    deps.py                # dépendances partagées (DbSession)
    v1/router.py           # agrégation des routers v1
    v1/routes/chat.py      # POST /chat
    v1/routes/conversations.py  # GET /conversations...
    v1/routes/health.py    # healthcheck
    v1/routes/hello.py     # hello world
  models/                  # modèles SQLAlchemy
  repositories/            # accès aux données (conversations, messages)
  schemas/                 # schémas Pydantic (entrées / sorties HTTP)
  services/
    assistant.py           # agent LangChain + OpenRouter (initialisé une fois)
    chat.py                # orchestration d'un échange (transaction)
    conversations.py       # lecture des conversations / messages
  tools/weather.py         # outil `get_information_weather` (réutilisé d'API_WEATHER)
tests/
  conftest.py              # schéma isolé + assistant simulé
  test_api.py              # routes OpenAPI, schémas de réponse
  test_chat.py             # POST /chat (création, historique, erreurs, rollback)
  test_conversations.py    # listes, détails, messages, pagination
  test_assistant.py        # conversion LangChain, modèle, outil météo
alembic/
  env.py                   # configuration async
  versions/                # migrations
```
