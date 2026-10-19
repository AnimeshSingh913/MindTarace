"""OpenAICompatClient against a mocked HTTP transport (no network, no API key needed)."""

import json
from dataclasses import replace

import httpx
import pytest

from mindtrace.config import Settings
from mindtrace.llm import LLMError, LLMRateLimited, LLMUnavailable, OpenAICompatClient

pytestmark = pytest.mark.anyio

ARGS = dict(model="m", system="s", prompt="p", schema={"type": "object"}, temperature=0.2, max_tokens=50, timeout_s=5)


@pytest.fixture
def hosted() -> Settings:
    return Settings(provider="openai", openai_base_url="https://llm.example/v1", openai_api_key="sk-test", model="m", judge_model="j")


def make(handler, settings):
    return OpenAICompatClient(settings, transport=httpx.MockTransport(handler))


def ok(content='{"a": 1}'):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_request_shape(hosted):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return ok()

    assert await make(handler, hosted).generate_json(**ARGS, seed=3) == '{"a": 1}'
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert body["model"] == "m" and body["max_tokens"] == 50 and body["temperature"] == 0.2 and body["seed"] == 3
    assert body["messages"] == [{"role": "system", "content": "s"}, {"role": "user", "content": "p"}]
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("json_schema", {"type": "json_schema", "json_schema": {"name": "mindtrace_output", "schema": {"type": "object"}}}),
        ("none", None),
    ],
)
async def test_json_modes(hosted, mode, expected):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return ok()

    await make(handler, replace(hosted, openai_json_mode=mode)).generate_json(**ARGS)
    assert seen.get("response_format") == expected


@pytest.mark.parametrize(
    "status, exc",
    [(401, LLMUnavailable), (403, LLMUnavailable), (404, LLMUnavailable), (429, LLMRateLimited), (500, LLMError)],
)
async def test_status_mapping(hosted, status, exc):
    client = make(lambda r: httpx.Response(status, text="provider said: secret-prompt-echo"), hosted)
    with pytest.raises(exc) as info:
        await client.generate_json(**ARGS)
    assert "secret-prompt-echo" not in str(info.value)


@pytest.mark.parametrize("body", [{"choices": []}, {"oops": 1}, {"choices": [{"message": {"content": "  "}}]}])
async def test_bad_bodies(hosted, body):
    with pytest.raises(LLMError):
        await make(lambda r: httpx.Response(200, json=body), hosted).generate_json(**ARGS)


async def test_connect_error(hosted):
    def handler(request):
        raise httpx.ConnectError("dns")

    with pytest.raises(LLMUnavailable):
        await make(handler, hosted).generate_json(**ARGS)


async def test_health_checks_models_and_is_cached(hosted):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "m"}, {"id": "other"}]})

    client = make(handler, hosted)
    first = await client.health()
    second = await client.health()
    assert first["reachable"] and first["model_ready"] and not first["judge_ready"]
    assert first == second and calls == ["/v1/models"]


def test_full_api_through_hosted_client(hosted):
    """Main call + judge call both go through the OpenAI-compatible client."""
    from fastapi.testclient import TestClient

    from mindtrace.main import create_app
    from tests.conftest import education_output

    models_seen = []

    def handler(request):
        body = json.loads(request.content)
        models_seen.append(body["model"])
        if "reveals_answer" in body["messages"][0]["content"]:
            return ok('{"reveals_answer": false, "reason": "only describes the method"}')
        # A novel number ("10") forces the judge to run.
        return ok(json.dumps(education_output(how_to_rethink="Pause for 10 seconds and restate the question.")))

    client = OpenAICompatClient(hosted, transport=httpx.MockTransport(handler))
    with TestClient(create_app(settings=hosted, llm=client)) as c:
        data = c.post("/api/analyze", json={"problem": "8 by 5 rectangle, perimeter?", "reasoning": "8 x 5 = 40"}).json()
    assert data["status"] == "ok" and data["meta"]["judge_called"] is True
    assert models_seen == ["m", "j"]


async def test_health_with_bad_key_is_reachable_but_not_ready(hosted):
    health = await make(lambda r: httpx.Response(401), hosted).health()
    assert health["reachable"] and not health["model_ready"]
