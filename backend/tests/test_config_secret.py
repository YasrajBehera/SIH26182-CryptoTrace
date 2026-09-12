"""Development token-secret persistence tests.

The dev-only falling secret must survive backend restarts (it lives in a
git-ignored dotfile) and an explicit AUTH_SECRET must always win.
"""

from app.config import Settings


def test_dev_secret_persists_across_calls(tmp_path):
    file = tmp_path / "auth_dev_secret"
    settings = Settings(auth_secret="")
    first = settings.resolved_auth_secret(dev_file=file)
    second = settings.resolved_auth_secret(dev_file=file)
    assert first == second
    assert file.exists()
    assert file.read_text(encoding="utf-8").strip() == first


def test_explicit_auth_secret_wins_over_file(tmp_path):
    file = tmp_path / "auth_dev_secret"
    file.write_text("should-not-be-used\n", encoding="utf-8")
    settings = Settings(auth_secret="chosen-production-secret")
    assert settings.resolved_auth_secret(dev_file=file) == "chosen-production-secret"


def test_blank_secret_file_is_regenerated(tmp_path):
    file = tmp_path / "auth_dev_secret"
    file.write_text("   \n", encoding="utf-8")
    settings = Settings(auth_secret="")
    secret = settings.resolved_auth_secret(dev_file=file)
    assert secret
    assert file.read_text(encoding="utf-8").strip() == secret