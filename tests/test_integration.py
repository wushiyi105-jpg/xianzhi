"""集成测试:HTTP 服务、模型层、CLI 三条链路各跑一遍真实路径。

单测只测规则函数;这里关心的是「接上之后还能不能正常工作」——
HTTP 真的起服务、模型返回真的按本仓 schema 解析、CLI 真的走子进程。
"""

import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from xianzhi import agent, llm, web
from xianzhi import db as dbmod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE = "iPhone 13 128G,95新,2023年买的,电池健康 82%,屏幕有细微划痕,无盒"


class TestHttpLayer(unittest.TestCase):
    """真起 ThreadingHTTPServer,随机端口,走真实 HTTP。"""

    @classmethod
    def setUpClass(cls):
        cls.db = dbmod.Database(os.path.join(ROOT, "data", "_test_http.db"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), web._handler(cls.db, {}, True))
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _get(self, path):
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, payload):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_page_served(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("二手定价助手", body)
        # 页面必须自己渲染区间与到手价,这两个数是本仓的核心卖点
        self.assertIn("区间", body)
        self.assertIn("平台到手", body)
        # 行情锚点与偏离提示必须出现在页面脚本里,否则前端只能显示公式口径
        self.assertIn("行情锚点", body)
        self.assertIn("以行情为准", body)
        # 来源与覆盖率也要在前端露出来,避免「以行情为准」被读成实时抓取
        self.assertIn("行情来源", body)
        self.assertIn("未抓取(无样本量)", body)
        self.assertIn("行情覆盖", body)

    def test_status_mock(self):
        status, body = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"mock": True, "model": None})

    def test_quote_numbers(self):
        status, r = self._post("/api/quote", {"text": PHONE, "original": "5999"})
        self.assertEqual(status, 200)
        self.assertEqual(r["mode"], "offline")
        # 行情锚点口径:iPhone 13 128G 95新 落在 1500–2200 的真实成交带里
        self.assertEqual(r["price"]["source"], "market")
        self.assertEqual(r["price"]["suggested"], 1599)
        self.assertEqual(r["price"]["low"], 1476)
        self.assertEqual(r["price"]["high"], 1722)
        self.assertEqual(r["model"], "iPhone 13")
        self.assertEqual([p["name"] for p in r["platforms"]],
                         ["闲鱼", "转转", "爱回收", "红布林"])

    def test_quote_flags_formula_gap(self):
        # 原价公式只给 1042,行情给 1599,偏离 -35% 以上必须提示,不能悄悄用公式
        status, r = self._post("/api/quote", {"text": PHONE, "original": "5999"})
        self.assertEqual(status, 200)
        self.assertEqual(r["price"]["formula_suggested"], 1042)
        self.assertTrue(r["price"]["gap_alert"])

    def test_quote_floor_applied(self):
        status, r = self._post("/api/quote", {"text": PHONE, "original": "5999", "floor": "1800"})
        self.assertEqual(status, 200)
        self.assertEqual(r["price"]["floor_price"], 1800)
        self.assertTrue(r["price"]["floor_from_user"])

    def test_quote_saved_to_db(self):
        status, r = self._post("/api/quote", {"text": PHONE, "original": "5999"})
        self.assertEqual(status, 200)
        self.assertIsInstance(r["saved_id"], int)
        rows = self.db.latest(5)
        self.assertTrue(any(row["id"] == r["saved_id"] for row in rows))

    def test_unknown_path_404(self):
        status, r = self._post("/api/nope", {})
        self.assertEqual(status, 404)
        self.assertIn("error", r)


class FakeLLM:
    """按本仓 schema 回:{"tips": [], "risks": [], "buyer_questions": []}。"""

    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def __call__(self, messages, **kwargs):
        self.prompts.append(messages)
        return json.dumps(self.payload, ensure_ascii=False)


class TestModelLayer(unittest.TestCase):
    def setUp(self):
        self.cfg = {"api_key": "test-key", "base_url": "http://127.0.0.1:9", "model": "fake"}

    def _run(self, payload, text=PHONE, original=5999, **kwargs):
        fake = FakeLLM(payload)
        with mock.patch.object(llm, "chat", fake):
            r = agent.quote(text, original=original, config=self.cfg, **kwargs)
        return r, fake

    def test_schema_fields(self):
        r, fake = self._run({"tips": ["标题写清成色"], "risks": ["拒绝站外付款"],
                             "buyer_questions": ["能包邮吗?"], "extra": "忽略"})
        self.assertEqual(r["mode"], "model")
        self.assertEqual(r["tips"], ["标题写清成色"])
        self.assertEqual(r["risks"], ["拒绝站外付款"])
        self.assertEqual(r["buyer_questions"], ["能包邮吗?"])
        self.assertFalse(hasattr(r, "extra"))
        self.assertNotIn("extra", r["tips"])
        # 提示词里必须带上本仓的本地定价,否则模型会自己编价
        self.assertIn("本地建议价", fake.prompts[0][1]["content"])

    def test_model_money_is_stripped(self):
        r, _ = self._run({"tips": ["建议挂 1200 元,底价 900 元"], "risks": [], "buyer_questions": []})
        self.assertEqual(r["tips"], ["建议挂该价格,底价该价格"])
        self.assertNotIn("1200", r["tips"][0])
        self.assertEqual(r["price"]["suggested"], 1599)

    def test_force_mock_wins_over_key(self):
        r, fake = self._run({"tips": ["x"], "risks": [], "buyer_questions": []}, force_mock=True)
        self.assertEqual(r["mode"], "offline")
        self.assertEqual(fake.prompts, [])
        self.assertTrue(r["tips"])

    def test_short_lists_are_cut(self):
        payload = {"tips": ["t%d" % i for i in range(9)], "risks": [], "buyer_questions": []}
        r, _ = self._run(payload)
        self.assertEqual(len(r["tips"]), 6)


class TestCliLayer(unittest.TestCase):
    """真开子进程,断言退出码与 stderr。"""

    def _run(self, args, stdin=None):
        return subprocess.run(
            [sys.executable, "-m", "xianzhi"] + args,
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", input=stdin,
        )

    def test_quote_file_ok(self):
        r = self._run(["--mock", "quote", "--file", "examples/case-01.txt", "--original", "5999"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("建议挂 1525 元", r.stdout)
        self.assertIn("行情锚点:iPhone 13(128G)95新无瑕疵 1800–2100 元", r.stdout)
        # 公式价与行情偏离时必须让用户看见,不能只打印一个新数字
        self.assertIn("偏离 -38%(偏离过大,以行情为准)", r.stdout)
        self.assertIn("爱回收", r.stdout)
        self.assertIn("折价 20%", r.stdout)
        # 行情是这个工具的地基,来源/日期/样本量/挂价口径必须打在输出里
        self.assertIn("行情来源:2026-11", r.stdout)
        self.assertIn("样本量:未抓取(无样本量)", r.stdout)
        self.assertIn("在售挂价(非成交价)", r.stdout)
        self.assertIn("非实时", r.stdout)

    def test_quote_formula_warns_no_market(self):
        # 没有型号命中时必须直说「无行情参考,公式值通常偏低」,不能默默给个低价
        r = self._run(["--mock", "quote", "--file", "examples/case-02.txt", "--original", "4299"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("无行情参考(内置 29 个型号", r.stdout)
        self.assertIn("公式值通常偏低", r.stdout)
        self.assertIn("行情覆盖:内置 29 个型号", r.stdout)
        self.assertIn("其余仅公式参考(可能偏低)", r.stdout)

    def test_quote_market_without_original(self):
        r = self._run(["--mock", "quote", "--text", "iPhone 13 128G 95新 电池健康 85% 无拆修"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("按行情锚点(iPhone 13)", r.stdout)
        self.assertNotIn("原价 0", r.stdout)

    def test_quote_no_input_exit_2(self):
        r = self._run(["--mock", "quote"], stdin="")
        self.assertEqual(r.returncode, 2)
        self.assertIn("没有描述", r.stderr)

    def test_quote_missing_file_exit_2(self):
        r = self._run(["--mock", "quote", "--file", "examples/_not_here.txt", "--original", "5999"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("读不到文件", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_quote_floor_flag(self):
        r = self._run(["--mock", "quote", "--text", PHONE, "--original", "5999", "--floor", "1800"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("底价 1800 元(按你填的底价)", r.stdout)

    def test_platforms_command(self):
        r = self._run(["platforms"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("爱回收", r.stdout)
        self.assertIn("红布林", r.stdout)

    def test_history_empty(self):
        tmp = os.path.join(ROOT, "data", "_test_cli_empty.db")
        if os.path.exists(tmp):
            os.remove(tmp)
        r = self._run(["--db", tmp, "history"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("还没有记录", r.stdout)


if __name__ == "__main__":
    unittest.main()
