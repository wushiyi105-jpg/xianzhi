"""用例：报价 + 落库；只依赖 domain 与 ports，不认识 SQLAlchemy。"""

from __future__ import annotations

from ..domain.engine import quote
from ..domain.models import Item, MarketPrice, Quote
from ..ports import StorePort


def price_only(item: Item, market: dict[str, MarketPrice], deviation_threshold: float = 0.25) -> Quote:
    return quote(item, market, deviation_threshold)


def quote_and_save(
    store: StorePort,
    item: Item,
    market: dict[str, MarketPrice],
    deviation_threshold: float = 0.25,
) -> tuple[Quote, int]:
    q = quote(item, market, deviation_threshold)
    row_id = store.save(item.name, item.model, q)
    return q, row_id
