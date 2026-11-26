"""定价：年限、公式折旧、行情锚定。"""

from __future__ import annotations

from ..models import Finding, Item, MarketPrice

# 品类首年留存与年衰减（手机/数码）
DIGITAL_FIRST_YEAR = 0.55
DIGITAL_YEARLY = 0.82
# 家电曲线更平
APPLIANCE_FIRST_YEAR = 0.68
APPLIANCE_YEARLY = 0.92
APPLIANCE_FLOOR = 0.30

APPLIANCE_WORDS = ["冰箱", "洗衣机", "空调", "微波炉", "洗碗机", "电视", "热水器"]


def is_appliance(text: str) -> bool:
    return any(w in text for w in APPLIANCE_WORDS)


def effective_years(item: Item) -> float:
    """'2021 年买的' + '用了 4 年'：以使用年数为准。"""
    if item.used_years is not None:
        return max(item.used_years, 0.0)
    if item.bought_year is not None:
        return max(2026 - item.bought_year, 0.0)
    return 1.0


def formula_price(item: Item, condition_factor: float) -> int:
    years = effective_years(item)
    if is_appliance(item.name):
        residual = APPLIANCE_FIRST_YEAR * (APPLIANCE_YEARLY ** max(years - 1, 0))
        residual = max(residual, APPLIANCE_FLOOR)
        factor = 0.73 if condition_factor <= 0.58 else condition_factor
    else:
        residual = DIGITAL_FIRST_YEAR * (DIGITAL_YEARLY ** max(years - 1, 0))
        factor = condition_factor
    return int(item.original_price_cents * residual * factor)


def anchor(item: Item, market: dict[str, MarketPrice], formula_cents: int, threshold: float) -> tuple[int, int, int, str, list[Finding], list[str]]:
    """返回（建议价, 低, 高, 依据, findings, notes）。"""
    findings: list[Finding] = []
    notes: list[str] = []
    entry = market.get(item.model) if item.model else None

    if entry is None:
        notes.append("未命中行情：仅公式参考，通常偏低，建议先搜同款成交价")
        findings.append(
            Finding(
                rule_id="pricing.no_market",
                severity="warn",
                message="没有该型号的行情",
                evidence=f"型号='{item.model or '未填'}'，行情表未覆盖",
                suggestion="补型号后可重新定价",
            )
        )
        return formula_cents, int(formula_cents * 0.92), int(formula_cents * 1.08), "formula", findings, notes

    dev = (entry.mid_cents - formula_cents) / entry.mid_cents if entry.mid_cents else 0.0
    if abs(dev) >= threshold:
        findings.append(
            Finding(
                rule_id="pricing.deviation",
                severity="info",
                message=f"公式与行情偏差 {dev:+.0%}",
                evidence=f"公式 {formula_cents / 100:.0f}，行情 {entry.mid_cents / 100:.0f}",
                suggestion="两者都是估算，以实际成交价为准",
            )
        )
        notes.append("公式折旧与行情估算偏差较大，两个都只作参考")
    return entry.mid_cents, entry.low_cents, entry.high_cents, "market", findings, notes


def floor_price(low_cents: int) -> int:
    return int(low_cents * 0.93)
