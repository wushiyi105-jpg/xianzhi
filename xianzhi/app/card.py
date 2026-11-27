"""定价卡：区间、到手价、砍价话术、可直接贴的文案，一张卡全给。"""

from __future__ import annotations

from ..domain.catalog import detect_model, platforms, slang
from ..domain.models import Item, Quote
from ..domain.rules import condition


def _yuan(cents: int) -> str:
    return f"{cents / 100:.0f}"


def _detected_slang(text: str) -> list[dict[str, str]]:
    rows = []
    for row in slang().get("phrases", []):
        if row["word"] in text:
            rows.append(row)
    return rows


def build_card(item: Item, q: Quote, text: str) -> str:
    cond_name, cond_factor, cond_word = condition.detect_condition(text)
    defects = condition.detect_defects(text)
    platform_rows = platforms()["platforms"]
    guessed = item.model or detect_model(text, [])

    lines = [
        f"# 定价卡 · {item.name}",
        "",
        f"> 建议挂 **{_yuan(q.suggested_cents)} 元**，区间 **{_yuan(q.low_cents)}–{_yuan(q.high_cents)} 元**，"
        f"底价 **{_yuan(q.floor_cents)} 元**。依据：{'同型号行情' if q.anchor == 'market' else '折旧公式（未命中行情）'}。",
        "",
        f"型号：{guessed or '未填'}；成色：{cond_name}（系数 {cond_factor:.2f}，命中“{cond_word or '默认'}”）；"
        f"瑕疵：{'、'.join(defects) if defects else '未检出未被否定的瑕疵词'}。",
        "",
        "## 一、四个平台到手价",
        "",
        "| 平台 | 费率 | 到手价 | 说明 |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, cents in q.net.items():
        fee, is_recycle, note = platform_rows[name]["fee"], platform_rows[name]["recycle"], platform_rows[name]["note"]
        fee_text = "回收 8 折" if is_recycle else ("免佣" if fee == 0 else f"{fee:.0%}")
        lines.append(f"| {name} | {fee_text} | **{_yuan(cents)} 元** | {note} |")
    lines += [
        "",
        "## 二、买家砍价，三句话回",
        "",
        f"- **“{_yuan(q.low_cents)} 卖不卖？”**：这个价已经在区间下限了，我这台{cond_name}，"
        f"您可以先看看同款成色再比。",
        f"- **“{_yuan(q.floor_cents - 5000)} 面交立刻要。”**：面交可以，价格最低到 {_yuan(q.floor_cents)}，"
        "再低我就不出了，留着备用也不亏。",
        "- **“有划痕还卖这么贵？”**：划痕我写在描述里了，不藏着；接受这个成色再谈价，"
        "这个价是按同型号行情区间给的。",
        "",
        "## 三、可直接贴的文案",
        "",
        "```text",
        f"出 {guessed or item.name}，{cond_name}。",
        f"瑕疵：{'、'.join(defects) if defects else '成色见图，瑕疵如实描述'}。",
        f"心理价 {_yuan(q.suggested_cents)} 元，可小刀，屠龙刀不回。",
        "爽快的来，验货可当面，描述里写了的都认。",
        "```",
        "",
        "## 四、这段话里的暗语",
        "",
    ]
    rows = _detected_slang(text)
    if rows:
        lines += ["| 暗语 | 实际意思 | 风险 |", "| --- | --- | --- |"]
        for row in rows:
            lines.append(f"| {row['word']} | {row['means']} | {row['risk']} |")
    else:
        lines.append("- 没有命中暗语词典；描述按字面理解。")

    lines += ["", "## 五、定价提醒", ""]
    notes = list(q.notes)
    notes += [f"{f.message}（{f.evidence}）" for f in q.findings]
    lines += [f"- {n}" for n in notes] or ["- 没有额外风险。"]
    lines += [
        "",
        "---",
        "",
        "口径：行情是在售挂价区间，不是成交价；成交通常再低 5%–8%。"
        "底价 = 区间下限 × 0.93，低于这个不如留着自己用。",
        "",
    ]
    return "\n".join(lines)
