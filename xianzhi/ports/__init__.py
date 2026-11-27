"""端口：应用与 domain 只认这里的协议，SQLAlchemy 实现放 adapters。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import Quote, QuoteRecord


@runtime_checkable
class StorePort(Protocol):
    def save(self, item: str, model: str, quote: Quote) -> int: ...

    def recent(self, limit: int = 10) -> list[QuoteRecord]: ...
