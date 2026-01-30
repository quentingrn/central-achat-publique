from modules.discovery_compare.application.settings import get_discovery_compare_settings


def test_settings_without_env_files(monkeypatch, tmp_path) -> None:
    with monkeypatch.context() as mp:
        mp.chdir(tmp_path)
        mp.delenv("MISTRAL_MODEL", raising=False)
        # Ensure no error on instantiation even if env files are missing.
        settings = get_discovery_compare_settings()
        assert settings.mistral_model == "mistral-large-latest"


def test_env_local_overrides_env(monkeypatch, tmp_path) -> None:
    (tmp_path / ".env").write_text("MISTRAL_MODEL=from-env\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("MISTRAL_MODEL=from-local\n", encoding="utf-8")

    with monkeypatch.context() as mp:
        mp.chdir(tmp_path)
        mp.delenv("MISTRAL_MODEL", raising=False)
        settings = get_discovery_compare_settings()
        assert settings.mistral_model == "from-local"

        mp.setenv("MISTRAL_MODEL", "from-process")
        settings = get_discovery_compare_settings()
        assert settings.mistral_model == "from-process"
