"""引擎：把规则串成一份可解释的报价。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Item, MarketPrice, Quote
from .rules import condition, fees, pricing

DATA = Path(__file__).resolve().parents[2] / "data" / "market.json"


def load_market(path: Path | None = None) -> dict[str, MarketPrice]:
    raw = json.loads((path or DATA).read_text(encoding="utf-8"))
    out: dict[str, MarketPrice] = {}
    for row in raw["prices"]:
        out[row["model"]] = MarketPrice(
            model=row["model"],
            low_cents=row["low_cents"],
            high_cents=row["high_cents"],
            collected=row.get("collected", "2026-11"),
            platform=row.get("platform", "闲鱼/转转（在售挂价）"),
            samples=row.get("samples"),
            source_type=row.get("source_type", "estimate"),
        )
    return out


def quote(item: Item, market: dict[str, MarketPrice], deviation_threshold: float = 0.25) -> Quote:
    cond_name, cond_factor, _ = condition.detect_condition(item.name)
    defects = condition.detect_defects(item.name)
    formula = pricing.formula_price(item, cond_factor)
    suggested, low, high, anchor, f1, notes = pricing.anchor(
        item, market, formula, deviation_threshold
    )
    net, f2 = fees.net_prices(suggested)
    findings = condition.findings(item.name, defects) + f1 + f2
    return Quote(
        suggested_cents=suggested,
        low_cents=low,
        high_cents=high,
        floor_cents=pricing.floor_price(low),
        anchor=anchor,
        findings=findings,
        net=net,
        notes=notes,
    )


def allowed_numbers(q: Quote, item: Item | None = None) -> set[str]:
    nums = {
        f"{q.suggested_cents / 100:.0f}",
        f"{q.low_cents / 100:.0f}",
        f"{q.high_cents / 100:.0f}",
        f"{q.floor_cents / 100:.0f}",
    }
    nums |= {f"{v / 100:.0f}" for v in q.net.values()}
    if item is not None:
        nums |= set(re.findall(r"\d+(?:\.\d+)?", item.model))
        nums |= set(re.findall(r"\d+", item.name))
    return nums
