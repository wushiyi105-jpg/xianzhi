"""FastAPI + Jinja2。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..adapters.store import Store
from ..app.run import quote_and_save
from ..config import Settings
from ..domain.engine import load_market
from ..domain.models import Item

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="xianzhi", version="1.0.0")
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "static")),
        name="static",
    )
    store = Store(settings.db_path)
    market = load_market()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": None})

    @app.post("/quote", response_class=HTMLResponse)
    def do_quote(
        request: Request,
        text: str = Form(""),
        model: str = Form(""),
        original: float = Form(0.0),
        years: str = Form(""),
    ) -> HTMLResponse:
        item = Item(
            name=text,
            original_price_cents=int(original * 100),
            used_years=float(years) if years.strip() else None,
            model=model.strip(),
        )
        q, _ = quote_and_save(store, item, market, settings.deviation_threshold)
        result = {
            "suggested": f"{q.suggested_cents / 100:.0f}",
            "low": f"{q.low_cents / 100:.0f}",
            "high": f"{q.high_cents / 100:.0f}",
            "floor": f"{q.floor_cents / 100:.0f}",
            "anchor": q.anchor,
            "net": [(k, f"{v / 100:.0f}") for k, v in q.net.items()],
            "notes": q.notes,
            "findings": [(f.rule_id, f.message) for f in q.findings],
        }
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": result})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def app_factory(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        from ..config import settings as default_settings

        settings = default_settings
    return create_app(settings)

