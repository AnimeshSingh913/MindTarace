"""End-to-end API tests through FastAPI's TestClient with a fake LLM."""

import pytest
from fastapi.testclient import TestClient

from mindtrace.llm import LLMError, LLMUnavailable, MockLLMClient
from mindtrace.main import create_app
from tests.conftest import FakeLLM, education_output

BODY = {
    "problem": "A rectangle has length 8 cm and width 5 cm. Find the perimeter.",
    "reasoning": "I multiplied 8 by 5 and got 40 cm.",
    "mode": "education",
}


def client_for(llm, settings) -> TestClient:
    return TestClient(create_app(settings=settings, llm=llm))


def test_ok_response_shape(settings):
    with client_for(FakeLLM(education_output()), settings) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mistake_type"] == "Conceptual"
    assert data["reasoning_pattern"] == "Formula Confusion"
    assert data["confidence"] == "High" and data["agreement"] == "Yes"
    titles = [s["title"] for s in data["sections"]]
    assert titles[0] == "What Went Wrong" and "Mistake Type" not in titles
    assert "raw_response" not in data and "block" not in data


def test_blocked_response_never_contains_model_text(settings):
    leak = education_output(what_went_wrong="Adding all four sides, the correct answer is 26 cm.")
    with client_for(FakeLLM(leak), settings) as c:
        r = c.post("/api/analyze", json=BODY)
    data = r.json()
    assert r.status_code == 200 and data["status"] == "blocked"
    assert data["block"]["reason"] == "explicit_answer"
    assert "26" not in r.text and "four sides" not in r.text


def test_judge_unavailable_blocks_at_api_level(settings):
    # The old API only blocked on one message string, so fail-closed actually failed open.
    leak = education_output(what_went_wrong="Walking the whole edge lands on twenty-six.")
    with client_for(FakeLLM(leak, judge=LLMUnavailable("judge missing")), settings) as c:
        data = c.post("/api/analyze", json=BODY).json()
    assert data["status"] == "blocked" and data["block"]["reason"] == "judge_unavailable"
    assert "twenty-six" not in str(data)


def test_interview_mode_has_no_duplicated_explanation(settings):
    out = {
        "mistake_type": "Logical", "error_pattern_tag": "Rushing", "confidence_level": "Medium",
        "consistency_check": "Partially", "interviewer_assessment": "Focuses on X.", "risk_signals": "Omits Y.",
    }
    with client_for(FakeLLM(out), settings) as c:
        data = c.post("/api/analyze", json={**BODY, "mode": "interview"}).json()
    assert data["explanation"] == "Focuses on X."
    assert [s["key"] for s in data["sections"]] == ["interviewer_assessment", "risk_signals"]


def test_retries_once_on_unparseable_output(settings):
    llm = FakeLLM(["not json at all", education_output()])
    with client_for(llm, settings) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 200 and len(llm.calls) == 2
    assert llm.calls[1]["temperature"] == 0.0


def test_unparseable_twice_is_502(settings):
    with client_for(FakeLLM(["nope", "still nope"]), settings) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 502


@pytest.mark.parametrize("exc, status", [(LLMUnavailable("Ollama down"), 503), (LLMError("timeout"), 502)])
def test_llm_errors_map_to_status(settings, exc, status):
    with client_for(FakeLLM(exc), settings) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == status and r.json()["detail"]


def test_unexpected_error_does_not_leak_details(settings):
    with client_for(FakeLLM(RuntimeError("secret path C:/x")), settings) as c:
        r = c.post("/api/analyze", json=BODY)
    assert r.status_code == 500 and "secret" not in r.text


@pytest.mark.parametrize(
    "patch",
    [{"mode": "hacker"}, {"problem": "   "}, {"reasoning": "x" * 5000}, {"problem": None}],
)
def test_validation(settings, patch):
    with client_for(FakeLLM(education_output()), settings) as c:
        assert c.post("/api/analyze", json={**BODY, **patch}).status_code == 422


def test_cors_is_restricted(settings):
    with client_for(FakeLLM(education_output()), settings) as c:
        ok = c.options("/api/analyze", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        bad = c.options("/api/analyze", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_health_and_modes_with_mock(settings):
    with client_for(MockLLMClient(), settings) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        modes = c.get("/api/modes").json()
        assert [m["key"] for m in modes] == ["education", "interview", "research"]
        for mode in ("education", "interview", "research"):
            assert c.post("/api/analyze", json={**BODY, "mode": mode}).json()["status"] == "ok"
