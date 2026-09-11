import pytest
from sqlalchemy import text
from db.session import engine, SessionLocal
from core.models.source import Source


def test_database_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            assert result.scalar() == 1
    except Exception as e:
        pytest.skip(f"PostgreSQL database not reachable for integration test: {e}")


def test_source_model_instantiation():
    source = Source(
        source_id="test-source-001",
        source_name="National Career Service Test",
        organization="Ministry of Labour and Employment",
        url="https://www.ncs.gov.in/",
        category="Demand",
        access_method="SOURCE_SNAPSHOT",
        freshness_class="PERIODIC",
        enabled=True
    )
    assert source.source_id == "test-source-001"
    assert source.access_method == "SOURCE_SNAPSHOT"
    assert source.freshness_class == "PERIODIC"
    assert source.enabled is True
