import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "canonical,legacy,expected",
    [
        ("qwen-plus", None, "qwen-plus"),
        (None, "legacy-model", "legacy-model"),
        ("qwen-plus", "legacy-model", "qwen-plus"),
        ("", "legacy-model", "legacy-model"),
        ("  ", "legacy-model", "legacy-model"),
        (None, None, ""),
    ],
)
def test_model_environment_aliases(monkeypatch, canonical, legacy, expected):
    for name, value in [("QWEN_CHAT_MODEL", canonical), ("QWEN_MODEL", legacy)]:
        if value is not None:
            monkeypatch.setenv(name, value)
    assert Settings(_env_file=None).qwen_model == expected


def test_dotenv_canonical_precedence_and_base_url(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "QWEN_CHAT_MODEL=qwen-plus\nQWEN_MODEL=legacy-model\n"
        "DASHSCOPE_API_KEY=fake-test-marker\n"
        "DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1\n"
    )
    settings = Settings(_env_file=env_file)
    assert settings.qwen_model == "qwen-plus"
    assert settings.model_ready
    assert settings.dashscope_base_url == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    assert "fake-test-marker" not in repr(settings)


def test_model_aliases_across_configuration_sources(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("QWEN_CHAT_MODEL=qwen-plus\n")
    monkeypatch.setenv("QWEN_MODEL", "legacy-process-model")
    assert Settings(_env_file=env_file).qwen_model == "qwen-plus"
    monkeypatch.setenv("QWEN_CHAT_MODEL", "canonical-process-model")
    assert Settings(_env_file=env_file).qwen_model == "canonical-process-model"


def test_empty_base_url_keeps_compatible_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DASHSCOPE_BASE_URL=\n")
    assert Settings(_env_file=env_file).dashscope_base_url == Settings(_env_file=None).dashscope_base_url


def test_existing_internal_model_argument_is_preserved(monkeypatch):
    monkeypatch.setenv("QWEN_CHAT_MODEL", "environment-model")
    assert Settings(_env_file=None, qwen_model="test-model").qwen_model == "test-model"
