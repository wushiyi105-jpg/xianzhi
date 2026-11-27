"""新功能：30 型号行情、暗语识别、一张定价卡。"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from xianzhi.domain.catalog import detect_model, platforms
from xianzhi.domain.engine import load_market
from xianzhi.iface.cli import app

runner = CliRunner()


def test_market_has_thirty_models() -> None:
    assert len(load_market()) >= 30


def test_slang_alias_resolves_model() -> None:
    assert detect_model("苹果13 九成新 无拆修", list(load_market())) == "iPhone 13 128G"


def test_card_writes_all_sections(tmp_path) -> None:
    out = tmp_path / "定价卡.md"
    result = runner.invoke(
        app,
        ["card", "--text", "iPhone 13 128G 九成新 无拆修 边框有划痕", "--out", str(out)],
    )
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert "四个平台到手价" in body
    assert "买家砍价，三句话回" in body
    assert "可直接贴的文案" in body
    assert "暗语" in body


def test_card_uses_alias_when_model_missing(tmp_path) -> None:
    out = tmp_path / "alias.md"
    result = runner.invoke(app, ["card", "--text", "苹果13 九成新 无拆修", "--out", str(out)])
    assert result.exit_code == 0
    assert "iPhone 13 128G" in out.read_text(encoding="utf-8")


def test_card_needs_model_or_original(tmp_path) -> None:
    result = runner.invoke(app, ["card", "--text", "一个没有型号的东西", "--out", str(tmp_path / "x.md")])
    assert result.exit_code == 2


def test_platforms_data_is_loaded() -> None:
    assert set(platforms()["platforms"]) == {"闲鱼", "转转", "爱回收", "红布林"}
    assert len(Path("data/platforms.json").read_text(encoding="utf-8")) > 10
