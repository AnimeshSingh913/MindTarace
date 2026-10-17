"""Extract the numeric values mentioned in a piece of text, in digits or in words.

Used by the guardrail: an analysis that mentions a number which appears nowhere in
the problem or the person's reasoning is the strongest general signal of a leaked
answer, however it is phrased ("comes out to", "lands on", "forty-eight", ...).
"""

from __future__ import annotations

import re

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_SCALES = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}

_FRACTION = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?![\w.])")
_DIGITS = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d*\.?\d+")
_WORD = re.compile(r"[a-z]+")


def _norm(value: float) -> float:
    return round(abs(value), 6)


def _digit_numbers(text: str) -> set[float]:
    found: set[float] = set()
    for num, den in _FRACTION.findall(text):
        found.update({_norm(float(num)), _norm(float(den))})
        if float(den):
            found.add(_norm(float(num) / float(den)))
    for match in _DIGITS.findall(text):
        try:
            found.add(_norm(float(match.replace(",", ""))))
        except ValueError:
            continue
    return found


def _word_numbers(text: str) -> set[float]:
    found: set[float] = set()
    total = current = 0
    in_number = False
    previous = ""

    def flush() -> None:
        nonlocal total, current, in_number
        if in_number:
            found.add(_norm(total + current))
        total = current = 0
        in_number = False

    for word in _WORD.findall(text.lower().replace("-", " ")):
        if word in _UNITS or word in _TENS:
            # "five six" is two numbers; "forty two" is one.
            if in_number and not (previous in _TENS and word in _UNITS) and previous not in (
                "hundred", "and", *_SCALES
            ):
                flush()
            current += _UNITS.get(word, 0) + _TENS.get(word, 0)
            in_number = True
        elif word == "hundred" and in_number:
            current = (current or 1) * 100
        elif word in _SCALES and in_number:
            total += (current or 1) * _SCALES[word]
            current = 0
        elif word == "and" and in_number and previous in ("hundred", *_SCALES):
            pass  # "two hundred and five"
        else:
            flush()
        previous = word
    flush()
    return found


def extract_numbers(text: str) -> set[float]:
    return _digit_numbers(text) | _word_numbers(text)
