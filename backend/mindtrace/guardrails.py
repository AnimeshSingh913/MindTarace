"""Output guardrail: decides whether an analysis may be shown.

Tiers, in order:
  1. Explicit answer statements ("the correct answer is", "answer: 42") -> block.
  2. Equality with a number that is not in the input ("= 48", "equals 48") -> block.
  3. Novel numbers (in digits or words) not in the input -> policy: judge | block | allow.
  4. Optional always-on judge (MINDTRACE_JUDGE_ALWAYS) for conceptual leaks.

The judge is a small model asked for structured JSON ({"reveals_answer": bool}), and it
sees the problem, so it can tell a quoted mistake from a revealed result. Any judge
failure blocks the response (fail-closed). The verdict is returned as a value, never
stored in module state, so concurrent requests cannot see each other's results.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from mindtrace.config import Settings
from mindtrace.numerics import extract_numbers

logger = logging.getLogger(__name__)

BlockReason = Literal[
    "explicit_answer", "numeric_equality", "novel_number", "judge_leak", "judge_unavailable", "guard_error"
]

# A judge takes (problem, reasoning, analysis) and returns True if the answer is revealed.
Judge = Callable[[str, str, str], Awaitable[bool]]

_ANSWER_STATEMENTS = [
    re.compile(
        r"\b(?:correct|right|actual|true|real|expected|final)\s+(?:answer|result|value|solution|total)"
        r"\s+(?:is|would\s+be|should\s+be|will\s+be|equals|comes\s+(?:out\s+)?to|works\s+out\s+to)\b"
    ),
    re.compile(r"\bthe\s+answer\s+(?:is|would\s+be|should\s+be|will\s+be)\b"),
    re.compile(r"\b(?:answer|result|solution)\s*[:=]\s*[-+$€£]?\d"),
    re.compile(r"\b(?:it|this|that)\s+should\s+(?:have\s+)?(?:be|been)\s+[-+$€£]?\d"),
]
# Possessives right before a match mean the text is describing the person's own answer
# ("the student's final answer is 40, which ..."), not giving the right one.
_DESCRIBES_PERSON = re.compile(
    r"\b(?:student|learner|candidate|person|user|their|your|his|her)(?:'s|s')?\s*$"
)
_EQUALITY = re.compile(r"(?:=|\bequals?(?:\s+to)?\b)\s*[-+$€£]?\s*(\d[\d,]*(?:\.\d+)?|[a-z]+(?:[\s-][a-z]+)?)")
_MARKDOWN = re.compile(r"[*_`#>]+")

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"reveals_answer": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["reveals_answer", "reason"],
}
JUDGE_SYSTEM = (
    "You audit a tutoring system that must NEVER reveal the answer to a problem. "
    "You are given the problem, the person's reasoning, and the system's analysis. "
    "Quoting or describing numbers the person already wrote is allowed. "
    "Decide whether the ANALYSIS states, computes, or clearly implies the correct answer "
    "or the correct result, or tells the person which of their values is right. "
    'Reply as JSON: {"reveals_answer": true|false, "reason": "<short reason>"}.'
)


@dataclass
class Verdict:
    safe: bool
    reason: BlockReason | None = None
    detail: str = ""
    novel_numbers: list[float] = field(default_factory=list)
    judge_called: bool = False


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKDOWN.sub("", text.lower())).strip()


def find_answer_statement(text: str) -> str | None:
    norm = _normalise(text)
    for pattern in _ANSWER_STATEMENTS:
        for match in pattern.finditer(norm):
            before = norm[max(0, match.start() - 30): match.start()]
            before = re.sub(r"\b(?:final|correct|actual|own|original)\s*$", "", before.rstrip()).rstrip()
            if _DESCRIBES_PERSON.search(before):
                continue
            return match.group(0)
    return None


def find_novel_equality(text: str, input_numbers: set[float], allowed: frozenset[float]) -> str | None:
    norm = _normalise(text)
    for match in _EQUALITY.finditer(norm):
        values = extract_numbers(match.group(1))
        if values and not values <= (input_numbers | allowed):
            return match.group(0)
    return None


async def check(
    analysis: str,
    *,
    problem: str,
    reasoning: str,
    settings: Settings,
    judge: Judge | None,
) -> Verdict:
    """Never raises: any internal error yields a blocking verdict."""
    try:
        return await _check(analysis, problem=problem, reasoning=reasoning, settings=settings, judge=judge)
    except Exception:  # noqa: BLE001 - fail closed on anything unexpected
        logger.exception("Guardrail crashed; blocking response")
        return Verdict(safe=False, reason="guard_error", detail="internal guardrail error")


async def _check(analysis: str, *, problem: str, reasoning: str, settings: Settings, judge: Judge | None) -> Verdict:
    if not analysis.strip():
        return Verdict(safe=False, reason="guard_error", detail="empty analysis")

    if statement := find_answer_statement(analysis):
        return Verdict(safe=False, reason="explicit_answer", detail=statement)

    input_numbers = extract_numbers(problem) | extract_numbers(reasoning)
    allowed = settings.allowed_numbers
    if equality := find_novel_equality(analysis, input_numbers, allowed):
        return Verdict(safe=False, reason="numeric_equality", detail=equality)

    novel = sorted(extract_numbers(analysis) - input_numbers - allowed)
    needs_judge = settings.judge_always
    if novel:
        if settings.novel_number_policy == "block":
            return Verdict(safe=False, reason="novel_number", detail=_fmt(novel), novel_numbers=novel)
        needs_judge = needs_judge or settings.novel_number_policy == "judge"

    if not needs_judge:
        return Verdict(safe=True, novel_numbers=novel)

    if judge is None:
        return Verdict(safe=False, reason="judge_unavailable", detail="no judge configured", novel_numbers=novel)
    try:
        leaked = await judge(problem, reasoning, analysis)
    except Exception as exc:  # noqa: BLE001 - fail closed
        logger.warning("Safety judge failed (%s); blocking response", exc)
        return Verdict(safe=False, reason="judge_unavailable", detail=str(exc), novel_numbers=novel, judge_called=True)
    if leaked:
        return Verdict(safe=False, reason="judge_leak", detail=_fmt(novel), novel_numbers=novel, judge_called=True)
    return Verdict(safe=True, novel_numbers=novel, judge_called=True)


def _fmt(values: list[float]) -> str:
    return ", ".join(f"{v:g}" for v in values)


def parse_judge_reply(raw: str) -> bool:
    """Returns True if the judge says the answer was revealed. Raises ValueError on
    anything that is not a clear boolean verdict, which the caller treats as a failure."""
    data = json.loads(raw)
    value = data.get("reveals_answer") if isinstance(data, dict) else None
    if not isinstance(value, bool):
        raise ValueError(f"judge reply has no boolean verdict: {raw[:120]!r}")
    return value
