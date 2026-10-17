"""LLM clients.

OllamaClient talks to Ollama's HTTP API only. (The old analyzer fell back to spawning
`ollama run`, but that CLI talks to the same server, so the fallback could never help
and only added ANSI cursor noise to clean up.) Output is constrained with Ollama's
structured-output `format` (a JSON schema), so parsing does not depend on headers.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from mindtrace.config import Settings


class LLMError(Exception):
    """The model call failed (bad response, timeout)."""


class LLMUnavailable(LLMError):
    """The runtime cannot be reached or the model is not installed."""


class LLMClient(Protocol):
    async def generate_json(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        seed: int | None = None,
    ) -> str: ...

    async def health(self) -> dict[str, Any]: ...

    async def aclose(self) -> None: ...


class OllamaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(base_url=settings.ollama_url, transport=transport)

    async def generate_json(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        seed: int | None = None,
    ) -> str:
        options: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        if seed is not None:
            options["seed"] = seed
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "options": options,
        }
        try:
            resp = await self._http.post("/api/chat", json=payload, timeout=timeout_s)
        except httpx.ConnectError as exc:
            raise LLMUnavailable(
                f"Cannot reach Ollama at {self.settings.ollama_url}. Is it running? (`ollama serve`)"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(f"Model '{model}' did not answer within {timeout_s:.0f}s.") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Request to Ollama failed: {exc}") from exc

        if resp.status_code == 404:
            raise LLMUnavailable(f"Model '{model}' is not installed. Run: ollama pull {model}")
        if resp.status_code >= 400:
            raise LLMError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("Ollama returned an unexpected response shape.") from exc

    async def health(self) -> dict[str, Any]:
        try:
            resp = await self._http.get("/api/tags", timeout=3.0)
            resp.raise_for_status()
            installed = {m.get("name", "") for m in resp.json().get("models", [])}
        except (httpx.HTTPError, ValueError):
            return {"runtime": "ollama", "reachable": False, "model_ready": False, "judge_ready": False}

        def has(name: str) -> bool:
            return name in installed or f"{name}:latest" in installed

        return {
            "runtime": "ollama",
            "reachable": True,
            "model": self.settings.model,
            "model_ready": has(self.settings.model),
            "judge_model": self.settings.judge_model,
            "judge_ready": has(self.settings.judge_model),
        }

    async def aclose(self) -> None:
        await self._http.aclose()


_MOCK_TEXT: dict[str, Any] = {
    "mistake_type": "Assumption",
    "error_pattern_tag": "Unchecked Assumption",
    "confidence_level": "Medium",
    "consistency_check": "Partially",
    "what_went_wrong": (
        "The reasoning commits to the first interpretation of the question and builds on it "
        "without pausing to test whether that interpretation matches what is actually being asked."
    ),
    "why_this_happens": (
        "Once a plausible reading is found, attention shifts to executing it, and the original "
        "wording stops being re-read. Familiar-looking problems make this more likely."
    ),
    "how_to_rethink": (
        "Before committing, restate the question in your own words and ask what kind of quantity "
        "or conclusion it is asking for."
    ),
    "what_would_have_prevented_this": "A quick sense-check of whether the result is reasonable.",
    "reflection_question": "At which point did you decide what the question meant, and what made you sure?",
    "interviewer_assessment": (
        "The explanation focuses on carrying out a single approach and does not examine the "
        "assumptions that approach depends on."
    ),
    "risk_signals": "Early commitment to one interpretation; limited self-checking of intermediate conclusions.",
    "reasoning_error_category": "Premature Closure",
    "cognitive_pattern": "A first plausible framing is adopted and later evidence is fitted to it.",
    "confidence_in_classification": "Medium",
    "agreement_with_user_analysis": "Partially",
    "research_interpretation": (
        "The error reflects a tendency to stop searching for interpretations once one coherent "
        "reading is available, trading accuracy for cognitive economy."
    ),
    "why_this_pattern_occurs": "Time pressure, fluency of the first reading, and low perceived difficulty.",
    "broader_implications": "Reasoners often equate a coherent story with a correct one.",
    "related_cognitive_biases": ["Anchoring", "Confirmation Bias", "Einstellung Effect"],
}


class MockLLMClient:
    """Offline stand-in used when MINDTRACE_MOCK_LLM=true. Returns a fixed, generic
    analysis that satisfies the requested schema, so the UI and API can be exercised
    without Ollama."""

    async def generate_json(self, *, schema: dict[str, Any], **_: Any) -> str:
        keys = schema.get("properties", {})
        if "reveals_answer" in keys:
            return json.dumps({"reveals_answer": False, "reason": "mock judge"})
        return json.dumps({k: _MOCK_TEXT.get(k, "Mock content.") for k in keys})

    async def health(self) -> dict[str, Any]:
        return {"runtime": "mock", "reachable": True, "model_ready": True, "judge_ready": True}

    async def aclose(self) -> None:
        return None
