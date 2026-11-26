from __future__ import annotations

from xianzhi.domain.guard import guard

ALLOWED = {"1525", "1408", "1642", "1220"}


def test_allowed_numbers_kept():
    text = "建议挂 1525 元，区间 1408–1642。"
    safe, dropped = guard(text, ALLOWED)
    assert safe == text and dropped == []


def test_invented_number_drops_sentence():
    text = "建议挂 1525 元。原价 8888 元。"
    safe, dropped = guard(text, ALLOWED)
    assert "8888" in dropped
    assert "1525" in safe and "8888" not in safe
