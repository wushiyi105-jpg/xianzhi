"""迁移是真的：空库 upgrade 建表，downgrade base 拆掉，再 upgrade 回得去。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect

from xianzhi.adapters.store import alembic_config


def test_upgrade_creates_tables_matching_model(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    cfg = alembic_config(db)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert {"quotes", "alembic_version"} <= names

    cols = {c["name"] for c in inspect(engine).get_columns("quotes")}
    assert cols == {
        "id",
        "item",
        "model",
        "anchor",
        "suggested_cents",
        "low_cents",
        "high_cents",
        "floor_cents",
        "net_json",
        "created_at",
    }


def test_downgrade_and_upgrade_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "round.db"
    cfg = alembic_config(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(f"sqlite:///{db}")
    assert "quotes" not in set(inspect(engine).get_table_names())

    command.upgrade(cfg, "head")
    assert "quotes" in set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
