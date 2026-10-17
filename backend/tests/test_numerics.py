import pytest

from mindtrace.numerics import extract_numbers


@pytest.mark.parametrize(
    "text, expected",
    [
        ("speed was 60 km/h", {60}),
        ("10,000 users and 3.5 hours", {10000, 3.5}),
        ("I got -3", {3}),
        ("It is 120/90", {120, 90, 1.333333}),
        ("forty-eight", {48}),
        ("thirty thousand", {30000}),
        ("two hundred and five", {205}),
        ("five six", {5, 6}),
        ("one and two", {1, 2}),
        ("a 15% rise", {15}),
    ],
)
def test_extract_numbers(text, expected):
    found = extract_numbers(text)
    assert {round(v, 6) for v in expected} <= found


def test_no_numbers_in_plain_text():
    assert extract_numbers("Someone assumed the opposite direction.") == set()


def test_labels_glued_to_letters_are_not_numbers():
    assert extract_numbers("x2 and v1.2.3 are labels") == set()
