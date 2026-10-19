"""Runtime settings, read once from environment variables (prefix MINDTRACE_)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

JudgePolicy = Literal["judge", "block", "allow"]
Provider = Literal["ollama", "openai"]
JsonMode = Literal["json_schema", "json_object", "none"]

OLLAMA_DEFAULT_MODEL = "qwen2.5:3b"
OLLAMA_DEFAULT_JUDGE = "qwen2.5:0.5b"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"MINDTRACE_{name}", default).strip()


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


def _env_choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    value = _env(name, default).lower()
    if value not in choices:
        raise ValueError(f"MINDTRACE_{name} must be one of {'|'.join(choices)}, got {value!r}")
    return value


@dataclass(frozen=True)
class Settings:
    # LLM runtime: "ollama" (local) or "openai" (any OpenAI-compatible API: Groq,
    # OpenRouter, Together, OpenAI, ...).
    provider: Provider = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = field(default="", repr=False)
    # How to ask an OpenAI-compatible API for JSON. json_object is the most widely
    # supported; json_schema is stricter where the provider/model supports it.
    openai_json_mode: JsonMode = "json_object"
    model: str = OLLAMA_DEFAULT_MODEL
    judge_model: str = OLLAMA_DEFAULT_JUDGE
    temperature: float = 0.4
    max_tokens: int = 600
    seed: int | None = None
    llm_timeout_s: float = 120.0
    judge_timeout_s: float = 20.0
    mock_llm: bool = False

    # Guardrail behaviour when the output contains numbers that are not in the input.
    #   judge -> ask the judge model (fail-closed if it is unavailable)
    #   block -> block without asking
    #   allow -> let it through (explicit answer statements are still blocked)
    novel_number_policy: JudgePolicy = "judge"
    # Also send outputs without novel numbers to the judge (catches conceptual leaks on
    # non-numeric problems, at the cost of one extra small-model call per request).
    judge_always: bool = False
    # Numbers that may appear in an analysis without suggesting a leaked answer.
    allowed_numbers: frozenset[float] = frozenset({0.0, 1.0, 2.0, 100.0})

    # API
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    max_input_chars: int = 4000
    # Per-client-IP limits on /api/analyze (0 disables). Keep these on for public
    # deployments: every analysis costs one or two paid model calls.
    rate_limit_per_minute: int = 0
    rate_limit_per_hour: int = 0
    # Cap on analyses per UTC day across all clients (0 disables): a bill safety net.
    daily_request_cap: int = 0

    def validate(self) -> None:
        """Fail fast at startup on settings that cannot work."""
        if self.mock_llm:
            return
        if self.provider == "openai":
            missing = [
                name
                for name, value in (("MINDTRACE_OPENAI_API_KEY", self.openai_api_key), ("MINDTRACE_MODEL", self.model))
                if not value
            ]
            if missing:
                raise ValueError(f"provider=openai requires {', '.join(missing)} to be set")


@lru_cache
def get_settings() -> Settings:
    provider = _env_choice("PROVIDER", "ollama", ("ollama", "openai"))
    is_ollama = provider == "ollama"
    model = _env("MODEL", OLLAMA_DEFAULT_MODEL if is_ollama else "")
    seed = _env("SEED", "")
    return Settings(
        provider=provider,  # type: ignore[arg-type]
        ollama_url=_env("OLLAMA_URL", Settings.ollama_url).rstrip("/"),
        openai_base_url=_env("OPENAI_BASE_URL", Settings.openai_base_url).rstrip("/"),
        openai_api_key=_env("OPENAI_API_KEY", ""),
        openai_json_mode=_env_choice("OPENAI_JSON_MODE", "json_object", ("json_schema", "json_object", "none")),  # type: ignore[arg-type]
        model=model,
        # Hosted APIs are fast and cheap enough to judge with the main model by default.
        judge_model=_env("JUDGE_MODEL", OLLAMA_DEFAULT_JUDGE if is_ollama else model),
        temperature=float(_env("TEMPERATURE", str(Settings.temperature))),
        max_tokens=int(_env("MAX_TOKENS", str(Settings.max_tokens))),
        seed=int(seed) if seed else None,
        llm_timeout_s=float(_env("LLM_TIMEOUT_S", str(Settings.llm_timeout_s))),
        judge_timeout_s=float(_env("JUDGE_TIMEOUT_S", str(Settings.judge_timeout_s))),
        mock_llm=_env_bool("MOCK_LLM", False),
        novel_number_policy=_env_choice("NOVEL_NUMBER_POLICY", "judge", ("judge", "block", "allow")),  # type: ignore[arg-type]
        judge_always=_env_bool("JUDGE_ALWAYS", False),
        cors_origins=_env_list("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
        max_input_chars=int(_env("MAX_INPUT_CHARS", str(Settings.max_input_chars))),
        rate_limit_per_minute=int(_env("RATE_LIMIT_PER_MINUTE", "0")),
        rate_limit_per_hour=int(_env("RATE_LIMIT_PER_HOUR", "0")),
        daily_request_cap=int(_env("DAILY_REQUEST_CAP", "0")),
    )
