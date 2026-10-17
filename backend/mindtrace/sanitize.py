"""Input cleaning and prompt assembly.

Unlike the old analyzer, user text is NOT rewritten ("km/h" stays "km/h", "x=5" stays
"x=5"). Rewriting symbols into words mangled the input and made the output guardrail
fire whenever the model quoted the student. Instead, user text is fenced in tags the
system prompt tells the model to treat as data.
"""

from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_FENCE_TAGS = re.compile(r"</?\s*(problem|reasoning)\s*>", re.IGNORECASE)
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


def clean_user_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    # Stop user text from closing our fence and smuggling in "instructions".
    text = _FENCE_TAGS.sub(lambda m: m.group(0).replace("<", "‹").replace(">", "›"), text)
    text = _MANY_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def build_user_prompt(problem: str, reasoning: str) -> str:
    return (
        f"<problem>\n{problem}\n</problem>\n\n"
        f"<reasoning>\n{reasoning}\n</reasoning>\n\n"
        "Analyse the reasoning mistake. Do not solve, calculate, or reveal the answer."
    )
