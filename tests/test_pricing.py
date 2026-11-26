from __future__ import annotations

from xianzhi.domain.engine import load_market, quote
from xianzhi.domain.models import Item
from xianzhi.domain.rules import condition, fees, pricing

MARKET = load_market()


def test_condition_prefers_longest_match():
    name, factor, word = condition.detect_condition("iPhone 13 九成新")
    assert name == "9成新" and word == "九成新"
    assert factor == 0.58  # 不是 95新 的 0.72


def test_95_new_maps_to_its_own_tier():
    name, factor, _ = condition.detect_condition("95新 只拆封")
    assert name == "95新" and abs(factor - 0.72) < 1e-9


def test_negated_defects_do_not_count():
    assert condition.detect_defects("无拆修 无进水 屏幕无划痕") == []


def test_real_defect_is_detected():
    assert condition.detect_defects("边框有划痕") == ["划痕"]


def test_used_years_wins_over_bought_year():
    item = Item(name="冰箱", original_price_cents=429900, bought_year=2021, used_years=4)
    assert pricing.effective_years(item) == 4


def test_appliance_has_floor():
    item = Item(name="海尔冰箱", original_price_cents=429900, used_years=6)
    value = pricing.formula_price(item, 0.58)
    assert value >= int(429900 * 0.30 * 0.73)


def test_market_hit_uses_market_range():
    item = Item(name="iPhone 13 128G 九成新", original_price_cents=599900, used_years=4, model="iPhone 13 128G")
    q = quote(item, MARKET)
    assert q.anchor == "market"
    assert q.low_cents <= q.suggested_cents <= q.high_cents


def test_missing_market_falls_back_with_warning():
    item = Item(name="杂牌空气炸锅", original_price_cents=29900, used_years=2, model="")
    q = quote(item, MARKET)
    assert q.anchor == "formula"
    assert any(n.startswith("未命中行情") for n in q.notes)


def test_floor_below_range_low():
    item = Item(name="iPhone 13 128G", original_price_cents=599900, used_years=3, model="iPhone 13 128G")
    q = quote(item, MARKET)
    assert q.floor_cents < q.low_cents


def test_net_prices_respect_fees_and_recycle_discount():
    net, _ = fees.net_prices(100_000)
    assert net["闲鱼"] == 100_000
    assert net["红布林"] == 85_000
    assert net["爱回收"] == 80_000


def test_recycle_gap_finding_emitted():
    _, found = fees.net_prices(100_000)
    assert any(f.rule_id == "fees.recycle_gap" for f in found)
