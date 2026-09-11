import pytest
from decimal import Decimal
from ingestion.pipelines.ncs_pipeline import (
    parse_experience,
    parse_salary,
    calculate_job_hash
)


def test_parse_experience():
    assert parse_experience("2-4 years") == (2, 4)
    assert parse_experience("3-6 years experience") == (3, 6)
    assert parse_experience("5 years") == (5, 5)
    assert parse_experience(None) == (None, None)
    assert parse_experience("Freshers") == (None, None)


def test_parse_salary():
    assert parse_salary("₹6,00,000 - ₹9,00,000 PA") == (Decimal("600000"), Decimal("900000"))
    assert parse_salary("₹4,50,000 PA") == (Decimal("450000"), Decimal("450000"))
    assert parse_salary(None) == (None, None)
    assert parse_salary("Not disclosed") == (None, None)


def test_calculate_job_hash():
    h1 = calculate_job_hash("ncs-pune", "REC-001", "Python Developer", "Tech Mahindra")
    h2 = calculate_job_hash("ncs-pune", "REC-001", "Python Developer", "Tech Mahindra")
    h3 = calculate_job_hash("ncs-pune", "REC-002", "Python Developer", "Tech Mahindra")

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64
