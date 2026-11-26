import unittest

from xianzhi import agent, rules


def sample():
    return "iPhone 13 128G,95新,2023年买的,电池健康 82%,屏幕有细微划痕,无盒"


class TestCategory(unittest.TestCase):
    def test_phone(self):
        cat, hits = rules.detect_category(sample())
        self.assertEqual(cat["key"], "phone")
        self.assertTrue(hits)

    def test_furniture(self):
        cat, _ = rules.detect_category("宜家沙发,9成新")
        self.assertEqual(cat["key"], "furniture")

    def test_default(self):
        cat, hits = rules.detect_category("随便一个东西")
        self.assertIsNone(cat)
        self.assertEqual(hits, [])

    def test_condition_match(self):
        cond = rules.detect_condition(sample())
        self.assertEqual(cond["key"], "good")

    def test_condition_default(self):
        self.assertEqual(rules.detect_condition("无描述")["key"], "good")


class TestYears(unittest.TestCase):
    def test_purchase_year(self):
        self.assertEqual(rules.detect_years("2023年买的"), 4)

    def test_used_years(self):
        self.assertEqual(rules.detect_years("用了3年"), 3)

    def test_default(self):
        self.assertEqual(rules.detect_years("不知道什么时候买的"), 2)

    def test_zero_year_floor(self):
        self.assertEqual(rules.detect_years("2026年买的"), 1)


class TestPrice(unittest.TestCase):
    def test_formula_first_year(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("99新")
        p = rules.price(5000, cat, cond, 1, [])
        self.assertEqual(p["base"], 3100)
        self.assertEqual(p["suggested"], round(3100 * 0.86))

    def test_floor_applies(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("8成新")
        p = rules.price(1000, cat, cond, 10, [])
        self.assertGreaterEqual(p["base"], 100)

    def test_flaw_deduction(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("95新")
        flaws = rules.detect_flaws("进水了")
        p = rules.price(5000, cat, cond, 2, flaws)
        self.assertLess(p["suggested"], rules.price(5000, cat, cond, 2, [])["suggested"])

    def test_flaw_cap(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("95新")
        flaws = rules.detect_flaws("划痕 电池 拆修 无盒 进水")
        p = rules.price(5000, cat, cond, 2, flaws)
        self.assertLessEqual(p["flaw_deduct"], rules.FLAW_CAP)

    def test_range_order(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("95新")
        p = rules.price(3000, cat, cond, 2, [])
        self.assertLess(p["low"], p["suggested"])
        self.assertLess(p["suggested"], p["high"])

    def test_floor_price(self):
        cat, _ = rules.detect_category("手机")
        p = rules.price(3000, cat, rules.detect_condition("95新"), 2, [])
        self.assertEqual(p["floor_price"], round(p["suggested"] * 0.8))


class TestPlatformsAndBanned(unittest.TestCase):
    def test_platform_fee(self):
        rows = rules.platform_net(1000)
        zhuan = [r for r in rows if r["name"] == "转转"][0]
        self.assertEqual(zhuan["net"], 985)

    def test_xianyu_no_fee(self):
        rows = rules.platform_net(1000)
        xy = [r for r in rows if r["name"] == "闲鱼"][0]
        self.assertEqual(xy["net"], 1000)

    def test_banned_wechat(self):
        hits = rules.banned("加微信详聊")
        self.assertTrue(any(h["type"] == "导流" for h in hits))

    def test_banned_clean(self):
        self.assertEqual(rules.banned("95新,自用,无拆修"), [])


class TestListingAndBargain(unittest.TestCase):
    def test_title_length(self):
        cat, _ = rules.detect_category("手机")
        p = rules.price(5000, cat, rules.detect_condition("95新"), 2, [])
        item = rules.listing(cat, rules.detect_condition("95新"), [], p, 5000)
        self.assertLessEqual(len(item["title"]), 30)

    def test_bargain_three_tiers(self):
        rows = rules.bargaining(1000, 800)
        self.assertEqual(len(rows), 3)
        self.assertGreater(rows[0]["offer"], rows[2]["offer"])

    def test_bargain_holds_floor(self):
        rows = rules.bargaining(1000, 800)
        self.assertIn("800", rows[2]["reply"])

    def test_checklist_flags(self):
        checks = rules.checklist("有实拍图和发票,无盒")
        names = [c["item"] for c in checks if not c["ok"]]
        self.assertIn("序列号/型号", names)


class TestAgent(unittest.TestCase):
    def test_offline_structure(self):
        r = agent.quote(sample(), original=5999, force_mock=True)
        self.assertEqual(r["mode"], "offline")
        for k in ("tips", "risks", "buyer_questions", "listing", "bargain"):
            self.assertTrue(r[k])

    def test_no_original_no_model(self):
        r = agent.quote("宜家沙发,9成新,搬家急出", force_mock=True)
        self.assertIsNone(r["price"])
        self.assertTrue(r["tips"])

    def test_strip_money(self):
        self.assertNotIn("1200", agent.strip_money("建议挂 1200 元"))

    def test_verdict_has_price(self):
        r = agent.quote(sample(), original=5999, force_mock=True)
        self.assertIn("建议挂", r["verdict"])


class TestNegationRegression(unittest.TestCase):
    """闲鱼文案爱写「无拆修、无进水、屏幕无划痕」,这些否定句不是瑕疵。"""

    def test_negated_flaws_ignored(self):
        self.assertEqual(rules.detect_flaws("无拆修 无进水 屏幕无划痕 无磕碰"), [])

    def test_positive_flaw_kept(self):
        names = [f["name"] for f in rules.detect_flaws("屏幕有明显划痕")]
        self.assertIn("屏幕/外观划痕", names)

    def test_negated_keyword_is_flaw(self):
        # 「无盒」本身就是在说缺配件,不能再当否定句跳过
        names = [f["name"] for f in rules.detect_flaws("手机 无盒")]
        self.assertIn("缺配件/无盒", names)

    def test_battery_pack_not_decay(self):
        # 「原装电池两块」是配件,不是衰减;只有电池健康/续航这类才算
        self.assertEqual(rules.detect_flaws("原装电池两块 无拆修"), [])

    def test_battery_health_counts(self):
        names = [f["name"] for f in rules.detect_flaws("电池健康 85%")]
        self.assertIn("电池/续航衰减", names)

    def test_clean_phone_not_capped(self):
        cat, _ = rules.detect_category("手机")
        cond = rules.detect_condition("95新")
        p = rules.price(5999, cat, cond, 4, rules.detect_flaws("95新 无拆修 无进水 屏幕无划痕"))
        self.assertEqual(p["flaw_deduct"], 0)


class TestConditionOverlapRegression(unittest.TestCase):
    """「九成新」不等于「95新」:同一条描述按 95新算会虚高约 24%。"""

    def test_jiuchengxin_is_9(self):
        self.assertEqual(rules.detect_condition("自用 九成新")["key"], "fair")
        self.assertEqual(rules.detect_condition("自用 9成新")["key"], "fair")

    def test_95xin_is_good(self):
        self.assertEqual(rules.detect_condition("95新")["key"], "good")

    def test_gap_between_two_conditions(self):
        cat, _ = rules.detect_category("手机")
        a = rules.price(5999, cat, rules.detect_condition("95新"), 4, [])["suggested"]
        b = rules.price(5999, cat, rules.detect_condition("九成新"), 4, [])["suggested"]
        self.assertGreater(a / b, 1.2)


class TestPlatformNetRegression(unittest.TestCase):
    """爱回收是按回收价收,不是按挂价收;只按费率算会得到和闲鱼一样的假数字。"""

    def test_aihuishou_discount(self):
        rows = rules.platform_net(1000)
        ai = [r for r in rows if r["name"] == "爱回收"][0]
        self.assertEqual(ai["discount"], 0.20)
        self.assertEqual(ai["net"], 800)

    def test_hongbulin_ten_percent(self):
        rows = rules.platform_net(1000)
        hb = [r for r in rows if r["name"] == "红布林"][0]
        self.assertEqual(hb["net"], 900)

    def test_sale_platforms_unchanged(self):
        rows = rules.platform_net(1000)
        self.assertEqual([r["net"] for r in rows if r["name"] == "闲鱼"][0], 1000)
        self.assertEqual([r["net"] for r in rows if r["name"] == "转转"][0], 985)

    def test_gap_between_platforms(self):
        rows = {r["name"]: r["net"] for r in rules.platform_net(942)}
        self.assertGreater(rows["闲鱼"] - rows["爱回收"], 150)


class TestYearsConflictRegression(unittest.TestCase):
    """「2021 年买的」+「用了 4 年」同时出现时,按使用年限算,不能取更旧的年份。"""

    def test_used_years_wins(self):
        self.assertEqual(rules.detect_years("2021 年买的 用了4年"), 4)

    def test_year_only(self):
        self.assertEqual(rules.detect_years("2023年买的"), 4)

    def test_used_only(self):
        self.assertEqual(rules.detect_years("用了3年"), 3)


class TestUserFloor(unittest.TestCase):
    def test_floor_overrides_formula(self):
        r = agent.quote("iPhone 13 95新", original=5999, force_mock=True, floor=500)
        self.assertEqual(r["price"]["floor_price"], 500)
        self.assertTrue(r["price"]["floor_from_user"])

    def test_floor_default_is_formula(self):
        r = agent.quote("iPhone 13 95新", original=5999, force_mock=True)
        self.assertFalse(r["price"]["floor_from_user"])

    def test_bargain_respects_user_floor(self):
        r = agent.quote("iPhone 13 95新", original=5999, force_mock=True, floor=1200)
        self.assertTrue(all("1200" in b["reply"] or b["offer"] >= 1200 for b in r["bargain"]))


class TestMarketAnchor(unittest.TestCase):
    """3C 二手看同型号当前行情,不看当年买价;原价公式只做参考并提示偏离。"""

    PHONE = "iPhone 13 128G,95新,2023年买的,电池健康 82%,屏幕有细微划痕,无盒"

    def test_seed_table_is_broad_enough(self):
        models = rules.load("market.json")["models"]
        self.assertGreaterEqual(len(models), 20)
        for m in models:
            self.assertTrue(m["ranges"].get("default"))

    def test_iphone13_lands_in_real_band(self):
        p, _ = rules.pricing(self.PHONE, *self._ctx(self.PHONE), original=5999)
        self.assertEqual(p["source"], "market")
        # 2026 年 iPhone 13 128G 95新 正常成交在 1500–2200,不能再给 1000 以下
        self.assertGreaterEqual(p["suggested"], 1500)
        self.assertLessEqual(p["suggested"], 2200)

    def test_market_price_works_without_original(self):
        p, _ = rules.pricing("iPhone 13 128G 95新 电池健康 85% 无拆修",
                             *self._ctx("iPhone 13 128G 95新"), original=None)
        self.assertIsNotNone(p)
        self.assertEqual(p["source"], "market")
        self.assertGreaterEqual(p["suggested"], 1500)

    def test_unknown_model_falls_back_to_formula(self):
        text = "海尔 465L 冰箱 用了4年 8成新 有磕碰 制冷正常"
        p, model = rules.pricing(text, *self._ctx(text), original=4299)
        self.assertIsNone(model)
        self.assertEqual(p["source"], "formula")

    def test_gap_alert_when_formula_far_off(self):
        text = "LV Neverfull 中号 专柜购买 有小票 95新 五金无氧化 无磨损"
        p, model = rules.pricing(text, *self._ctx(text), original=12000)
        self.assertEqual(model["name"], "LV Neverfull MM")
        self.assertLess(p["formula_gap"], -0.4)
        self.assertTrue(p["gap_alert"])

    def test_storage_changes_price(self):
        a, _ = rules.pricing("iPhone 13 128G 95新", *self._ctx("iPhone 13 128G 95新"))
        b, _ = rules.pricing("iPhone 13 256G 95新", *self._ctx("iPhone 13 256G 95新"))
        self.assertGreater(b["suggested"], a["suggested"])

    def test_longest_alias_wins(self):
        m = rules.detect_model("iPhone 13 Pro 128G 国行")
        self.assertEqual(m["name"], "iPhone 13 Pro")

    def test_condition_adjusts_market_price(self):
        base = "iPhone 13 128G,"
        prices = [rules.pricing(base + c, *self._ctx(base + c))[0]["suggested"]
                  for c in ("99新", "95新", "9成新", "8成新")]
        self.assertEqual(prices, sorted(prices, reverse=True))

    @staticmethod
    def _ctx(text):
        cat, _ = rules.detect_category(text)
        return (cat, rules.detect_condition(text), rules.detect_years(text), rules.detect_flaws(text))


if __name__ == "__main__":
    unittest.main()

