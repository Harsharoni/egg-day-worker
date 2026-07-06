from fastapi import APIRouter, HTTPException, Request

from web import service

router = APIRouter()


def _render(request: Request, name: str, ctx: dict):
    from web.app import render
    return render(request, name, ctx)


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/")
def home(request: Request):
    bundle = service.get_bundle()
    return _render(request, "home.html", {
        "phase": bundle["phase"],
        "guilds": bundle["guilds"].to_dict("records"),
        "scores": bundle["scores"].to_dict("records"),
        "last_updated": bundle["last_updated"],
    })


@router.get("/player/{discord_id}")
def player(request: Request, discord_id: int, ei: str | None = None):
    row, accounts = service.get_player(discord_id, ei)
    if row is None:
        if not accounts:
            raise HTTPException(404, "player not on the leaderboard")
        if ei is not None:
            raise HTTPException(404, "no account with that name")
        # multiple alts, none selected — picker
        return _render(request, "player.html", {
            "row": None,
            "accounts": accounts,
            "discord_id": discord_id,
            "series": None,
            "phase": service.get_bundle()["phase"],
        })
    series = service.get_player_series(discord_id, row["ei_name"])
    return _render(request, "player.html", {
        "row": row,
        "accounts": accounts,
        "discord_id": discord_id,
        "series": series,
        "phase": service.get_bundle()["phase"],
    })


@router.get("/guild/{gkey:path}")
def guild(request: Request, gkey: str):
    info, members = service.get_guild(gkey)
    if info is None:
        raise HTTPException(404, "guild not found")
    return _render(request, "guild.html", {
        "info": info,
        "members": members.to_dict("records"),
        "series": service.get_guild_series(gkey),
        "phase": service.get_bundle()["phase"],
    })
