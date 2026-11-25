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

    def test_no_original(self):
        r = agent.quote(sample(), force_mock=True)
        self.assertIsNone(r["price"])
        self.assertTrue(r["tips"])

    def test_strip_money(self):
        self.assertNotIn("1200", agent.strip_money("建议挂 1200 元"))

    def test_verdict_has_price(self):
        r = agent.quote(sample(), original=5999, force_mock=True)
        self.assertIn("建议挂", r["verdict"])


if __name__ == "__main__":
    unittest.main()

