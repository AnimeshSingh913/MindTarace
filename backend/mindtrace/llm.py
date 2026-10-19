"""LLM clients: OllamaClient (local), OpenAICompatClient (hosted), MockLLMClient (offline).

OllamaClient talks to Ollama's HTTP API only. (The old analyzer fell back to spawning
`ollama run`, but that CLI talks to the same server, so the fallback could never help
and only added ANSI cursor noise to clean up.) Output is constrained with Ollama's
structured-output `format` (a JSON schema), so parsing does not depend on headers.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

import httpx

from mindtrace.config import Settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The model call failed (bad response, timeout)."""


class LLMUnavailable(LLMError):
    """The runtime cannot be reached, the model is not installed, or the key is rejected."""


class LLMRateLimited(LLMError):
    """The hosted provider is rate-limiting us."""


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


class OpenAICompatClient:
    """Any provider exposing the OpenAI Chat Completions API (Groq, OpenRouter,
    Together, OpenAI, ...). Used for online deployments where running Ollama is not
    practical."""

    HEALTH_TTL_S = 60.0

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.openai_base_url + "/",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            transport=transport,
        )
        self._health_cache: tuple[float, dict[str, Any]] | None = None

    def _response_format(self, schema: dict[str, Any]) -> dict[str, Any] | None:
        mode = self.settings.openai_json_mode
        if mode == "json_schema":
            return {"type": "json_schema", "json_schema": {"name": "mindtrace_output", "schema": schema}}
        if mode == "json_object":
            return {"type": "json_object"}
        return None

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
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        if (fmt := self._response_format(schema)) is not None:
            payload["response_format"] = fmt

        try:
            resp = await self._http.post("chat/completions", json=payload, timeout=timeout_s)
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"Cannot reach {self.settings.openai_base_url}.") from exc
        except httpx.TimeoutException as exc:
            raise LLMError(f"Model '{model}' did not answer within {timeout_s:.0f}s.") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Request to the model provider failed: {exc}") from exc

        if resp.status_code in (401, 403):
            raise LLMUnavailable("The model provider rejected the API key (MINDTRACE_OPENAI_API_KEY).")
        if resp.status_code == 404:
            raise LLMUnavailable(f"Model '{model}' was not found at {self.settings.openai_base_url}.")
        if resp.status_code == 429:
            raise LLMRateLimited("The model provider is rate-limiting requests. Try again in a minute.")
        if resp.status_code >= 400:
            # Provider error bodies can echo the request; keep them in logs only.
            logger.warning("Provider error %d for model %s: %s", resp.status_code, model, resp.text[:500])
            raise LLMError(f"The model provider returned HTTP {resp.status_code}.")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("The model provider returned an unexpected response shape.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("The model provider returned an empty response.")
        return content

    async def health(self) -> dict[str, Any]:
        # Cached: every open browser tab polls /api/health, and that should not turn
        # into a stream of provider calls.
        now = time.monotonic()
        if self._health_cache and now - self._health_cache[0] < self.HEALTH_TTL_S:
            return self._health_cache[1]
        status: dict[str, Any] = {
            "runtime": "openai-compatible",
            "reachable": False,
            "model": self.settings.model,
            "model_ready": False,
            "judge_model": self.settings.judge_model,
            "judge_ready": False,
        }
        try:
            resp = await self._http.get("models", timeout=5.0)
            if resp.status_code < 500:
                status["reachable"] = True
            if resp.status_code == 200:
                ids = {m.get("id") for m in resp.json().get("data", []) if isinstance(m, dict)}
                status["model_ready"] = self.settings.model in ids
                status["judge_ready"] = self.settings.judge_model in ids
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
        self._health_cache = (now, status)
        return status

    async def aclose(self) -> None:
        await self._http.aclose()


def build_client(settings: Settings) -> LLMClient:
    if settings.mock_llm:
        return MockLLMClient()
    if settings.provider == "openai":
        return OpenAICompatClient(settings)
    return OllamaClient(settings)


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
