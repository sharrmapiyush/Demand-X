"""Tests for API routers — app startup, router registration, and DB-backed endpoints.

Uses a file-based SQLite session via FastAPI dependency override so no live
Postgres connection is required. The /skills/demand endpoint is monkeypatched
because it calls calculate_skill_demand(db_url=...) directly, bypassing get_db.
"""
import sys
from unittest.mock import MagicMock

# Mock psycopg2 before any core.models/db.session import (DLL blocked on Py3.14).
for _mod in ('psycopg2', 'psycopg2._psycopg', 'psycopg2.extras', 'psycopg2.extensions'):
    sys.modules.setdefault(_mod, MagicMock())

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient


@pytest.fixture
def db_session(tmp_path):
    """File-based SQLite session with one registered Source row."""
    from core.models.base import Base
    from core.models.source import Source

    url = f"sqlite:///{tmp_path / 'api_test.db'}"
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON").close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Source(
        source_id="test-src", source_name="Test Source", organization="Test Org",
        url="https://example.com", category="demand", access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC", enabled=True,
    ))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient with get_db overridden to return the SQLite session."""
    from api.main import app
    from db.session import get_db

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Import and structure ─────────────────────────────────────────────────────

def test_fastapi_app_imports():
    from api.main import app
    assert app.title is not None
    assert app.version == "0.4.0"


def test_fastapi_router_count():
    """All 8 routers should be registered (≥8 distinct /api/v1 prefixes)."""
    from api.main import app
    prefixes = set()
    for r in app.routes:
        # FastAPI 0.115+ wraps each included router as an _IncludedRouter
        # whose .original_router carries the prefix.
        orig = getattr(r, "original_router", None)
        if orig is not None:
            p = getattr(orig, "prefix", None)
            if p and p.startswith("/api/v1"):
                prefixes.add(p)
    assert len(prefixes) >= 8


# ── Static / non-DB endpoints ────────────────────────────────────────────────

def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "endpoints" in data
    assert "/api/v1/health" in data.get("health", "")


def test_districts_list_endpoint(client):
    """36 official Maharashtra districts after Aurangabad/Sambhajinagar dedup."""
    resp = client.get("/api/v1/districts/")
    assert resp.status_code == 200
    data = resp.json()
    assert "districts" in data
    assert len(data["districts"]) == 36


# ── DB-backed endpoints (SQLite override) ─────────────────────────────────────

def test_health_endpoint(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"


def test_governance_policies_endpoint(client):
    resp = client.get("/api/v1/governance/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert "policies" in data
    assert data["count"] == 1
    assert data["policies"][0]["source_id"] == "test-src"


# ── Monkeypatched endpoint (uses db_url, not get_db) ─────────────────────────

def test_skills_demand_endpoint(client, monkeypatch):
    """Skill demand returns deterministic stub without hitting Postgres."""
    import core.analytics.skill_demand_engine as engine_mod

    def _stub_skill_demand(db_url, source_id, district=None, sector=None):
        return {
            "demand_rows": [],
            "total_jobs_evaluated": 0,
            "jobs_with_skill_evidence": 0,
            "skills_with_evidence": 0,
            "total_evidence_rows": 0,
            "source_id": source_id or "",
            "district": district,
            "sector": sector,
            "period_start": "2026-09-10",
            "period_end": "2026-09-10",
            "rule_version": "test-v0",
            "run_id": "test-run",
            "dvet_supply_summary": {},
        }

    monkeypatch.setattr(engine_mod, "calculate_skill_demand", _stub_skill_demand)
    resp = client.get("/api/v1/skills/demand")
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data
    assert "total_jobs_evaluated" in data
    assert data["total_jobs_evaluated"] == 0
