from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from xianzhi.adapters.migrate import migrate
from xianzhi.adapters.store import Store
from xianzhi.config import Settings
from xianzhi.doctor import run_doctor


def _legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE quotes (id INTEGER PRIMARY KEY, category TEXT, condition TEXT,"
        " years REAL, original REAL, suggested REAL, detail TEXT)"
    )
    detail = {
        "category": {"name": "手机"},
        "price": {"suggested": 1200, "low": 1104, "high": 1296, "floor_price": 1026},
        "platforms": [{"name": "闲鱼", "net": 1200}, {"name": "转转", "net": 1188}],
    }
    conn.execute(
        "INSERT INTO quotes (category, condition, years, original, suggested, detail) VALUES (?,?,?,?,?,?)",
        ("手机", "9成新", 2, 3999, 1200, json.dumps(detail, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def test_migrate_legacy_quotes(tmp_path):
    db = tmp_path / "legacy.db"
    _legacy_db(db)
    result = migrate(db)
    assert result["status"] == "converted"
    assert result["rows"] == 1
    assert Path(result["backup"]).exists()
    rows = Store(db).recent(5)
    assert rows[0].item == "手机"
    assert rows[0].anchor == "formula"
    assert rows[0].suggested_cents == 120000
    assert rows[0].floor_cents == 102600
    assert json.loads(rows[0].net_json)["闲鱼"] == 120000


def test_migrate_unknown_schema_keeps_original(tmp_path):
    db = tmp_path / "odd.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nope (id INTEGER PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError):
        migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()[0] == "nope"
    conn.close()


def test_migrate_current_db_is_idempotent(tmp_path):
    db = tmp_path / "new.db"
    Store(db).recent(1)
    assert migrate(db)["status"] == "current"
    assert migrate(db)["status"] == "current"


def test_migrate_missing_db_creates_schema(tmp_path):
    db = tmp_path / "absent.db"
    result = migrate(db)
    assert result["status"] == "created"
    assert db.exists()


def test_doctor_reports_ok_without_keys(tmp_path):
    settings = Settings(db_path=tmp_path / "doctor.db", llm_api_key="", webhook_url="")
    checks = {name: (ok, detail) for name, ok, detail in run_doctor(settings)}
    assert checks["config"][0] is True
    assert checks["market"][0] is True
    assert "离线模式" in checks["llm"][1]
    assert "跳过" in checks["webhook"][1]
    # 空库没有表，database 项应按设计报 fail，让用户先跑 quote
    assert checks["database"][0] is False
