import httpx
import pytest
from pydantic import BaseModel

from app.core.budget import ExecutionBudget
from app.core.config import Settings
from app.core.errors import ControlledError
from app.services.model_client import MockModelClient, QwenClient, get_model, structured_call


class Answer(BaseModel):
    value: int


def settings():
    return Settings(_env_file=None, dashscope_api_key="test-marker", qwen_model="test-model")


@pytest.mark.parametrize("usage", [None, {"prompt_tokens": 4, "completion_tokens": 3}])
async def test_qwen_success_and_usage(usage):
    def handle(req):
        assert req.headers["authorization"] == "Bearer test-marker"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"value":1}'}}], "usage": usage}
        )

    result = await QwenClient(settings(), httpx.MockTransport(handle)).complete({}, {})
    assert result.content == '{"value":1}'
    assert (result.usage is None) == (usage is None)


@pytest.mark.parametrize(
    "status,code", [(401, "AUTH_REQUIRED"), (429, "RATE_LIMITED"), (503, "PROVIDER_FAILURE")]
)
async def test_qwen_safe_errors(status, code):
    client = QwenClient(settings(), httpx.MockTransport(lambda r: httpx.Response(status, text="test-marker")))
    with pytest.raises(ControlledError) as error:
        await client.complete({}, {})
    assert error.value.error.code == code
    assert "test-marker" not in str(error.value)


async def test_qwen_timeout():
    def handle(req):
        raise httpx.ReadTimeout("secret-url", request=req)

    with pytest.raises(ControlledError) as exc:
        await QwenClient(settings(), httpx.MockTransport(handle)).complete({}, {})
    assert exc.value.error.code == "TIMEOUT"


@pytest.mark.parametrize("path", ["/api/v1", "/compatible-mode/v1/", "/compatible-mode/v1/chat/completions"])
async def test_dashscope_base_url_compatibility(path):
    def handle(request):
        assert request.url.path == "/compatible-mode/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"value":1}'}}]})

    config = settings()
    config.dashscope_base_url = "https://dashscope.aliyuncs.com" + path
    await QwenClient(config, httpx.MockTransport(handle)).complete({}, {})
    assert config.dashscope_base_url.endswith(path)


async def test_repair_counts_and_stops():
    budget = ExecutionBudget()
    with pytest.raises(ControlledError):
        await structured_call(MockModelClient(lambda p: {"wrong": 1}), {}, Answer, budget, [])
    assert budget.models == 2


async def test_repair_success():
    budget = ExecutionBudget()
    answer = await structured_call(
        MockModelClient(lambda p: {"value": 2} if "repair" in p else {}), {}, Answer, budget, []
    )
    assert answer.value == 2 and budget.models == 2


async def test_modes_and_missing_live_configuration():
    config = Settings(_env_file=None, dashscope_api_key="", qwen_model="")
    assert isinstance(get_model(config, "auto"), MockModelClient)
    with pytest.raises(ControlledError) as exc:
        await get_model(config, "live").complete({}, {})
    assert exc.value.error.code == "AUTH_REQUIRED"
