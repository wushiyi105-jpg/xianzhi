"""SQLite 持久化：报价记录 + Alembic 建表。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import DateTime, Integer, String, create_engine, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

MIGRATIONS_DIR = Path(__file__).resolve().parents[2]


class Base(DeclarativeBase):
    pass


class QuoteRow(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item: Mapped[str] = mapped_column(String(300))
    model: Mapped[str] = mapped_column(String(120), default="")
    anchor: Mapped[str] = mapped_column(String(16))
    suggested_cents: Mapped[int] = mapped_column(Integer)
    low_cents: Mapped[int] = mapped_column(Integer)
    high_cents: Mapped[int] = mapped_column(Integer)
    floor_cents: Mapped[int] = mapped_column(Integer)
    net_json: Mapped[str] = mapped_column(String, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def alembic_config(db_path: Path) -> Config:
    cfg = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def ensure_schema(db_path: Path, engine) -> None:
    """没有 alembic_version 时：有旧表就 stamp 到 head，没有就 upgrade 建表。"""
    tables = set(inspect(engine).get_table_names())
    cfg = alembic_config(db_path)
    if "alembic_version" not in tables:
        if tables:
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
        return
    command.upgrade(cfg, "head")


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        ensure_schema(db_path, self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def save(self, item: str, model: str, quote) -> int:
        with self.session_factory() as s:
            row = QuoteRow(
                item=item[:300],
                model=model[:120],
                anchor=quote.anchor,
                suggested_cents=quote.suggested_cents,
                low_cents=quote.low_cents,
                high_cents=quote.high_cents,
                floor_cents=quote.floor_cents,
                net_json=json.dumps(quote.net, ensure_ascii=False),
            )
            s.add(row)
            s.commit()
            return row.id

    def recent(self, limit: int = 10) -> list[QuoteRow]:
        with self.session_factory() as s:
            return list(s.scalars(select(QuoteRow).order_by(QuoteRow.id.desc()).limit(limit)).all())
