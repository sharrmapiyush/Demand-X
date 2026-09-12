"""Tests for Skill Velocity — honest INSUFFICIENT_DATA for single snapshot."""
import sys
from unittest.mock import MagicMock

# Mock psycopg2 to prevent DLL load failure when db.session is imported.
# (psycopg2 DLL blocked by Windows application control policy on Python 3.14)
for _mod in ('psycopg2', 'psycopg2._psycopg', 'psycopg2.extras', 'psycopg2.extensions'):
    sys.modules.setdefault(_mod, MagicMock())

import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.base import Base
from core.models.source import Source
from core.models.observation import JobPosting


@pytest.fixture
def tmp_db(tmp_path):
    """File-based SQLite DB that survives separate engine connections
    (compute_skill_velocity builds its own engine from a db_url string)."""
    url = f"sqlite:///{tmp_path / 'velocity.db'}"
    engine = create_engine(url)
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
    session.close()
    engine.dispose()
    return url


def _add_jobs(url, rows):
    import hashlib
    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    for r in rows:
        rid = r["id"]
        session.add(JobPosting(
            id=rid,
            source_id=r.get("source_id", "test-src"),
            job_title=r["title"],
            source_skills=r.get("skills"),
            description=r.get("description", ""),
            employer_name=r.get("employer", "Test Employer"),
            district=r.get("district"),
            sector=r.get("sector"),
            retrieved_at=r.get("retrieved_at", datetime.datetime(2026, 9, 10, 12, 0, 0)),
            status="EXPIRED",
            # record_identity_hash is NOT NULL on JobPosting; derive a unique
            # deterministic hash per test row.
            record_identity_hash=hashlib.sha256(rid.encode()).hexdigest(),
        ))
    session.commit()
    session.close()
    engine.dispose()


def test_velocity_single_snapshot_insufficient(tmp_db):
    """Two windows with 0 jobs → NO_DATA, empty skill list, honest labels."""
    from core.analytics.skill_velocity import compute_skill_velocity
    result = compute_skill_velocity(
        db_url=tmp_db,
        source_id="test-src",
        window_start=datetime.date(2026, 9, 10),
        window_end=datetime.date(2026, 9, 10),
        previous_start=datetime.date(2026, 9, 1),
        previous_end=datetime.date(2026, 9, 10),
    )
    assert result["freshness"] == "NO_DATA"
    assert result["total_window_jobs"] == 0
    assert result["total_previous_jobs"] == 0
    assert result["skills"] == []


def test_velocity_real_windows_below_threshold(tmp_db):
    """Jobs exist but < MIN_WINDOW_JOBS in at least one window → INSUFFICIENT_DATA."""
    from core.analytics.skill_velocity import compute_skill_velocity
    _add_jobs(tmp_db, [
        {"id": "j1", "title": "Cosmetologist", "skills": "excel", "district": "Pune",
         "retrieved_at": datetime.datetime(2026, 9, 10, 12)},
        {"id": "j2", "title": "Beautician", "skills": "ms office", "district": "Pune",
         "retrieved_at": datetime.datetime(2026, 9, 10, 12)},
    ])
    result = compute_skill_velocity(
        db_url=tmp_db,
        source_id="test-src",
        window_start=datetime.date(2026, 9, 10),
        window_end=datetime.date(2026, 9, 10),
        previous_start=datetime.date(2026, 8, 1),
        previous_end=datetime.date(2026, 8, 31),
    )
    # 2 jobs in window (below min 3), 0 in previous → freshness NEW_WINDOW
    assert result["freshness"] == "NEW_WINDOW"
    for row in result["skills"]:
        assert row["velocity"] == "INSUFFICIENT_DATA"


def test_velocity_constants():
    from core.analytics.skill_velocity import (
        MIN_WINDOW_JOBS, RISING_THRESHOLD, FALLING_THRESHOLD, MIN_WINDOWS,
        VELOCITY_LABELS,
    )
    assert MIN_WINDOW_JOBS >= 3
    assert RISING_THRESHOLD >= 0.25
    assert FALLING_THRESHOLD >= 0.20
    assert MIN_WINDOWS == 2
    assert "INSUFFICIENT_DATA" in VELOCITY_LABELS


def test_velocity_thresholds_explicit():
    """All thresholds are transparent — no hidden knobs."""
    from core.analytics.skill_velocity import MIN_WINDOW_JOBS, RISING_THRESHOLD, FALLING_THRESHOLD
    assert isinstance(MIN_WINDOW_JOBS, int)
    assert isinstance(RISING_THRESHOLD, float)
    assert isinstance(FALLING_THRESHOLD, float)


def test_velocity_return_structure(tmp_db):
    from core.analytics.skill_velocity import compute_skill_velocity
    result = compute_skill_velocity(
        db_url=tmp_db,
        source_id="test-src",
        window_start=datetime.date(2026, 1, 1),
        window_end=datetime.date(2026, 6, 30),
        previous_start=datetime.date(2025, 1, 1),
        previous_end=datetime.date(2025, 6, 30),
    )
    assert "rule_version" in result
    assert "freshness" in result
    assert "thresholds" in result
    assert "skills" in result
    assert "labels" in result
    assert isinstance(result["skills"], list)
    assert result["thresholds"]["min_window_jobs"] >= 3


def test_velocity_never_calls_rising_without_minimum(tmp_db):
    """Guards: RISING/FALLING labels must require >= min jobs in BOTH windows."""
    from core.analytics.skill_velocity import compute_skill_velocity, MIN_WINDOW_JOBS
    n = MIN_WINDOW_JOBS
    # Previous window has fewer than MIN job per skill → can never be RISING/FALLING
    _add_jobs(tmp_db, [
        {"id": f"w{i}", "title": "Cosmetologist", "skills": "excel", "district": "Pune",
         "retrieved_at": datetime.datetime(2026, 9, 10, 12)} for i in range(n)
    ] + [
        {"id": f"p{i}", "title": "Cosmetologist", "skills": "excel", "district": "Pune",
         "retrieved_at": datetime.datetime(2026, 8, 1, 12)} for i in range(n - 1)
    ])
    result = compute_skill_velocity(
        db_url=tmp_db,
        source_id="test-src",
        window_start=datetime.date(2026, 9, 10),
        window_end=datetime.date(2026, 9, 10),
        previous_start=datetime.date(2026, 8, 1),
        previous_end=datetime.date(2026, 8, 31),
    )
    # At least one skill present in previous window below threshold → guarded
    for row in result["skills"]:
        if row["previous_distinct_jobs"] < MIN_WINDOW_JOBS:
            assert row["velocity"] == "INSUFFICIENT_DATA"