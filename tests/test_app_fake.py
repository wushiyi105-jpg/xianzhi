"""主用例不碰 SQLite：内存假实现跑通报价 + 落库。"""

from __future__ import annotations

from xianzhi.app.run import quote_and_save
from xianzhi.domain.models import Item, Quote, QuoteRecord
from xianzhi.ports import StorePort


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Quote]] = []

    def save(self, item: str, model: str, quote: Quote) -> int:
        self.calls.append((item, model, quote))
        return 7

    def recent(self, limit: int = 10) -> list[QuoteRecord]:
        return []


def test_quote_and_save_uses_injected_store_only() -> None:
    fake = FakeStore()
    store: StorePort = fake
    item = Item(name="iPhone 13 128G 国行", original_price_cents=599900)
    q, row_id = quote_and_save(store, item, {}, 0.25)
    assert row_id == 7
    assert q.suggested_cents > 0
    assert fake.calls[0][0] == item.name
