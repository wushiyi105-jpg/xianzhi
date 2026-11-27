"""成色与瑕疵：最长词匹配 + 否定句过滤。"""

from __future__ import annotations

from ..catalog import condition_table, defect_words, negations
from ..models import Finding

# 长词在前：九成新必须先于 9成新 命中（顺序由 data/condition_factors.json 保证）
CONDITION_TABLE = condition_table()
DEFECT_WORDS = defect_words()
NEGATIONS = negations()


def detect_condition(text: str) -> tuple[str, float, str | None]:
    """返回（成色名，系数，命中的词）。长词优先。"""
    for word, name, factor in CONDITION_TABLE:
        if word in text:
            return name, factor, word
    return "9成新", 0.58, None


def _negated(text: str, index: int) -> bool:
    window = text[max(0, index - 3) : index]
    return any(neg in window for neg in NEGATIONS)


def detect_defects(text: str) -> list[str]:
    """只算没被否定的瑕疵。'无划痕' 不算。"""
    found: list[str] = []
    for word in DEFECT_WORDS:
        start = 0
        while True:
            idx = text.find(word, start)
            if idx < 0:
                break
            if not _negated(text, idx):
                found.append(word)
                break
            start = idx + len(word)
    return found


def findings(text: str, defects: list[str]) -> list[Finding]:
    out: list[Finding] = []
    if defects:
        out.append(
            Finding(
                rule_id="condition.defects",
                severity="warn" if len(defects) <= 1 else "high",
                message=f"检出 {len(defects)} 处瑕疵：{'、'.join(defects)}",
                evidence="从描述中匹配到未被否定的瑕疵词",
                suggestion="在文案里主动写明，可减少砍价",
            )
        )
    return out
