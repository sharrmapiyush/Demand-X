"""AI service abstraction and evidence-grounded local fallback.

Adapted from reference project's ai/gemini_engine.py and ai/local_counselor.py.

Explicitly REJECTED from reference:
- Gemini engine impersonating "Government of Maharashtra" with fabricated salary
  charts — never done. The User-Agent and provider name are "Demand-X" throughout.
- Local counselor using seed_data.py hardcoded salaries, demand scores, and
  company names — never done. The local fallback queries REAL persisted
  observations only.
- Deterministic response builder using hardcoded data — never done. Responses
  are evidence-grounded and expose provenance.

Not copied:
- No external LLM API calls in MVP (deferred). This module provides:
  1. The AI provider interface (for future LLM integration).
  2. A local evidence-grounded fallback that queries actual DB records and
     returns structured evidence with provenance, freshness, and confidence.
"""

from ai.service.abstraction import (
    AIAbstraction,
    AIResponse,
    LocalEvidenceFallback,
)

__all__ = ["AIAbstraction", "AIResponse", "LocalEvidenceFallback"]