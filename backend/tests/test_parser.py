import json

import pytest

from mindtrace.modes import MODES
from mindtrace.parser import ParseError, parse_model_output
from tests.conftest import education_output

EDU = MODES["education"]


def test_parses_json():
    parsed = parse_model_output(EDU, json.dumps(education_output()))
    assert parsed.values["mistake_type"] == "Conceptual"
    assert parsed.missing == []


def test_parses_fenced_json_with_title_keys():
    raw = '```json\n{"Mistake Type": "logical", "What Went Wrong": "Reversed the condition."}\n```'
    parsed = parse_model_output(EDU, raw)
    assert parsed.values["mistake_type"] == "Logical"
    assert parsed.values["what_went_wrong"] == "Reversed the condition."
    assert "reflection_question" in parsed.missing


def test_enum_outside_choices_is_dropped():
    parsed = parse_model_output(EDU, json.dumps(education_output(confidence_level="Very sure")))
    assert "confidence_level" in parsed.missing


def test_text_fallback_handles_markdown_headers():
    # The old parser returned "Unknown" for every field on bold headers.
    raw = (
        "**Mistake Type:** Conceptual\n"
        "## Error Pattern Tag\nRushing\n"
        "- **What Went Wrong:** Used the area formula.\n"
        "The student said this:\nlength times width.\n"
    )
    parsed = parse_model_output(EDU, raw)
    assert parsed.values["mistake_type"] == "Conceptual"
    assert parsed.values["error_pattern_tag"] == "Rushing"
    # A sentence ending in ":" stays content, not a new header.
    assert "The student said this:" in parsed.values["what_went_wrong"]


def test_research_list_field_from_string():
    raw = json.dumps({"research_interpretation": "x", "related_cognitive_biases": "Anchoring, Framing; Halo"})
    parsed = parse_model_output(MODES["research"], raw)
    assert parsed.values["related_cognitive_biases"] == ["Anchoring", "Framing", "Halo"]


def test_missing_explanation_raises():
    with pytest.raises(ParseError):
        parse_model_output(EDU, '{"mistake_type": "Logical"}')


def test_garbage_raises():
    with pytest.raises(ParseError):
        parse_model_output(EDU, "I cannot help with that.")
