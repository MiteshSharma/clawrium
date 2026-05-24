"""Tests for kubectl-style AGE formatter."""

import pytest

from clawrium.cli.output.age import format_age


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "0s"),
        (1, "1s"),
        (59, "59s"),
        (60, "1m"),
        (61, "1m"),
        (3599, "59m"),
        (3600, "1h"),
        (3661, "1h"),
        (86399, "23h"),
        (86400, "1d"),
        (86401, "1d"),
        (8640000, "100d"),
    ],
)
def test_boundary_table(seconds: int, expected: str) -> None:
    assert format_age(seconds) == expected


def test_negative_clamps_to_zero() -> None:
    assert format_age(-1) == "0s"
    assert format_age(-10000) == "0s"
