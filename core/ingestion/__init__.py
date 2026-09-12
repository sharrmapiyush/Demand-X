"""Raw Ingestion — connector interface + digest-dedup orchestration.

Adapted from reference project's sources/base.py and ingestion/orchestrator.py.

Not copied from reference:
- No fabricated observations; fetch_raw must return actual evidence.
- No hardcoded Windows paths / seed-data fallbacks.
- Orchestrator stages into Demand-X's existing JobStaging + provenance
  identity pipeline and delegates persistence to the existing
  BulkObservationIngestor — no duplicate parallel persistence layer.
"""

from core.ingestion.sources import SourceConnector, SourceRecordError
from core.ingestion.orchestrator import RawIngestionOrchestrator

__all__ = ["SourceConnector", "SourceRecordError", "RawIngestionOrchestrator"]