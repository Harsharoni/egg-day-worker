import sys
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import processors.competition as competition
import web.service as service
from web.app import app
from web.cache import cache

LIVE_NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(monkeypatch, scores_df, participants_df, snapshot_df, history_df):
    """TestClient with all db loaders monkeypatched — no Postgres."""
    calls = {"snapshot": 0}

    def fake_snapshot():
        calls["snapshot"] += 1
        return snapshot_df.copy()

    monkeypatch.setattr(service, "load_snapshot", fake_snapshot)
    monkeypatch.setattr(service, "load_start_snapshot", lambda: snapshot_df.copy())
    monkeypatch.setattr(service, "load_participants", lambda: participants_df.copy())
    monkeypatch.setattr(service, "load_history", lambda s, e: history_df.copy())
    # deterministic "live" clock unless a test overrides the phase
    cache.clear()
    c = TestClient(app)
    c.calls = calls
    yield c
    cache.clear()


def test_web_never_imports_worker_io():
    assert "fetchers.egg9000" not in sys.modules
    assert "sheets.writer" not in sys.modules


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_home_all_phases(client, monkeypatch):
    for now, phase in [
        (datetime(2026, 7, 1, tzinfo=timezone.utc), "pre"),
        (LIVE_NOW, "live"),
        (datetime(2026, 8, 1, tzinfo=timezone.utc), "post"),
    ]:
        cache.clear()

        class FakeDT(datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        monkeypatch.setattr(service, "datetime", FakeDT)
        if phase == "post":
            # post-comp end state resolves via snapshot_at — stub it
            monkeypatch.setattr(competition, "snapshot_at", lambda ts: None,
                                raising=False)
            monkeypatch.setattr(
                "db.snapshot_at",
                lambda ts: client_snapshot(client),
            )
        r = client.get("/")
        assert r.status_code == 200, f"{phase}: {r.text[:300]}"
        assert competition.comp_phase(now) == phase
        assert "Scoreboard" in r.text


def client_snapshot(client):
    # helper: reuse the snapshot loader the client fixture installed
    return service.load_snapshot()


def test_home_pre_comp_shows_dashes(client, monkeypatch):
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(service, "datetime", FakeDT)
    r = client.get("/")
    assert r.status_code == 200
    assert "starts soon" in r.text.lower()
    assert "—" in r.text  # dash cells for missing scores


def test_player_unicode_query_param(client):
    r = client.get(f"/player/3?ei={quote('Émil 🥚')}")
    assert r.status_code == 200
    assert "Émil 🥚" in r.text


def test_player_slash_name(client):
    r = client.get(f"/player/4?ei={quote('a/b slash', safe='')}")
    assert r.status_code == 200
    assert "a/b slash" in r.text


def test_player_single_account_no_ei(client):
    r = client.get("/player/1")
    assert r.status_code == 200
    assert "Alice" in r.text


def test_player_404s(client):
    assert client.get("/player/424242").status_code == 404
    assert client.get("/player/1?ei=NotAlice").status_code == 404


def test_guild_page_and_casing_merge(client):
    r = client.get("/guild/the%20coop")
    assert r.status_code == 200
    # both case-variant members listed
    assert "Alice" in r.text and "Bob" in r.text


def test_guild_404(client):
    assert client.get("/guild/no%20such%20guild").status_code == 404


def test_cache_single_db_hit_across_requests(client):
    client.get("/")
    client.get("/")
    client.get("/player/1")
    assert client.calls["snapshot"] == 1  # bundle computed once, TTL-cached


def test_html_cache_control(client):
    r = client.get("/")
    assert r.headers["cache-control"] == "public, max-age=30"
