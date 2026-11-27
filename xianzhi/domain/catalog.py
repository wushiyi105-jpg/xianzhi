"""本地定价知识：成色系数、平台费率、暗语与型号别名。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[2] / "data"


def _load(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def condition_table() -> list[tuple[str, str, float]]:
    return [
        (alias, row["name"], float(row["factor"]))
        for row in _load("condition_factors.json")["conditions"]
        for alias in row["aliases"]
    ]


@lru_cache(maxsize=1)
def defect_words() -> list[str]:
    return list(_load("condition_factors.json")["defects"])


@lru_cache(maxsize=1)
def negations() -> list[str]:
    return list(_load("condition_factors.json")["negations"])


@lru_cache(maxsize=1)
def platforms() -> dict[str, Any]:
    return _load("platforms.json")


@lru_cache(maxsize=1)
def slang() -> dict[str, Any]:
    return _load("slang.json")


def model_aliases() -> dict[str, str]:
    return dict(slang().get("models", {}))


def detect_model(text: str, known: list[str] | None = None) -> str:
    """先认型号全称，再认暗语别名；返回空串表示没认出来。"""
    for model in known or []:
        if model and model in text:
            return model
    aliases = sorted(model_aliases().items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, model in aliases:
        if alias in text:
            return model
    return ""
