"""编排:折旧、成色、平台费率、文案、砍价话术全在本地;模型只写挂牌建议与风险。

金额一律以本地定价为准:模型输出里的价格都会被 strip_money 换成「该价格」,
避免「建议挂 1200」和本地算出的 980 打架。
"""

from __future__ import annotations

import re

from . import llm, mock, rules

JSON_ONLY = "只输出 JSON,不要输出解释或多余文字。"
MONEY_RE = re.compile(r"(¥|￥)?\s*\d+(?:\.\d+)?\s*(?:元|块|k|K|千)(?:出头|左右)?")


def _use_model(config, force_mock):
    if force_mock:
        return False
    return bool({**llm.default_config(), **(config or {})}.get("api_key"))


def _cfg(config):
    return {**llm.default_config(), **(config or {})}


def strip_money(text):
    return MONEY_RE.sub("该价格", text).replace("该价格该价格", "该价格")


def summary(r):
    p = r["price"]
    if not p:
        return "缺少原价,算不出折旧;补一句「原价 3299,2023 年买的」即可。"
    return ("%s %s,用了约 %d 年,建议挂 %d 元(区间 %d–%d),底价 %d 元。"
            % (r["category"]["name"], r["condition"]["name"], r["years"],
               p["suggested"], p["low"], p["high"], p["floor_price"]))


def _model_advice(r, config):
    p = r["price"] or {}
    flaws = "、".join(f["name"] for f in r["flaws"]) or "无"
    raw = llm.chat([{
        "role": "system",
        "content": ("你是二手交易顾问。只根据给定的品类、成色、瑕疵、平台费率与本地定价说话;"
                    "不要写任何金额数字,价格由系统给出;不要建议站外交易或虚假描述。"),
    }, {
        "role": "user",
        "content": (
            "品类:%s 成色:%s 使用年限:%s 瑕疵:%s 本地建议价:%s 元(区间 %s–%s)\n平台:%s\n违禁词:%s\n"
            "%s\n输出格式:{\"tips\":[\"挂牌技巧,3-5 条\"],\"risks\":[\"交易风险\"],"
            "\"buyer_questions\":[\"买家可能问的问题及怎么答\"]}"
            % (r["category"]["name"], r["condition"]["name"], r["years"], flaws,
               p.get("suggested"), p.get("low"), p.get("high"),
               "、".join("%s(费率 %.1f%%)" % (x["name"], x["fee"] * 100) for x in r["platforms"]),
               "、".join(w["word"] for w in r["banned"]) or "无", JSON_ONLY)
        ),
    }], config=_cfg(config), temperature=0.4, max_tokens=2000)
    d = llm.extract_json(raw)
    return {"tips": [strip_money(str(x)) for x in d.get("tips", [])][:6],
            "risks": [strip_money(str(x)) for x in d.get("risks", [])][:6],
            "buyer_questions": [strip_money(str(x)) for x in d.get("buyer_questions", [])][:6]}


def quote(text, original=None, config=None, db=None, force_mock=False, save=False):
    r = rules.analyze(text, original=original)
    r["text"] = text
    if _use_model(config, force_mock):
        layers = _model_advice(r, config)
        mode = "model"
    else:
        layers = mock.offline(r)
        mode = "offline"
    r.update({"verdict": summary(r), "mode": mode, "saved_id": None, **layers})
    if db is not None and save:
        r["saved_id"] = db.save(r)
    return r
