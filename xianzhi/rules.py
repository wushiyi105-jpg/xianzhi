"""闲置定价本地规则:折旧、成色、瑕疵、平台费率、文案、砍价、违禁词。"""

import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
YEAR_RE = re.compile(r"(20\d{2})\s*年?[买购入]")
USED_RE = re.compile(r"用了?\s*(\d+(?:\.\d+)?)\s*年")
FLAW_CAP = 0.30


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def detect_category(text):
    low = (text or "").lower()
    best, hits_best = None, []
    for c in load("categories.json")["categories"]:
        hits = [k for k in c["keywords"] if k.lower() in low]
        if len(hits) > len(hits_best):
            best, hits_best = c, hits
    return best, hits_best


def detect_condition(text):
    """成色按「命中的关键词最长」判,同长度按表顺序。

    成色词之间有重叠(「95新」「9成新」「九成新」都带「新」),
    只按表顺序取第一个会把「九成新」判成 95新,价格虚高。
    """
    text = text or ""
    conds = load("categories.json")["conditions"]
    best, best_len = None, 0
    for c in conds:
        for k in c["keywords"]:
            if k in text and len(k) > best_len:
                best, best_len = c, len(k)
    return best or conds[2]


def detect_years(text, this_year=2026):
    """「用了 N 年」比「哪年买的」更贴近实际磨损,两者都在时以它为准。"""
    text = text or ""
    m = USED_RE.search(text)
    if m:
        return max(1, int(float(m.group(1))))
    m = YEAR_RE.search(text)
    if m:
        return max(1, this_year - int(m.group(1)) + 1)
    return 2


# 否定前缀:「无拆修」「没有划痕」「不带盒子」是卖家在说自己没这个问题
NEG_HEADS = ("没有", "不带", "无", "没", "未", "不", "非")
# 关键词本身就是「缺什么」,以否定字开头属于正常表述,不能再判否定
NEG_KEYWORD_HEADS = ("无", "没", "非")


def _negated(text, idx, keyword):
    if keyword[:1] in NEG_KEYWORD_HEADS:
        return False
    head = text[max(0, idx - 3):idx]
    return any(head.endswith(p) for p in NEG_HEADS)


def detect_flaws(text):
    """按否定语义识别瑕疵:「无进水」不算进水,「原装电池两块」不算电池衰减。"""
    text = text or ""
    out = []
    for f in load("categories.json")["flaws"]:
        hit = False
        for k in f["keywords"]:
            start = 0
            while True:
                i = text.find(k, start)
                if i < 0:
                    break
                if not _negated(text, i, k):
                    hit = True
                    break
                start = i + 1
            if hit:
                break
        if hit:
            out.append(f)
    return out


def price(original, category, condition, years, flaws, floor=None):
    base = original * category["year1"] * (category["annual"] ** max(0, years - 1))
    base = max(base, original * category["floor"])
    coef = condition["coef"]
    deduct = min(FLAW_CAP, sum(f["deduct"] for f in flaws))
    suggested = base * coef * (1 - deduct)
    low = suggested * 0.85
    high = suggested * 1.12
    floor_price = round(floor) if floor else round(suggested * 0.80)
    return {
        "original": original,
        "base": round(base),
        "condition_coef": coef,
        "flaw_deduct": round(deduct, 2),
        "suggested": round(suggested),
        "low": round(low),
        "high": round(high),
        "floor_price": floor_price,
        "floor_from_user": bool(floor),
        "formula": "原价 × %.2f(首年留存)× %.2f^%d(年衰减)× %.2f(成色)× %.2f(瑕疵),下限为原价 %.0f%%"
                   % (category["year1"], category["annual"], max(0, years - 1), coef, 1 - deduct,
                      category["floor"] * 100),
    }


def platform_net(suggested):
    """到手价 = 挂价 × (1 - 费率) × (1 - 折价)。

    回收类平台(爱回收)不是抽成,而是按回收价收,通常在个人成交价的 8 折上下;
    只按费率算会得到「和闲鱼一样多」的假数字,比价表反而误导。
    """
    rows = []
    for p in load("platforms.json")["platforms"]:
        discount = p.get("discount", 0.0)
        rows.append({"name": p["name"], "fee": p["fee"], "discount": discount,
                     "net": round(suggested * (1 - p["fee"]) * (1 - discount)),
                     "audience": p["audience"], "days": p["days"], "extra": p["extra"]})
    return rows


def banned(text):
    hits = []
    low = (text or "").lower()
    for w in load("banned.json")["words"]:
        if w["word"].lower() in low:
            hits.append(w)
    return hits


def listing(category, condition, flaws, price_info, original, extra=""):
    title = "%s %s %s 闲置转让" % (condition["name"], category["name"], "自用")
    body = ["【成色】%s,实物如图" % condition["name"],
            "【购入】原价 %d 元,%s" % (original, extra or "自用,非商家货"),
            "【瑕疵】%s" % ("、".join(f["name"] for f in flaws) or "无明显瑕疵,细节见图"),
            "【配件】以图为准,缺件已标注",
            "【交易】平台内下单,当面验货,不议价勿拍"]
    tags = [category["name"], condition["name"], "个人闲置", "可小刀", "同城优先"]
    return {"title": title[:30], "body": "\n".join(body), "tags": tags}


def bargaining(ask, floor_price):
    """按砍价幅度给三档应答,底价以下不松口。"""
    rows = []
    tiers = [("小刀", 0.05, "接受,爽快成交"), ("中刀", 0.12, "让一步,守住中位"),
             ("大刀", 0.25, "婉拒,守底价")]
    for name, pct, move in tiers:
        offer = round(ask * (1 - pct))
        if offer >= floor_price:
            reply = "可以,按 %d 成交,今天能拍就改价。" % offer
        elif offer >= floor_price * 0.92:
            reply = "太低了,我最低 %d,能接受就拍。" % floor_price
        else:
            reply = "这个价出不了,我的底价是 %d,不合适就算了。" % floor_price
        rows.append({"tier": name, "pct": int(pct * 100), "offer": offer, "reply": reply})
    return rows


def checklist(text):
    checks = [
        ("实拍图", ["图", "照片", "实拍"], "至少 6 张:正面、背面、瑕疵、配件、序列号、包装"),
        ("序列号/型号", ["序列号", "型号", "sn", "imei"], "挡掉后四位再发图,防被套保"),
        ("购买凭证", ["发票", "小票", "订单", "凭证"], "有发票可多卖 5%–10%,没有就如实写"),
        ("瑕疵说明", ["划痕", "磕碰", "瑕疵", "维修"], "主动写瑕疵,退货率降一半"),
        ("配件清单", ["配件", "盒", "充电器", "包装"], "缺什么写什么,别等买家问"),
        ("交易方式", ["面交", "自提", "邮寄", "同城"], "大件写自提,数码写验货后确认"),
    ]
    out = []
    for name, keys, how in checks:
        ok = any(k in (text or "").lower() for k in keys)
        out.append({"item": name, "ok": ok, "how": how})
    return out


def analyze(text, original=None, this_year=2026, floor=None):
    cat, hits = detect_category(text)
    if cat is None:
        cat = load("categories.json")["categories"][0]
        cat_note = "未识别品类,按手机/平板估算,请用 --category 指定"
    else:
        cat_note = ""
    cond = detect_condition(text)
    years = detect_years(text, this_year)
    flaws = detect_flaws(text)
    orig = original or 0
    price_info = price(orig, cat, cond, years, flaws, floor=floor) if orig else None
    return {"category": cat, "category_note": cat_note, "category_hits": hits,
            "condition": cond, "years": years, "flaws": flaws,
            "price": price_info, "platforms": platform_net(price_info["suggested"]) if price_info else [],
            "banned": banned(text), "checklist": checklist(text),
            "listing": listing(cat, cond, flaws, price_info, orig) if price_info else None,
            "bargain": bargaining(price_info["suggested"], price_info["floor_price"]) if price_info else []}
