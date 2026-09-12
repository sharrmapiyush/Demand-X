"""Tests for Data Exports — CSV/JSON export of evidence-grounded analytics."""
import sys
from unittest.mock import MagicMock

# Mock psycopg2 to prevent DLL load failure when db.session is imported.
for _mod in ('psycopg2', 'psycopg2._psycopg', 'psycopg2.extras', 'psycopg2.extensions'):
    sys.modules.setdefault(_mod, MagicMock())

import datetime
import json
import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.observation import JobPosting
from core.models.source import Source


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'exports_test.db'}")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Source(
        source_id="test-src",
        source_name="Test Source",
        organization="Test Org",
        url="https://example.com",
        category="demand",
        access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC",
        enabled=True,
    ))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _add_job(session, *, source_id="test-src", title="Cosmetologist",
             skills="excel", description="Customer service",
             district="Pune", sector="Personal Care",
             retrieved_at=None):
    from uuid import uuid4
    import hashlib
    job_id = f"exp-{uuid4().hex[:12]}"
    job = JobPosting(
        id=job_id,
        source_id=source_id,
        job_title=title,
        source_skills=skills,
        description=description,
        employer_name="Test Employer",
        district=district,
        sector=sector,
        retrieved_at=retrieved_at or datetime.datetime(2026, 9, 10, 12, 0, 0),
        status="EXPIRED",
        record_identity_hash=hashlib.sha256(job_id.encode()).hexdigest(),
    )
    session.add(job)
    session.commit()
    return job


def _register_source(session, source_id):
    from core.models.source import Source
    session.add(Source(
        source_id=source_id,
        source_name=f"Source {source_id}",
        organization="Test Org",
        url="https://example.com",
        category="demand",
        access_method="PUBLIC_PAGE",
        freshness_class="PERIODIC",
        enabled=True,
    ))
    session.commit()


def test_export_skill_demand_empty(tmp_path, db):
    from core.exports.reporter import export_skill_demand
    path = export_skill_demand(db, output_dir=str(tmp_path / "exports"))
    assert os.path.exists(path)
    with open(path) as f:
        lines = f.readlines()
    # Header only — no jobs with extractable skills (title "Cosmetologist" may match, but let's check)
    assert lines[0].strip() != ""  # header exists


def test_export_skill_demand_with_jobs(tmp_path, db):
    from core.exports.reporter import export_skill_demand
    for _ in range(3):
        _add_job(db, skills="excel, word", title="Office Assistant")
    path = export_skill_demand(db, output_dir=str(tmp_path / "exports"))
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) > 1  # header + at least one row
    # Each row has 11 columns
    header = lines[0].strip().split(",")
    assert len(header) == 11


def test_export_skill_demand_source_filter(tmp_path, db):
    from core.exports.reporter import export_skill_demand
    _register_source(db, "src-a")
    _register_source(db, "src-b")
    _add_job(db, source_id="src-a", skills="excel")
    _add_job(db, source_id="src-b", skills="excel")
    path = export_skill_demand(db, output_dir=str(tmp_path / "exports"),
                               filename="filtered.csv", source_id="src-a")
    with open(path) as f:
        lines = f.readlines()
    # Header + rows; every row should have src-a
    assert len(lines) > 1
    for line in lines[1:]:
        assert "src-a" in line


def test_export_district_occupation_demand_empty(tmp_path, db):
    from core.exports.reporter import export_district_occupation_demand
    path = export_district_occupation_demand(db, output_dir=str(tmp_path / "exports"))
    assert os.path.exists(path)
    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1  # header only


def test_export_sources(tmp_path, db):
    from core.exports.reporter import export_sources
    path = export_sources(db, output_dir=str(tmp_path / "exports"))
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert len(data) >= 1
    assert data[0]["source_id"] == "test-src"
    assert "coverage" in data[0]


def test_export_occupations(tmp_path):
    """export_occupations copies the canonical occupations seed (a dict with
    an 'occupations' list, JSON), not a bare flat list."""
    from core.exports.reporter import export_occupations
    path = export_occupations(output_dir=str(tmp_path / "exports"))
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data["occupations"]) >= 7  # 7 canonical occupations


def test_export_skills(tmp_path):
    """export_skills copies the canonical skills seed (dict with 'skills')."""
    from core.exports.reporter import export_skills
    path = export_skills(output_dir=str(tmp_path / "exports"))
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data["skills"]) >= 32  # 32 canonical skills