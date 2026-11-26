"""命令行入口:python -m xianzhi <命令>。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, agent, llm, rules
from . import db as dbmod
from .llm import LLMError

BANNER = ("⚠️  当前为离线模式(未配置 LLM_API_KEY):折旧、区间、平台到手价、文案与砍价话术由本地给出。\n"
          "   填入 LLM_API_KEY 后,挂牌建议与风险由模型撰写(金额仍以本地定价为准)。\n")


def render(r):
    mode = "模型" if r["mode"] == "model" else "离线模式"
    lines = ["🏷  闲置定价  [%s]" % mode, "", "📌 " + r["verdict"], ""]
    if r.get("category_note"):
        lines.append("注:" + r["category_note"])
        lines.append("")

    lines.append("🔎 识别")
    lines.append("  品类:%s(%s)" % (r["category"]["name"], "命中 " + "、".join(r["category_hits"])
                                     if r["category_hits"] else "按默认"))
    lines.append("  成色:%s(系数 %.2f)" % (r["condition"]["name"], r["condition"]["coef"]))
    lines.append("  使用:%d 年" % r["years"])
    if r["flaws"]:
        lines.append("  瑕疵:" + "、".join("%s(-%d%%)" % (f["name"], f["deduct"] * 100) for f in r["flaws"]))
    lines.append("")

    p = r["price"]
    if p:
        lines.append("💰 定价")
        if p.get("source") == "market":
            lo, hi = p["market_base"]
            lines.append("  行情区间:%s(%s)95新无瑕疵 %d–%d 元"
                         % (p["model"], (p["storage"] + "G") if p.get("storage") else "默认容量", lo, hi))
            meta = p.get("market_meta") or {}
            lines.append("  行情来源:%s · %s · 样本量:%s · %s(非成交价)"
                         % (meta.get("collected", "?"), meta.get("platform", "?"),
                            "未抓取(无样本量)" if meta.get("samples") is None else meta["samples"],
                            "在售挂价" if meta.get("basis") == "asking" else "成交价"))
            lines.append("  成色 ×%.2f,瑕疵 -%d%% → 建议挂 %d 元(区间 %d–%d),底价 %d 元%s"
                         % (p["condition_adj"], p["flaw_deduct"] * 100, p["suggested"],
                            p["low"], p["high"], p["floor_price"],
                            "(按你填的底价)" if p.get("floor_from_user") else ""))
            if p.get("formula_suggested") is not None:
                gap = p["formula_gap"] * 100
                fmt = rules.GAP_COMPARE_FMT if p.get("gap_alert") else rules.GAP_CLOSE_FMT
                lines.append("  参考对比:" + fmt % (p["formula_suggested"], p["suggested"], gap))
            lines.append("  口径:同型号当前二手行情 × 成色 × 瑕疵,不按当年买价折旧(行情为估算,非实测)")
            lines.append("  注意:行情为 %s 整理的估算区间,非实时;%s"
                         % (meta.get("collected", "?"), rules.DEAL_HINT))
        else:
            lines.append("  原价 %d → 残值基数 %d(首年 %.0f%%,其后每年 ×%.2f,下限 %.0f%%)"
                         % (p["original"], p["base"], r["category"]["year1"] * 100,
                            r["category"]["annual"], r["category"]["floor"] * 100))
            lines.append("  成色 ×%.2f,瑕疵 -%d%% → 建议挂 %d 元(区间 %d–%d),底价 %d 元%s"
                         % (p["condition_coef"], p["flaw_deduct"] * 100, p["suggested"],
                            p["low"], p["high"], p["floor_price"],
                            "(按你填的底价)" if p.get("floor_from_user") else ""))
            lines.append("  公式:" + p["formula"])
            if p.get("residual_pct") is not None:
                lines.append("  残值率:原价的 %.0f%%%s"
                             % (p["residual_pct"] * 100,
                                "(已触到品类下限,实际成交通常更高)" if p.get("floor_hit") else ""))
            if p.get("market_hint"):
                lines.append("  ⚠️ " + p["market_hint"])
            cov = r.get("market_coverage") or {}
            if cov:
                lines.append("  行情覆盖:内置 %d 个型号(%s),其余仅公式参考(可能偏低)"
                             % (cov["models"], "、".join(cov["categories"])))
        lines.append("")
        lines.append("🏪 各平台到手(按建议价)")
        for x in r["platforms"]:
            tail = " 折价 %.0f%%" % (x["discount"] * 100) if x.get("discount") else ""
            lines.append("  · %s 费率 %.1f%%%s → 到手 %d 元(%s, %s)"
                         % (x["name"], x["fee"] * 100, tail, x["net"], x["days"], x["extra"]))
        lines.append("")

    if r["listing"]:
        lines.append("📝 文案")
        lines.append("  标题:" + r["listing"]["title"])
        for x in r["listing"]["body"].splitlines():
            lines.append("  " + x)
        lines.append("  标签:" + " ".join("#" + t for t in r["listing"]["tags"]))
        lines.append("")

    if r["bargain"]:
        lines.append("🗣 砍价三档(底价 %d)" % p["floor_price"])
        for b in r["bargain"]:
            lines.append("  · %s -%d%% → 对方出 %d:%s" % (b["tier"], b["pct"], b["offer"], b["reply"]))
        lines.append("")

    if r["banned"]:
        lines.append("🚫 违禁/导流词")
        for w in r["banned"]:
            lines.append("  · 「%s」[%s]%s → %s" % (w["word"], w["type"], w["why"], w["fix"]))
        lines.append("")

    lines.append("📷 挂牌体检")
    for c in r["checklist"]:
        lines.append("  %s %s —— %s" % ("✅" if c["ok"] else "❌", c["item"], c["how"]))
    lines.append("")

    if r["tips"]:
        lines.append("💡 挂牌建议")
        for t in r["tips"]:
            lines.append("  · " + t)
        lines.append("")
    if r["risks"]:
        lines.append("🚩 交易风险")
        for t in r["risks"]:
            lines.append("  · " + t)
        lines.append("")
    if r["buyer_questions"]:
        lines.append("❓ 买家会问")
        for t in r["buyer_questions"]:
            lines.append("  · " + t)
    return "\n".join(lines)


def _text(args):
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                return f.read()
        except UnicodeError:
            print("❌ 文件不是 UTF-8 编码:%s" % args.file, file=sys.stderr)
            sys.exit(2)
        except OSError as e:
            print("❌ 读不到文件 %s:%s" % (args.file, e.strerror or e), file=sys.stderr)
            sys.exit(2)
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def cmd_quote(args):
    text = _text(args)
    if not text.strip():
        print("❌ 没有描述:用 --text、--file 或管道输入。", file=sys.stderr)
        sys.exit(2)
    db = dbmod.Database(args.db) if args.db else dbmod.Database()
    r = agent.quote(text, original=args.original, config=llm.config_from_args(args),
                    db=db, force_mock=args.mock, save=args.save, floor=args.floor)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(render(r))
    if r.get("saved_id"):
        print("\n已入库(#%d),`python -m xianzhi history` 可回看。" % r["saved_id"])


def cmd_platforms(args):
    rows = rules.load("platforms.json")["platforms"]
    print("🏪 平台费率")
    for p in rows:
        print("  · %s:费率 %.1f%%,%s;%s(%s)" % (p["name"], p["fee"] * 100, p["audience"], p["days"], p["extra"]))


def cmd_banned(args):
    rows = rules.load("banned.json")["words"]
    print("🚫 违禁与导流词(%d 个)" % len(rows))
    for w in rows:
        print("  · [%s] %s —— %s;改法:%s" % (w["type"], w["word"], w["why"], w["fix"]))


def cmd_history(args):
    rows = dbmod.Database(args.db).latest(args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("还没有记录。`python -m xianzhi quote --text \"...\" --original 3299 --save` 存一条。")
        return
    print("🏷 估价记录")
    for r in rows:
        print("  #%d  %s  %s  %s 年  原价 %s → 建议 %s  %s"
              % (r["id"], r["category"], r["condition"], r["years"],
                 r["original"] or "—", r["suggested"] or "—", r["created_at"]))


def cmd_web(args):
    from . import web
    web.serve(host=args.host, port=args.port, db_path=args.db, force_mock=args.mock)


def build_parser():
    p = argparse.ArgumentParser(prog="xianzhi", description="闲置 · 二手定价与挂牌文案。")
    p.add_argument("--version", action="version", version="xianzhi %s" % __version__)
    p.add_argument("--mock", action="store_true", help="强制离线模式")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    p.add_argument("--model", help="覆盖 LLM_MODEL")
    p.add_argument("--base-url", help="覆盖 LLM_BASE_URL")
    p.add_argument("--api-key", help="覆盖 LLM_API_KEY")
    p.add_argument("--db", help="SQLite 路径")
    sub = p.add_subparsers(dest="command", required=True)

    qp = sub.add_parser("quote", help="估价并生成挂牌文案")
    qp.add_argument("--text", help="商品描述:品类、成色、购买时间、瑕疵")
    qp.add_argument("--file", help="从文件读")
    qp.add_argument("--original", type=float, help="原价,元")
    qp.add_argument("--floor", type=float, help="自定底价,元(留空按建议价 8 折)")
    qp.add_argument("--save", action="store_true")
    qp.set_defaults(func=cmd_quote)

    pp = sub.add_parser("platforms", help="平台费率")
    pp.set_defaults(func=cmd_platforms)

    bp = sub.add_parser("banned", help="违禁词清单")
    bp.set_defaults(func=cmd_banned)

    hp = sub.add_parser("history", help="历史估价")
    hp.add_argument("--limit", type=int, default=10)
    hp.set_defaults(func=cmd_history)

    wp = sub.add_parser("web", help="启动 Web 界面")
    wp.add_argument("--host", default="127.0.0.1")
    wp.add_argument("--port", type=int, default=8000)
    wp.add_argument("--mock", action="store_true", default=argparse.SUPPRESS)
    wp.set_defaults(func=cmd_web)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.mock and args.command == "quote" and not llm.config_from_args(args).get("api_key"):
        print(BANNER, file=sys.stderr)
    try:
        args.func(args)
    except LLMError as e:
        print("❌ %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
