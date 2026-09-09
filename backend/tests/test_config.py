from app.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert settings.app_name == "CryptoTrace"
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.neo4j_username == "neo4j"
    assert settings.neo4j_password == "change_me"


def test_settings_overrides():
    settings = Settings(neo4j_password="secret", api_port=9000)
    assert settings.neo4j_password == "secret"
    assert settings.api_port == 9000


def test_settings_loads_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NEO4J_URI=bolt://custom:7687\nNEO4J_PASSWORD=hunter2\nDATABASE_URL=postgresql+psycopg://db\n"
    )
    settings = Settings(_env_file=str(env_file))
    assert settings.neo4j_uri == "bolt://custom:7687"
    assert settings.neo4j_password == "hunter2"
    assert settings.database_url == "postgresql+psycopg://db"