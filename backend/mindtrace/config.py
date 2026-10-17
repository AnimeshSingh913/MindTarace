"""Runtime settings, read once from environment variables (prefix MINDTRACE_)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

JudgePolicy = Literal["judge", "block", "allow"]


def _env(name: str, default: str) -> str:
    return os.environ.get(f"MINDTRACE_{name}", default).strip()


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # LLM runtime
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:3b"
    judge_model: str = "qwen2.5:0.5b"
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


@lru_cache
def get_settings() -> Settings:
    seed = _env("SEED", "")
    policy = _env("NOVEL_NUMBER_POLICY", "judge").lower()
    if policy not in ("judge", "block", "allow"):
        raise ValueError(f"MINDTRACE_NOVEL_NUMBER_POLICY must be judge|block|allow, got {policy!r}")
    return Settings(
        ollama_url=_env("OLLAMA_URL", Settings.ollama_url).rstrip("/"),
        model=_env("MODEL", Settings.model),
        judge_model=_env("JUDGE_MODEL", Settings.judge_model),
        temperature=float(_env("TEMPERATURE", str(Settings.temperature))),
        max_tokens=int(_env("MAX_TOKENS", str(Settings.max_tokens))),
        seed=int(seed) if seed else None,
        llm_timeout_s=float(_env("LLM_TIMEOUT_S", str(Settings.llm_timeout_s))),
        judge_timeout_s=float(_env("JUDGE_TIMEOUT_S", str(Settings.judge_timeout_s))),
        mock_llm=_env_bool("MOCK_LLM", False),
        novel_number_policy=policy,  # type: ignore[arg-type]
        judge_always=_env_bool("JUDGE_ALWAYS", False),
        cors_origins=_env_list("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
        max_input_chars=int(_env("MAX_INPUT_CHARS", str(Settings.max_input_chars))),
    )
