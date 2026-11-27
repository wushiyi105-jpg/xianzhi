"""端口口径：配置默认值 = Dockerfile EXPOSE = README 命令。"""

from __future__ import annotations

from pathlib import Path

from xianzhi.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_default_port_is_8020() -> None:
    assert Settings().port == 8020


def test_dockerfile_exposes_same_port() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "EXPOSE 8020" in text
    assert '"--port", "8020"' in text
