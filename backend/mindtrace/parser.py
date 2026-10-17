"""Turn raw model output into validated field values for a mode.

Primary path: the JSON object Ollama's structured output produces.
Fallback: a lenient header parser for plain text (handles "**Header:**", "## Header",
"- Header: value"), matching only the headers the mode defines, so ordinary sentences
that end in a colon are never mistaken for sections.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mindtrace.modes import FieldSpec, ModeSpec

Value = str | list[str]


class ParseError(ValueError):
    """The output could not be mapped onto the mode's fields."""


@dataclass
class ParsedAnalysis:
    values: dict[str, Value] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    def joined_text(self) -> str:
        parts = []
        for value in self.values.values():
            parts.append("\n".join(value) if isinstance(value, list) else value)
        return "\n".join(parts)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start: end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


_HEADER_DECOR = re.compile(r"^\s*(?:[-*•]\s+|#{1,6}\s*|\d+[.)]\s+)?\**\s*")


def _parse_text(spec: ModeSpec, raw: str) -> dict[str, str]:
    titles = sorted(spec.fields, key=lambda f: len(f.title), reverse=True)
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        undecorated = _HEADER_DECOR.sub("", stripped)
        matched = None
        for f in titles:
            m = re.match(rf"{re.escape(f.title)}\s*\**\s*:\s*\**\s*(.*)$", undecorated, re.IGNORECASE)
            if m or undecorated.rstrip("*: ").lower() == f.title.lower():
                matched = (f, m.group(1).strip() if m else "")
                break
        if matched:
            f, rest = matched
            current = f.key
            sections[current] = [rest] if rest else []
        elif current:
            sections[current].append(re.sub(r"^[-*•]\s+", "", stripped))
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _coerce(f: FieldSpec, value: Any) -> Value | None:
    if value is None:
        return None
    if f.kind == "list":
        items = value if isinstance(value, list) else re.split(r"[,;\n]", str(value))
        cleaned = [re.sub(r"^[-*•\d.)\s]+", "", str(i)).strip() for i in items]
        cleaned = [c for c in cleaned if c]
        return cleaned[:3] or None
    text = (", ".join(map(str, value)) if isinstance(value, list) else str(value)).strip()
    if not text:
        return None
    if f.kind == "enum":
        lowered = text.lower().strip(" .*-")
        for choice in f.choices:
            if lowered == choice.lower() or lowered.startswith(choice.lower()):
                return choice
        return None
    return text


def parse_model_output(spec: ModeSpec, raw: str) -> ParsedAnalysis:
    data = _extract_json(raw)
    if data is not None:
        by_slug = {_slug(k): v for k, v in data.items()}
        source = {f.key: by_slug.get(f.key, by_slug.get(_slug(f.title))) for f in spec.fields}
    else:
        source = _parse_text(spec, raw)

    result = ParsedAnalysis()
    for f in spec.fields:
        value = _coerce(f, source.get(f.key))
        if value is None:
            result.missing.append(f.key)
        else:
            result.values[f.key] = value

    explanation = next(f.key for f in spec.fields if f.role == "explanation")
    if explanation not in result.values:
        raise ParseError("model output did not contain the main explanation field")
    return result
