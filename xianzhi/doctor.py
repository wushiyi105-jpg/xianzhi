"""自检：配置 / 数据库 / 行情表 / 模型 / webhook。"""

from __future__ import annotations

import sqlite3

import httpx

from .config import Settings


def _db(settings: Settings) -> tuple[bool, str]:
    try:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if r[0] != "alembic_version"
        }
        conn.close()
    except Exception as exc:  # noqa: BLE001
        return False, f"{settings.db_path} 不可写：{exc}"
    return (True, f"{settings.db_path}（{len(tables)} 张表）") if tables else (False, "还没有表，先跑一次 quote")


def _market() -> tuple[bool, str]:
    from .domain.engine import load_market

    try:
        data = load_market()
        return True, f"{len(data)} 个型号（估算，非实时）"
    except Exception as exc:  # noqa: BLE001
        return False, f"行情表读取失败：{exc}"


def _llm(settings: Settings) -> tuple[bool, str]:
    if not settings.llm_enabled:
        return True, "未配置 API key，走离线模式"
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                f"{settings.llm_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
        return resp.status_code < 400, f"{settings.llm_model} · HTTP {resp.status_code}"
    except httpx.HTTPError as exc:
        return False, f"连不上：{exc}"


def _webhook(settings: Settings) -> tuple[bool, str]:
    if not settings.webhook_url:
        return True, "未配置 webhook，跳过推送"
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.post(settings.webhook_url, json={"msg_type": "text", "content": {"text": "xianzhi doctor 探活"}})
        return 200 <= resp.status_code < 300, f"HTTP {resp.status_code}"
    except httpx.HTTPError as exc:
        return False, f"连不上：{exc}"


def run_doctor(settings: Settings) -> list[tuple[str, bool, str]]:
    return [
        ("config", True, f"db={settings.db_path} 偏离阈值={settings.deviation_threshold:.0%}"),
        ("database", *_db(settings)),
        ("market", *_market()),
        ("llm", *_llm(settings)),
        ("webhook", *_webhook(settings)),
    ]
