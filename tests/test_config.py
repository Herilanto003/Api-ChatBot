"""Chargement de la configuration depuis `.env` (python-dotenv + pydantic-settings)."""

from app.core.config import ENV_FILE, PROJECT_ROOT, Settings


def test_env_file_is_resolved_from_project_root() -> None:
    """`.env` est cherché à la racine du projet, pas dans le répertoire courant."""
    assert ENV_FILE == PROJECT_ROOT / ".env"
    assert ENV_FILE.is_absolute()
    assert ENV_FILE.is_file()
    assert Settings.model_config["env_file"] == ENV_FILE


def test_settings_read_dotenv_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'APP_NAME="Depuis dotenv"\nOPENROUTER_MODEL=openrouter:test/model:free\n',
        encoding="utf-8",
    )
    # Les variables du shell priment sur `.env` : on isole le test.
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "Depuis dotenv"
    assert settings.openrouter_model == "openrouter:test/model:free"
