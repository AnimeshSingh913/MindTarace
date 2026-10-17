"""Analysis modes: one declarative spec per mode drives the prompt, the JSON schema
sent to the model, and the mapping of model output onto the API response."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

Mode = Literal["education", "interview", "research"]
Role = Literal["mistake_type", "pattern", "confidence", "agreement", "explanation"]
Kind = Literal["text", "enum", "list"]

PROMPT_DIR = Path(__file__).parent / "prompts"

MISTAKE_TYPES = ("Conceptual", "Logical", "Assumption", "Misinterpretation", "Overconfidence")
CONFIDENCE = ("High", "Medium", "Low")
AGREEMENT = ("Yes", "Partially", "No")


@dataclass(frozen=True)
class FieldSpec:
    key: str
    title: str
    guidance: str
    kind: Kind = "text"
    choices: tuple[str, ...] = ()
    role: Role | None = None

    def json_schema(self) -> dict[str, Any]:
        if self.kind == "enum":
            return {"type": "string", "enum": list(self.choices)}
        if self.kind == "list":
            return {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}
        return {"type": "string"}


@dataclass(frozen=True)
class ModeSpec:
    key: Mode
    label: str
    fields: tuple[FieldSpec, ...]

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {f.key: f.json_schema() for f in self.fields},
            "required": [f.key for f in self.fields],
        }

    def field_by_title(self) -> dict[str, FieldSpec]:
        return {f.title.lower(): f for f in self.fields}


_SHARED_HEAD = (
    FieldSpec("mistake_type", "Mistake Type", "Pick exactly one category.", "enum", MISTAKE_TYPES, "mistake_type"),
    FieldSpec("error_pattern_tag", "Error Pattern Tag",
              "A short label of two to four words, e.g. Rushing, Unchecked Assumption.", role="pattern"),
    FieldSpec("confidence_level", "Confidence Level", "How confident you are in this classification.",
              "enum", CONFIDENCE, "confidence"),
    FieldSpec("consistency_check", "Consistency Check",
              "Does the person's own explanation already capture the core mistake?", "enum", AGREEMENT, "agreement"),
)

MODES: dict[str, ModeSpec] = {
    "education": ModeSpec("education", "Education", _SHARED_HEAD + (
        FieldSpec("what_went_wrong", "What Went Wrong", "Explain the flawed reasoning. Do not solve.", role="explanation"),
        FieldSpec("why_this_happens", "Why This Happens", "The cognitive cause of the mistake."),
        FieldSpec("how_to_rethink", "How To Rethink", "General, mindset-focused suggestions. No methods or steps that reveal the result."),
        FieldSpec("what_would_have_prevented_this", "What Would Have Prevented This", "A habit or mindset that avoids this mistake."),
        FieldSpec("reflection_question", "Reflection Question", "Exactly one question that prompts reflection on the thinking."),
    )),
    "interview": ModeSpec("interview", "Interview", _SHARED_HEAD + (
        FieldSpec("interviewer_assessment", "Interviewer Assessment",
                  "Neutral observation: what the explanation emphasises and what it omits. Do not judge correctness.",
                  role="explanation"),
        FieldSpec("risk_signals", "Risk Signals", "Descriptive observations of reasoning risks an interviewer would notice."),
    )),
    "research": ModeSpec("research", "Research", (
        FieldSpec("reasoning_error_category", "Reasoning Error Category",
                  "One category, e.g. Overconfidence Bias, Premature Closure.", role="mistake_type"),
        FieldSpec("cognitive_pattern", "Cognitive Pattern", "Abstract description of the reasoning pattern.", role="pattern"),
        FieldSpec("confidence_in_classification", "Confidence in Classification", "Confidence in the category.",
                  "enum", CONFIDENCE, "confidence"),
        FieldSpec("agreement_with_user_analysis", "Agreement with User Analysis",
                  "Does the person's own analysis capture the core error?", "enum", AGREEMENT, "agreement"),
        FieldSpec("research_interpretation", "Research Interpretation",
                  "The reasoning error in abstract, general terms.", role="explanation"),
        FieldSpec("why_this_pattern_occurs", "Why This Pattern Occurs", "Cognitive or situational factors."),
        FieldSpec("broader_implications", "Broader Implications", "What this suggests about human reasoning generally."),
        FieldSpec("related_cognitive_biases", "Related Cognitive Biases", "One to three related biases or concepts.", "list"),
    )),
}


@lru_cache
def _read_prompt(name: str) -> str:
    # Resolved relative to this file, so the server works from any working directory.
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


def system_prompt(mode: str) -> str:
    spec = MODES[mode]
    field_lines = []
    for f in spec.fields:
        hint = f" One of: {', '.join(f.choices)}." if f.kind == "enum" else ""
        hint += " A JSON array of strings." if f.kind == "list" else ""
        field_lines.append(f'- "{f.key}" ({f.title}): {f.guidance}{hint}')
    return "\n\n".join([
        _read_prompt("shared_rules"),
        _read_prompt(mode),
        "OUTPUT FORMAT:\nRespond with a single JSON object containing exactly these keys:\n" + "\n".join(field_lines),
    ])
