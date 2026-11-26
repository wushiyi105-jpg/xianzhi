"""0.x → 1.0 数据迁移：旧库先备份，转换成功后原子替换；失败保留原文件。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .store import Store


def _backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}.bak-{stamp}.db")
    backup.write_bytes(db_path.read_bytes())
    return backup


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _legacy_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM quotes ORDER BY id").fetchall()
    finally:
        conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        detail = data.get("detail") or "{}"
        try:
            parsed = json.loads(detail)
        except (TypeError, ValueError):
            parsed = {}
        price = parsed.get("price") or {}
        category = (parsed.get("category") or {}).get("name") or data.get("category") or "闲置"
        suggested = price.get("suggested") or data.get("suggested") or 0
        low = price.get("low") or int(suggested * 0.92)
        high = price.get("high") or int(suggested * 1.08)
        floor = price.get("floor_price") or int(low * 0.93)
        net = {}
        for item in parsed.get("platforms") or []:
            name = item.get("name")
            if name and item.get("net") is not None:
                net[name] = int(item["net"]) * 100
        out.append(
            {
                "item": str(category)[:300],
                "model": "",
                "anchor": "formula",
                "suggested_cents": int(round(float(suggested) * 100)),
                "low_cents": int(round(float(low) * 100)),
                "high_cents": int(round(float(high) * 100)),
                "floor_cents": int(round(float(floor) * 100)),
                "net_json": json.dumps(net, ensure_ascii=False),
            }
        )
    return out


def migrate(db_path: Path) -> dict[str, Any]:
    """返回 {status, backup, rows}。status: created / upgraded / converted / current。"""
    if not db_path.exists():
        Store(db_path)
        return {"status": "created", "backup": None, "rows": 0}

    backup = _backup(db_path)
    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cols = _columns(conn, "quotes") if "quotes" in tables else set()
    finally:
        conn.close()

    if {"suggested_cents"} <= cols:
        if "alembic_version" in tables:
            return {"status": "current", "backup": str(backup), "rows": 0}
        Store(db_path)
        return {"status": "upgraded", "backup": str(backup), "rows": 0}

    if "quotes" not in tables:
        raise ValueError("库里有未知表结构，未改动原文件")

    rows = _legacy_rows(db_path)
    tmp = db_path.with_name(db_path.stem + ".migrating.db")
    if tmp.exists():
        tmp.unlink()
    try:
        store = Store(tmp)
        with store.session_factory() as session:
            from .store import QuoteRow

            for row in rows:
                session.add(QuoteRow(**row))
            session.commit()
        store.engine.dispose()
        tmp.replace(db_path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    return {"status": "converted", "backup": str(backup), "rows": len(rows)}
