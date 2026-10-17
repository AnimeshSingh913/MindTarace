"""OllamaClient against a mocked HTTP transport (no Ollama needed)."""

import json

import httpx
import pytest

from mindtrace.llm import LLMError, LLMUnavailable, OllamaClient

pytestmark = pytest.mark.anyio

ARGS = dict(model="m", system="s", prompt="p", schema={"type": "object"}, temperature=0.2, max_tokens=50, timeout_s=5)


def make(handler, settings):
    return OllamaClient(settings, transport=httpx.MockTransport(handler))


async def test_sends_schema_and_token_limit(settings):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"a": 1}'}})

    client = make(handler, settings)
    assert await client.generate_json(**ARGS, seed=7) == '{"a": 1}'
    assert seen["format"] == {"type": "object"} and seen["stream"] is False
    assert seen["options"] == {"temperature": 0.2, "num_predict": 50, "seed": 7}
    assert seen["messages"][0] == {"role": "system", "content": "s"}
    await client.aclose()


async def test_missing_model_is_unavailable(settings):
    client = make(lambda r: httpx.Response(404, json={"error": "model not found"}), settings)
    with pytest.raises(LLMUnavailable, match="ollama pull m"):
        await client.generate_json(**ARGS)


async def test_connect_error_is_unavailable(settings):
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable):
        await make(handler, settings).generate_json(**ARGS)


async def test_timeout_is_llm_error(settings):
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(LLMError, match="did not answer"):
        await make(handler, settings).generate_json(**ARGS)


async def test_health_reports_models(settings):
    tags = {"models": [{"name": "qwen2.5:3b"}]}
    health = await make(lambda r: httpx.Response(200, json=tags), settings).health()
    assert health["reachable"] and health["model_ready"] and not health["judge_ready"]
