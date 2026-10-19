import pytest
from fastapi.testclient import TestClient

from mindtrace.config import Settings, get_settings
from mindtrace.llm import LLMRateLimited
from mindtrace.main import create_app
from mindtrace.ratelimit import RateLimiter
from tests.conftest import FakeLLM, education_output, with_settings

BODY = {"problem": "8 by 5 rectangle, perimeter?", "reasoning": "8 times 5 is 40.", "mode": "education"}


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_disabled_limiter_allows_everything():
    limiter = RateLimiter()
    assert not limiter.enabled
    assert all(limiter.check("ip") is None for _ in range(1000))


def test_per_minute_window_slides():
    clock = Clock()
    limiter = RateLimiter(per_minute=2, clock=clock)
    assert limiter.check("a") is None and limiter.check("a") is None
    wait = limiter.check("a")
    assert wait is not None and 0 < wait <= 60
    assert limiter.check("b") is None  # other clients unaffected
    clock.t += 61
    assert limiter.check("a") is None


def test_per_hour_limit():
    clock = Clock()
    limiter = RateLimiter(per_hour=3, clock=clock)
    for _ in range(3):
        assert limiter.check("a") is None
        clock.t += 120
    assert limiter.check("a") is not None
    clock.t += 3600
    assert limiter.check("a") is None


def test_daily_cap_resets_next_utc_day():
    clock = Clock(t=86400 * 20000 + 100)
    limiter = RateLimiter(daily_cap=2, clock=clock)
    assert limiter.check("a") is None and limiter.check("b") is None
    assert limiter.check("c") is not None
    clock.t += 86400
    assert limiter.check("c") is None


def test_rejected_requests_do_not_consume_quota():
    clock = Clock()
    limiter = RateLimiter(per_minute=1, clock=clock)
    limiter.check("a")
    for _ in range(5):
        assert limiter.check("a") is not None
    clock.t += 60
    assert limiter.check("a") is None


def test_api_returns_429_with_retry_after(settings):
    s = with_settings(settings, rate_limit_per_minute=1)
    with TestClient(create_app(settings=s, llm=FakeLLM(education_output()))) as c:
        assert c.post("/api/analyze", json=BODY).status_code == 200
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_provider_rate_limit_maps_to_429(settings):
    with TestClient(create_app(settings=settings, llm=FakeLLM(LLMRateLimited("slow down")))) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 429 and r.headers["retry-after"] == "30"


def test_live_never_touches_the_model(settings):
    with TestClient(create_app(settings=settings, llm=FakeLLM())) as c:
        assert c.get("/api/live").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "settings_obj, ok",
    [
        (Settings(provider="openai", openai_api_key="k", model="m"), True),
        (Settings(provider="openai", openai_api_key="", model="m"), False),
        (Settings(provider="openai", openai_api_key="k", model=""), False),
        (Settings(provider="openai", mock_llm=True, model=""), True),
        (Settings(), True),
    ],
)
def test_settings_validation(settings_obj, ok):
    if ok:
        settings_obj.validate()
    else:
        with pytest.raises(ValueError):
            settings_obj.validate()


def test_env_hosted_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MINDTRACE_PROVIDER", "openai")
    monkeypatch.setenv("MINDTRACE_MODEL", "some-model")
    monkeypatch.setenv("MINDTRACE_OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("MINDTRACE_OPENAI_BASE_URL", "https://api.groq.com/openai/v1/")
    try:
        s = get_settings()
        assert s.judge_model == "some-model"  # judge defaults to the main model when hosted
        assert s.openai_base_url == "https://api.groq.com/openai/v1"
        assert "sk-x" not in repr(s)
    finally:
        get_settings.cache_clear()


def test_env_rejects_unknown_provider(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MINDTRACE_PROVIDER", "nope")
    try:
        with pytest.raises(ValueError):
            get_settings()
    finally:
        get_settings.cache_clear()
