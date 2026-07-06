from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import SITE_TITLE, COMP_START_UTC, COMP_END_UTC
from processors.guilds import guild_key
from web import filters

_BASE = Path(__file__).parent

templates = Jinja2Templates(directory=str(_BASE / "templates"))
templates.env.filters["mag"] = filters.fmt_mag
templates.env.filters["int_"] = filters.fmt_int
templates.env.filters["pct"] = filters.fmt_pct
templates.env.filters["float_"] = filters.fmt_float
templates.env.filters["guild_key"] = guild_key
templates.env.globals["SITE_TITLE"] = SITE_TITLE
templates.env.globals["START_EPOCH"] = int(COMP_START_UTC.timestamp())
templates.env.globals["END_EPOCH"] = int(COMP_END_UTC.timestamp())

app = FastAPI(title=SITE_TITLE, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


def render(request: Request, name: str, ctx: dict, status_code: int = 200) -> HTMLResponse:
    resp = templates.TemplateResponse(
        request=request, name=name, context=ctx, status_code=status_code
    )
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return render(request, "404.html", {"detail": exc.detail}, status_code=404)
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail}</p>",
                        status_code=exc.status_code)


from web.routes import router  # noqa: E402  (needs templates/render above)

app.include_router(router)
