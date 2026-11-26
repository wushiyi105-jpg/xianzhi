"""成色与瑕疵：最长词匹配 + 否定句过滤。"""

from __future__ import annotations

from ..models import Finding

# 长词在前：九成新必须先于 9成新 命中
CONDITION_TABLE: list[tuple[str, str, float]] = [
    ("全新未拆", "全新", 0.90),
    ("全新", "全新", 0.88),
    ("99新", "99新", 0.80),
    ("95新", "95新", 0.72),
    ("九成新", "9成新", 0.58),
    ("9成新", "9成新", 0.58),
    ("九成", "9成新", 0.58),
    ("8成新", "8成新", 0.50),
    ("八成新", "8成新", 0.50),
    ("7成新", "7成新", 0.42),
    ("有磕碰", "6成新", 0.35),
]

DEFECT_WORDS = ["划痕", "拆修", "进水", "磕碰", "掉漆", "鼓包", "烧屏", "老化", "裂纹"]
NEGATIONS = ["无", "没有", "不", "未", "非"]


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
