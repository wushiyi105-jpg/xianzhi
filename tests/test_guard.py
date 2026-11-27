from __future__ import annotations

from xianzhi.domain.engine import allowed_numbers
from xianzhi.domain.guard import guard
from xianzhi.domain.models import Item, Quote

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


def test_title_with_model_numbers_is_kept():
    q = Quote(152500, 140800, 164200, 122000, "formula", net={"闲鱼": 150900})
    item = Item("iPhone 13 128G 九成新", 599900, model="iPhone 13 128G")
    text = "iPhone 13 128G 九成新，128G 无拆修。"
    safe, dropped = guard(text, allowed_numbers(q, item))
    assert "iPhone 13 128G" in safe
    assert dropped == []
