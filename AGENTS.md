# AGENTS.md

API de chatbot : **FastAPI + SQLAlchemy 2 async + PostgreSQL + Alembic + LangChain/OpenRouter**.
Point d'entrée : `app.main:app`. Pas de build, pas de front, pas de package secondaire.

## Commandes (PowerShell, depuis la racine)

```powershell
# Activer le venv (ou préfixer chaque commande par .\.venv\Scripts\python.exe)
Set-ExecutionPolicy -Scope Process RemoteSigned; .\.venv\Scripts\Activate.ps1

python -m uvicorn app.main:app --reload        # serveur dev (docs : /docs)
python -m pytest -q                            # suite complète (40 tests, ~15 s)
python -m pytest tests/test_chat.py::test_history_is_complete_without_duplicate -q
python -m ruff check .
python -m ruff format --check .                # formateur = ruff, line-length 100
python -m alembic upgrade head
python -m alembic check                        # doit dire "No new upgrade operations detected."
```

- `alembic` journalise sur **stderr** : PowerShell affiche « NativeCommandError » même en cas de succès. Se fier à la dernière ligne / `$LASTEXITCODE`.
- Ordre usuel avant de rendre : `pytest` → `ruff check` → `ruff format --check` → `alembic check` (si modèles touchés).

## Tests

- Ils exigent **un PostgreSQL local joignable** via `DATABASE_URL` du `.env` (pas de Docker, pas de SQLite, pas de mock DB). Sans base, la session pytest échoue d'entrée.
- `tests/conftest.py` crée un schéma jetable `test_<hex>` et le supprime à la fin ; le schéma `public` n'est **jamais** touché. Tables vidées avant/après chaque test.
- L'assistant réel est remplacé par `FakeAssistant` via `dependency_overrides` : aucun appel réseau, aucune clé API requise. Ne jamais introduire de test appelant réellement OpenRouter ou wttr.in.
- `asyncio_mode = "auto"` : les tests `async def` n'ont pas besoin de marker.
- Le client de test utilise `raise_app_exceptions=False` pour pouvoir tester le handler 500.
- Exemple de test unitaire DB-free : `tests/test_assistant.py`.

## Architecture (pièges à connaître)

- `ChatService` (`app/services/chat.py`) **possède la transaction** : rollback si le provider IA échoue, commit après persistance de la réponse. La couche assistant ne touche jamais à la session SQLAlchemy.
- L'historique est relu **après** l'insertion du message utilisateur : il contient déjà ce message une seule fois. Ne pas le rajouter manuellement à la liste envoyée à l'agent.
- `MessageRepository.add` fixe `created_at = datetime.now(UTC)` en Python **volontairement** : `now()` PostgreSQL = début de transaction, donc user et assistant auraient le même timestamp et l'ordre serait instable. Ne pas revenir à un server_default.
- Les GET passent par `ConversationService`, sans dépendance assistant : ils ne doivent jamais initialiser le LLM.
- Dans `app/api/v1/routes/conversations.py`, la route `/{conversation_id}/messages` doit rester **avant** `/{conversation_id}`.
- Toute nouvelle route doit être branchée dans `app/api/v1/router.py`.
- Les exceptions métier sont dans `app/core/exceptions.py` et traduites en HTTP dans `app/main.py` : `ConversationNotFoundError` → 404, `AssistantProviderError` → 502, `AssistantUnavailableError` → 503, fallback → 500 générique (aucune stack trace au client).
- `POST /chat` répond **200** (pas 201) ; les listes sont des tableaux JSON bruts (pas d'enveloppe de pagination).
- Le schéma n'est **jamais** créé par l'application : uniquement `alembic upgrade head`. Ne pas ajouter de `create_all` au démarrage.
- `alembic.ini` a `sqlalchemy.url` vide : `alembic/env.py` l'alimente depuis les settings. Ne pas y mettre d'URL.
- `app/core/config.py` convertit automatiquement `postgresql://` en `+asyncpg` (runtime) ou `+psycopg` (Alembic/scripts).

## Assistant / OpenRouter

- `get_assistant()` est `@lru_cache` : l'agent est construit **une fois par processus**. Ne jamais l'instancier par requête. Après modification de `.env` ou du modèle, redémarrer le process (le cache de settings et d'agent ne se rafraîchit pas).
- `OPENROUTER_MODEL` inclut le préfixe `openrouter:` (retiré avant `ChatOpenRouter`). Défaut : `openrouter:nvidia/nemotron-3.5-lightning:free`, gratuit et compatible tool calling.
- `minimax/minimax-m3.1-flash:free` a été retiré par OpenRouter le 22/10/2026 (cause des 502 passés). La variante payante `minimax/minimax-m3.1-flash` exige le plafond `OPENROUTER_MAX_TOKENS` (défaut 2048) : sans lui, OpenRouter refuse la requête (`PaymentRequired`, contexte maximal provisionné).
- La clé n'est jamais renvoyée ni journalisée : `sanitize_secret()` masque `OPENROUTER_API_KEY` dans les logs d'erreur provider. `get_assistant` injecte la clé dans `os.environ` car `langchain-openrouter` la lit là.
- Clé absente → 503 ; échec provider/quota/réseau → 502. Ne pas exposer le message d'erreur brut au client.
- `app/tools/weather.py` fait un appel HTTP **synchrone** à wttr.in : ne pas l'appeler dans les tests.

## Environnement / poste

- `.env` (ignoré par git) doit contenir `DATABASE_URL` et `OPENROUTER_API_KEY` ; `.env.example` est la référence versionnée. Ne jamais commiter ni afficher la clé.
- `.env` est chargé par `python-dotenv` via un chemin **absolu** (`ENV_FILE` dans `app/core/config.py`) : il fonctionne même si le process démarre depuis un autre répertoire. Les variables déjà définies dans le shell priment sur `.env` (`override=False`).
- SQLAlchemy est installé en **pur Python** : la politique Windows de contrôle d'application bloque ses DLL natives. Réinstaller avec `$env:DISABLE_SQLALCHEMY_CEXT='1'` et `--no-binary sqlalchemy` ; ne pas réintroduire d'extension C.
- Python 3.13 ; `pytest-asyncio` en mode auto.
- La console Windows (cp1252) plante sur certains caractères des réponses LLM (ex. `\u202f`). Pour inspecter une réponse : écrire un fichier UTF-8 ou passer par `ascii()`.
- `.agents/` contient des skills tierces (documentation) exclues de ruff : ne pas les modifier ni les traiter comme du code applicatif.
