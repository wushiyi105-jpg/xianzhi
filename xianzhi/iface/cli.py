"""CLI：Typer + rich。"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..adapters.llm import LLMClient
from ..adapters.store import Store
from ..app.run import price_only, quote_and_save
from ..config import settings as base_settings
from ..domain.engine import allowed_numbers, load_market
from ..domain.guard import guard
from ..domain.models import Item

app = typer.Typer(add_completion=False, help="xianzhi —— 二手定价")
console = Console()


def _settings(db: Path | None):
    return base_settings.model_copy(update={"db_path": db}) if db else base_settings


@app.command("quote")
def quote_cmd(
    text: str = typer.Option(..., "--text", help="物品描述"),
    model: str = typer.Option("", help="型号，命中行情才用得准"),
    original: float = typer.Option(0.0, "--original", help="原价（元）"),
    years: float = typer.Option(None, "--years", help="已用年数"),
    as_json: bool = typer.Option(False, "--json"),
    db: Path = typer.Option(None),
) -> None:
    """给一个建议价、区间与到手价。"""
    item = Item(
        name=text,
        original_price_cents=int(original * 100),
        used_years=years,
        model=model,
    )
    market = load_market()
    q, _ = quote_and_save(Store(_settings(db).db_path), item, market, base_settings.deviation_threshold)

    if as_json:
        console.print_json(json.dumps({
            "anchor": q.anchor,
            "suggested": q.suggested_cents / 100,
            "range": [q.low_cents / 100, q.high_cents / 100],
            "floor": q.floor_cents / 100,
            "net": {k: v / 100 for k, v in q.net.items()},
            "notes": q.notes,
            "findings": [{"rule": f.rule_id, "message": f.message} for f in q.findings],
        }, ensure_ascii=False))
        return

    console.print(f"[bold]建议挂 {q.suggested_cents / 100:.0f} 元[/]  区间 {q.low_cents / 100:.0f}–{q.high_cents / 100:.0f}  底价 {q.floor_cents / 100:.0f}")
    table = Table(title="到手价")
    table.add_column("平台")
    table.add_column("到手", justify="right")
    for name, cents in q.net.items():
        table.add_row(name, f"{cents / 100:.0f}")
    console.print(table)
    for note in q.notes:
        console.print(f"[yellow]注意[/] {note}")
    for f in q.findings:
        console.print(f"  · [dim]{f.rule_id}[/] {f.message}")


@app.command()
def listing(
    text: str = typer.Option(..., "--text"),
    model: str = typer.Option(""),
    original: float = typer.Option(0.0, "--original"),
    years: float = typer.Option(None, "--years"),
) -> None:
    """生成挂卖文案（无 key 时只打印报价）。"""
    s = base_settings
    item = Item(name=text, original_price_cents=int(original * 100), used_years=years, model=model)
    q = price_only(item, load_market(), s.deviation_threshold)
    console.print(f"建议挂 {q.suggested_cents / 100:.0f} 元，区间 {q.low_cents / 100:.0f}–{q.high_cents / 100:.0f}")
    if not s.llm_enabled:
        console.print("[yellow]离线模式：未配置 API key，只输出报价[/]")
        return
    facts = json.dumps({
        "物品": text, "型号": model, "建议价": q.suggested_cents / 100,
        "区间": [q.low_cents / 100, q.high_cents / 100],
        "到手价": {k: v / 100 for k, v in q.net.items()},
    }, ensure_ascii=False)
    try:
        raw = LLMClient(s.llm_base_url, s.llm_api_key, s.llm_model).write(facts)
    except Exception as exc:  # noqa: BLE001 模型失败不挡住报价
        console.print(f"[yellow]离线模式：模型调用失败，只输出报价（{type(exc).__name__}）[/]")
        return
    if not raw:
        console.print("[yellow]离线模式：模型返回空，只输出报价[/]")
        return
    safe, dropped = guard(raw, allowed_numbers(q, item))
    console.print(safe or raw)
    if dropped:
        console.print(f"[yellow]已丢弃含未授权数字的句子：{', '.join(dropped)}[/]")


@app.command()
def history(limit: int = typer.Option(10), db: Path = typer.Option(None)) -> None:
    """最近的报价记录。"""
    rows = Store(_settings(db).db_path).recent(limit)
    table = Table(title="最近报价")
    for col in ("物品", "建议", "区间"):
        table.add_column(col)
    for r in rows:
        table.add_row(r.item[:24], f"{r.suggested_cents / 100:.0f}", f"{r.low_cents / 100:.0f}–{r.high_cents / 100:.0f}")
    console.print(table)


@app.command()
def migrate(db: Path = typer.Option(None), force: bool = typer.Option(False, "--force", help="即使已是最新也重跑")) -> None:
    """0.x 旧库迁到 1.0：先备份，失败保留原文件。"""
    from ..adapters.migrate import migrate as run_migrate

    path = _settings(db).db_path
    if not path.exists():
        console.print(f"[red]没有这个库：{path}[/]")
        raise typer.Exit(code=2)
    try:
        result = run_migrate(path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]迁移失败，原文件未改动[/] {exc}")
        raise typer.Exit(code=2) from exc
    if result["status"] == "current" and not force:
        console.print("[green]已是最新 schema[/]")
        return
    console.print(
        f"[green]{result['status']}[/] 转换 {result['rows']} 行，原库备份在 {result['backup'] or '（新建，无旧库）'}"
    )


@app.command()
def serve(port: int = typer.Option(0, help="0 表示用配置里的 8020"), db: Path = typer.Option(None)) -> None:
    """Web 界面。"""
    import uvicorn

    from .web import app_factory

    s = _settings(db)
    uvicorn.run(app_factory(s), host="127.0.0.1", port=port or s.port)


@app.command()
def doctor(db: Path = typer.Option(None)) -> None:
    """环境自检：配置 / 数据库 / 行情 / 模型 / webhook。"""
    from ..doctor import run_doctor

    bad = 0
    for name, ok, detail in run_doctor(_settings(db)):
        console.print(f"{'[green]ok[/]' if ok else '[red]fail[/]'}  {name:10} {detail}")
        bad += 0 if ok else 1
    raise typer.Exit(code=1 if bad else 0)


if __name__ == "__main__":  # pragma: no cover
    app()
