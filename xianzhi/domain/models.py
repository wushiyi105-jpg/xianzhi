"""领域模型：纯 dataclass。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    name: str
    original_price_cents: int
    bought_year: int | None = None
    used_years: float | None = None
    condition: str = "9成新"
    accessories: tuple[str, ...] = ()
    model: str = ""


@dataclass(frozen=True)
class MarketPrice:
    model: str
    low_cents: int
    high_cents: int
    collected: str = "2026-11"
    platform: str = "闲鱼/转转（在售挂价）"
    samples: int | None = None
    source_type: str = "estimate"

    @property
    def mid_cents(self) -> int:
        return (self.low_cents + self.high_cents) // 2


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str  # info / warn / high
    message: str
    evidence: str
    suggestion: str = ""


@dataclass
class Quote:
    suggested_cents: int
    low_cents: int
    high_cents: int
    floor_cents: int
    anchor: str  # market / formula
    findings: list[Finding] = field(default_factory=list)
    net: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
