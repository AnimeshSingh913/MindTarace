"""Includes regression cases for every guardrail bug found in the old Reasoning Analyzer."""

import pytest

from mindtrace import guardrails
from mindtrace.guardrails import check, find_answer_statement, parse_judge_reply
from tests.conftest import with_settings

PROBLEM = "A rectangle has length 8 cm and width 5 cm. Find the perimeter."
REASONING = "I multiplied 8 by 5 and got 40 cm as the perimeter."

pytestmark = pytest.mark.anyio


async def _never_called(*_):
    raise AssertionError("judge should not be called")


async def _judge_says(value):
    async def judge(*_):
        return value
    return judge


@pytest.mark.parametrize(
    "text",
    [
        "The correct answer is 26 cm.",
        "The answer is twenty-six.",
        "So the right result would be 26.",
        "Answer: 26",
        "It should have been 26 cm.",
    ],
)
async def test_explicit_answers_blocked(text, settings):
    verdict = await check(text, problem=PROBLEM, reasoning=REASONING, settings=settings, judge=_never_called)
    assert not verdict.safe and verdict.reason == "explicit_answer"


@pytest.mark.parametrize(
    "text",
    [
        # Old analyzer blocked these on bare substrings "solution is" / "final answer".
        "The problem with this solution is that it skips the units.",
        "The student's final answer is 40, which reflects an area calculation.",
        "Your final answer was 40 because the two sides were multiplied.",
        # Old sanitizer turned x=5 into "x equals 5" and then its own regex fired on quotes.
        "You wrote that 8 = 8 and then multiplied 8 by 5 to get 40.",
        "The reasoning treats 40 cm as the boundary length.",
    ],
)
async def test_safe_text_allowed_without_judge(text, settings):
    verdict = await check(text, problem=PROBLEM, reasoning=REASONING, settings=settings, judge=_never_called)
    assert verdict.safe, verdict


@pytest.mark.parametrize("text", ["Doubling gives 8 + 5 = 13.", "The sum equals twenty-six.", "It is equal to 26."])
async def test_equality_with_novel_number_blocked(text, settings):
    verdict = await check(text, problem=PROBLEM, reasoning=REASONING, settings=settings, judge=_never_called)
    assert not verdict.safe and verdict.reason == "numeric_equality"


# Held-out evasion phrasings from the old audit (the selective judge missed 12/14).
@pytest.mark.parametrize(
    "text",
    [
        "Adding all four sides comes out to twenty-six.",
        "The boundary totals 26 cm.",
        "Walking the edge lands on 26.",
        "Done properly this resolves to twenty six centimetres.",
    ],
)
async def test_novel_numbers_go_to_judge(text, settings):
    calls = []

    async def judge(problem, reasoning, analysis):
        calls.append(analysis)
        return True

    verdict = await check(text, problem=PROBLEM, reasoning=REASONING, settings=settings, judge=judge)
    assert calls, "judge must see every output with a novel number"
    assert not verdict.safe and verdict.reason == "judge_leak"
    assert 26 in verdict.novel_numbers


async def test_judge_clears_harmless_novel_number(settings):
    async def judge(*_):
        return False

    verdict = await check("Try a 10 second sense check.", problem=PROBLEM, reasoning=REASONING,
                          settings=settings, judge=judge)
    assert verdict.safe and verdict.judge_called


async def test_judge_failure_fails_closed(settings):
    async def judge(*_):
        raise TimeoutError("judge timed out")

    verdict = await check("It totals 26.", problem=PROBLEM, reasoning=REASONING, settings=settings, judge=judge)
    assert not verdict.safe and verdict.reason == "judge_unavailable"


async def test_missing_judge_fails_closed(settings):
    verdict = await check("It totals 26.", problem=PROBLEM, reasoning=REASONING, settings=settings, judge=None)
    assert not verdict.safe and verdict.reason == "judge_unavailable"


async def test_block_policy_skips_judge(settings):
    s = with_settings(settings, novel_number_policy="block")
    verdict = await check("It totals 26.", problem=PROBLEM, reasoning=REASONING, settings=s, judge=_never_called)
    assert not verdict.safe and verdict.reason == "novel_number"


async def test_judge_always(settings):
    s = with_settings(settings, judge_always=True)
    calls = []

    async def judge(*args):
        calls.append(args)
        return False

    verdict = await check("The reasoning skipped a step.", problem=PROBLEM, reasoning=REASONING, settings=s, judge=judge)
    assert verdict.safe and len(calls) == 1


async def test_guard_crash_fails_closed(settings, monkeypatch):
    def boom(*_):
        raise RuntimeError("bug")

    monkeypatch.setattr(guardrails, "find_answer_statement", boom)
    verdict = await check("anything", problem=PROBLEM, reasoning=REASONING, settings=settings, judge=None)
    assert not verdict.safe and verdict.reason == "guard_error"


def test_markdown_does_not_hide_answer():
    assert find_answer_statement("**The correct answer is** 26") is not None


@pytest.mark.parametrize(
    "raw, expected",
    [('{"reveals_answer": true, "reason": "x"}', True), ('{"reveals_answer": false, "reason": "x"}', False)],
)
def test_parse_judge_reply(raw, expected):
    assert parse_judge_reply(raw) is expected


@pytest.mark.parametrize("raw", ["YES, it does NOT hide the answer", '{"reveals_answer": "no"}', "[]"])
def test_parse_judge_reply_rejects_ambiguous(raw):
    # The old judge read "YES ... NOT" as safe because "NOT" contains "NO".
    with pytest.raises(ValueError):
        parse_judge_reply(raw)
