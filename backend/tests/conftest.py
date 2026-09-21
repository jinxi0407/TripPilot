import httpx
import pytest

from app.core.config import Settings

# Disable dotenv before test-module collection imports app.main's module-level app.
Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.delenv("QWEN_CHAT_MODEL", raising=False)


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    async def forbidden(self, request):
        raise AssertionError("单元测试禁止真实 HTTP；请使用 MockTransport 或 ASGITransport")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
