"""数字守卫：模型话术里出现报价之外的数字，整句丢弃。"""

from __future__ import annotations

import re

NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
IGNORE = {"0", "1", "2", "3"}


def extract_numbers(text: str) -> list[str]:
    return [m.replace(",", "") for m in NUMBER_RE.findall(text)]


def guard(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    allowed_norm = {a.replace(",", "") for a in allowed}
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in re.split(r"(?<=[。！？!?\n])", text):
        if not sentence.strip():
            continue
        bad = [n for n in extract_numbers(sentence) if n not in allowed_norm and n not in IGNORE]
        if bad:
            dropped.extend(bad)
            continue
        kept.append(sentence)
    return "".join(kept).strip(), dropped
