from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Callable

import pytest

from mindtrace.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings()


class FakeLLM:
    """Scriptable LLM: `analysis` is what the main model returns (dict -> JSON, str -> as is,
    or a list to return in order); `judge` is a bool verdict, an exception, or a callable."""

    def __init__(self, analysis: Any = None, judge: Any = False):
        self.analysis = analysis
        self.judge = judge
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if "reveals_answer" in kwargs["schema"]["properties"]:
            verdict = self.judge(kwargs) if callable(self.judge) else self.judge
            if isinstance(verdict, BaseException):
                raise verdict
            return verdict if isinstance(verdict, str) else json.dumps({"reveals_answer": verdict, "reason": "t"})
        out = self.analysis.pop(0) if isinstance(self.analysis, list) else self.analysis
        if isinstance(out, BaseException):
            raise out
        return out if isinstance(out, str) else json.dumps(out)

    async def health(self) -> dict[str, Any]:
        return {"runtime": "fake", "reachable": True, "model_ready": True, "judge_ready": True}

    async def aclose(self) -> None:
        return None

    @property
    def judge_calls(self) -> int:
        return sum("reveals_answer" in c["schema"]["properties"] for c in self.calls)


@pytest.fixture
def fake_llm() -> Callable[..., FakeLLM]:
    return FakeLLM


def education_output(**overrides: Any) -> dict[str, Any]:
    base = {
        "mistake_type": "Conceptual",
        "error_pattern_tag": "Formula Confusion",
        "confidence_level": "High",
        "consistency_check": "Yes",
        "what_went_wrong": "The reasoning used the formula for area when the question asks about the boundary.",
        "why_this_happens": "Area and perimeter are taught together and are easy to swap.",
        "how_to_rethink": "Picture walking around the edge versus covering the surface.",
        "what_would_have_prevented_this": "Naming the quantity before choosing an operation.",
        "reflection_question": "What does perimeter measure, in your own words?",
    }
    base.update(overrides)
    return base


def with_settings(settings: Settings, **changes: Any) -> Settings:
    return replace(settings, **changes)
