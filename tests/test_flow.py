from __future__ import annotations

from xianzhi.adapters.store import Store
from xianzhi.domain.engine import load_market, quote
from xianzhi.domain.models import Item

MARKET = load_market()


def test_store_round_trip(tmp_path):
    store = Store(tmp_path / "x.db")
    item = Item(name="iPhone 13 128G", original_price_cents=599900, used_years=3, model="iPhone 13 128G")
    q = quote(item, MARKET)
    rid = store.save(item.name, item.model, q)
    assert rid > 0
    rows = store.recent(5)
    assert rows and rows[0].suggested_cents == q.suggested_cents


def test_deviation_finding_when_formula_far_from_market():
    # 原价很低但行情高 → 偏差大，应提示
    item = Item(name="索尼 A7M3", original_price_cents=200000, used_years=2, model="索尼 A7M3")
    q = quote(item, MARKET)
    assert any(f.rule_id == "pricing.deviation" for f in q.findings)
    assert q.notes


def test_no_market_no_deviation_finding():
    item = Item(name="杂牌耳机", original_price_cents=19900, used_years=1)
    q = quote(item, MARKET)
    assert not any(f.rule_id == "pricing.deviation" for f in q.findings)
