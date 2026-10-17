"""The analysis pipeline: clean -> prompt -> model (JSON) -> parse -> guard -> respond."""

from __future__ import annotations

import logging
import time

from mindtrace import guardrails
from mindtrace.config import Settings
from mindtrace.llm import LLMClient
from mindtrace.modes import MODES, system_prompt
from mindtrace.parser import ParseError, parse_model_output
from mindtrace.sanitize import build_user_prompt, clean_user_text
from mindtrace.schemas import AnalyzeRequest, AnalyzeResponse, BlockInfo, Meta, Section

logger = logging.getLogger(__name__)

_SUMMARY_ROLES = {"mistake_type", "pattern", "confidence", "agreement"}

BLOCK_MESSAGES = {
    "explicit_answer": "The analysis started to state the answer, so it was withheld. MindTrace only explains mistakes.",
    "numeric_equality": "The analysis worked out a value that isn't in your problem or reasoning, so it was withheld.",
    "novel_number": "The analysis introduced a new number that could reveal the answer, so it was withheld.",
    "judge_leak": "The safety check found that the analysis would reveal the answer, so it was withheld.",
    "judge_unavailable": "The safety check could not run, so the analysis was withheld (fail-closed). Check that the judge model is installed.",
    "guard_error": "The safety check failed, so the analysis was withheld (fail-closed).",
}


def make_judge(llm: LLMClient, settings: Settings) -> guardrails.Judge:
    async def judge(problem: str, reasoning: str, analysis: str) -> bool:
        raw = await llm.generate_json(
            model=settings.judge_model,
            system=guardrails.JUDGE_SYSTEM,
            prompt=f"PROBLEM:\n{problem}\n\nPERSON'S REASONING:\n{reasoning}\n\nANALYSIS:\n{analysis}",
            schema=guardrails.JUDGE_SCHEMA,
            temperature=0.0,
            max_tokens=120,
            timeout_s=settings.judge_timeout_s,
            seed=42,
        )
        return guardrails.parse_judge_reply(raw)

    return judge


async def analyze(request: AnalyzeRequest, llm: LLMClient, settings: Settings) -> AnalyzeResponse:
    started = time.perf_counter()
    spec = MODES[request.mode]
    problem = clean_user_text(request.problem)
    reasoning = clean_user_text(request.reasoning)
    prompt = build_user_prompt(problem, reasoning)

    parsed = None
    for attempt, temperature in enumerate((settings.temperature, 0.0)):
        raw = await llm.generate_json(
            model=settings.model,
            system=system_prompt(request.mode),
            prompt=prompt,
            schema=spec.json_schema(),
            temperature=temperature,
            max_tokens=settings.max_tokens,
            timeout_s=settings.llm_timeout_s,
            seed=settings.seed,
        )
        try:
            parsed = parse_model_output(spec, raw)
            break
        except ParseError:
            logger.warning("Unparseable model output (attempt %d): %r", attempt + 1, raw[:300])
    if parsed is None:
        raise ParseError("The model returned output that could not be parsed, twice.")

    verdict = await guardrails.check(
        parsed.joined_text(),
        problem=problem,
        reasoning=reasoning,
        settings=settings,
        judge=make_judge(llm, settings),
    )
    meta = Meta(
        model=settings.model,
        latency_ms=round((time.perf_counter() - started) * 1000),
        judge_called=verdict.judge_called,
        missing_fields=parsed.missing,
    )

    if not verdict.safe:
        reason = verdict.reason or "guard_error"
        logger.info("Blocked analysis (%s): %s", reason, verdict.detail)
        return AnalyzeResponse(
            mode=request.mode,
            status="blocked",
            block=BlockInfo(reason=reason, message=BLOCK_MESSAGES[reason]),
            meta=meta,
        )

    by_role = {f.role: parsed.values.get(f.key) for f in spec.fields if f.role}
    sections = [
        Section(key=f.key, title=f.title, content=parsed.values[f.key])
        for f in spec.fields
        if f.key in parsed.values and f.role not in _SUMMARY_ROLES
    ]
    return AnalyzeResponse(
        mode=request.mode,
        status="ok",
        mistake_type=by_role.get("mistake_type"),
        reasoning_pattern=by_role.get("pattern"),
        confidence=by_role.get("confidence"),
        agreement=by_role.get("agreement"),
        explanation=by_role.get("explanation"),
        sections=sections,
        meta=meta,
    )
