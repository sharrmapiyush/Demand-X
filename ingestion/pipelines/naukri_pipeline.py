"""Naukri historical dataset pipeline — source registration and ingestion orchestration.

The dataset is the PromptCloudHQ scrape of Naukri.com job postings (hosted on
HuggingFace, see `NAUKRI_HISTORICAL_SOURCE_URL`). It is a supplementary,
non-official, historical observation source. This module registers the source
in the canonical Source Registry and exposes the observation ingestion entry
point. Registration is idempotent: running it twice never creates a duplicate
source row.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.models.source import Source

NAUKRI_HISTORICAL_SOURCE_ID = "naukri-historical-promptcloud"
NAUKRI_HISTORICAL_SOURCE_NAME = "PromptCloudHQ Jobs on Naukri.com"
NAUKRI_HISTORICAL_SOURCE_URL = (
    "https://huggingface.co/datasets/jason1966/PromptCloudHQ_jobs-on-naukricom"
)


def register_naukri_historical_source(db: Session) -> Source:
    """Ensure the Naukri historical source is registered (idempotent).

    Follows the same convention as ``register_dvet_source`` and
    ``register_unverified_ncs_fixture_source``: query for the existing row
    first; only insert when absent. Safe to call repeatedly.
    """
    source = (
        db.query(Source)
        .filter(Source.source_id == NAUKRI_HISTORICAL_SOURCE_ID)
        .first()
    )
    if source is not None:
        return source

    source = Source(
        source_id=NAUKRI_HISTORICAL_SOURCE_ID,
        source_name=NAUKRI_HISTORICAL_SOURCE_NAME,
        organization="PromptCloudHQ (dataset hosted on HuggingFace by jason1966)",
        url=NAUKRI_HISTORICAL_SOURCE_URL,
        category="demand",
        access_method="SOURCE_SNAPSHOT",  # static scrape snapshot; NOT a verified API/export
        freshness_class="HISTORICAL",
        source_type="SUPPLEMENTARY_HISTORICAL",
        official_government_source=False,
        verification_status="UNVERIFIED_EXTERNAL_DATASET",
        last_verified_at=None,
        last_fetched_at=None,
        coverage="Naukri.com job postings (historical scrape, ~22k records, 2016)",
        historical_depth="Historical scrape snapshot (approximately 2016 era postings)",
        reliability_notes=(
            "UNVERIFIED_EXTERNAL_DATASET. Third-party scrape of Naukri.com hosted on "
            "HuggingFace. No verified license or provenance chain has been confirmed; "
            "observation status is derived by explicit historical-data rule (EXPIRED)."
        ),
        legal_access_notes=(
            "Posted on HuggingFace as a public dataset (jason1966/PromptCloudHQ_jobs-on-naukricom). "
            "License status is unverified; treat as external, non-official data."
        ),
        enabled=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source