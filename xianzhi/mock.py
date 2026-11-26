"""离线模式:挂牌建议、风险与买家问题,结构与模型模式一致。"""

from __future__ import annotations


def offline(r):
    tips, risks, qs = [], [], []
    p = r["price"]
    if p:
        tips.append("先按 %d 挂,留出 %d 元砍价空间,别一上来就报底价。" % (p["high"], p["high"] - p["floor_price"]))
        tips.append("标题写「成色 + 品类 + 关键配置」,前 12 个字决定点开率。")
        tips.append("瑕疵主动写在第 2 行,比藏在图里退货率低。")
        if r["flaws"]:
            tips.append("有 %s,先拍特写图,避免到手刀。" % "、".join(f["name"] for f in r["flaws"]))
        tips.append("同城优先,大件写自提;数码写「当面验机,验完不退」。")
    else:
        tips.append("先补原价和购入年份,否则只能给方法,给不了价。")
        tips.append("按同款二手实际成交价的中位数,再减 5%–8% 作为挂牌价(经验值,非统计)。")

    if r["banned"]:
        risks.append("描述里有 %d 个违禁/导流词:会被限流或下架,先删。" % len(r["banned"]))
    risks.append("买家最常见到手刀:以「和描述不符」压价,实拍与瑕疵说明是唯一防线。")
    risks.append("拒绝站外付款与「先寄后付」,平台担保外的交易几乎没有追回可能。")
    risks.append("数码类先抹掉序列号后四位,防止被人套保或报失。")
    for f in r["flaws"][:2]:
        risks.append("「%s」是主要压价点,成交前明确写进描述并留图。" % f["name"])

    qs.append("「最低多少出?」→ 报区间下限,不要直接报底价。")
    qs.append("「能包邮吗?」→ 运费按实收,或写「邮费到付」。")
    qs.append("「有发票/保修吗?」→ 如实答,没有就说没有,别承诺保修。")
    qs.append("「能便宜点马上拍?」→ 只让 5%,并要求当场下单。")
    return {"tips": tips[:6], "risks": risks[:6], "buyer_questions": qs[:6]}
