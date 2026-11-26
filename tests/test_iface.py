from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from xianzhi.config import Settings
from xianzhi.iface.cli import app
from xianzhi.iface.web import create_app

runner = CliRunner()


def test_quote_json_output(tmp_path):
    db = str(tmp_path / "cli.db")
    result = runner.invoke(
        app,
        ["quote", "--text", "iPhone 13 128G 九成新 无磕碰", "--model", "iPhone 13 128G",
         "--original", "5999", "--years", "3", "--json", "--db", db],
    )
    assert result.exit_code == 0, result.stdout
    assert '"anchor"' in result.stdout
    assert '"suggested"' in result.stdout


def test_history_lists_saved_row(tmp_path):
    db = str(tmp_path / "his.db")
    runner.invoke(app, ["quote", "--text", "Kindle Paperwhite 4 95新", "--original", "998", "--db", db])
    result = runner.invoke(app, ["history", "--limit", "2", "--db", db])
    assert result.exit_code == 0
    assert "Kindle" in result.stdout


def test_migrate_missing_db_exits_2(tmp_path):
    result = runner.invoke(app, ["migrate", "--db", str(tmp_path / "none.db")])
    assert result.exit_code == 2
    assert "没有这个库" in result.stdout


def test_doctor_after_quote_is_ok(tmp_path):
    db = str(tmp_path / "doc.db")
    runner.invoke(app, ["quote", "--text", "AirPods Pro 2 全新未拆", "--original", "1899", "--db", db])
    result = runner.invoke(app, ["doctor", "--db", db])
    assert result.exit_code == 0
    assert "ok" in result.stdout


def test_web_index_and_quote_roundtrip(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "web.db", llm_api_key="")
    client = TestClient(create_app(settings))
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    resp = client.post(
        "/quote",
        data={"text": "索尼 A7M3 95新 有轻微磕碰", "model": "索尼 A7M3", "original": "11999", "years": "2"},
    )
    assert resp.status_code == 200
    assert "建议" in resp.text or "元" in resp.text
