import logging

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import SafeJSONFormatter
from app.main import create_app


def test_health_without_keys():
    settings = Settings(_env_file=None, dashscope_api_key="", qwen_model="", amap_api_key="")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"
    assert response.json()["providers"]["rail"] == "mock"


def test_secret_settings_not_exposed():
    settings = Settings(_env_file=None, dashscope_api_key="fake-secret-marker", qwen_model="test")
    assert "fake-secret-marker" not in repr(settings)
    assert "fake-secret-marker" not in TestClient(create_app(settings)).get("/health").text


def test_log_formatter_drops_raw_upstream_content():
    record = logging.LogRecord("trippilot", logging.ERROR, "", 0, "key=fake-secret-marker", (), None)
    assert "fake-secret-marker" not in SafeJSONFormatter().format(record)
