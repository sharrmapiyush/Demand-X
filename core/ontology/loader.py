import json
import os
from typing import Dict, List, Any


def load_skills_seed(path: str = "core/ontology/skills_seed.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("skills", [])


def load_occupations_seed(path: str = "core/ontology/occupations_seed.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("occupations", [])


def load_trade_skill_mappings(path: str = "core/ontology/trade_skill_mapping.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


def load_trade_occupation_mappings(path: str = "core/ontology/trade_occupation_mapping.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mappings", [])


def normalize_skill_name(name: str) -> str:
    """Normalize skill name: lowercase, strip extra whitespace, remove common punctuation."""
    if not name:
        return ""
    return " ".join(name.lower().strip().split())


def get_skill_by_id(skill_id: str, skills: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    if skills is None:
        skills = load_skills_seed()
    for s in skills:
        if s.get("skill_id") == skill_id:
            return s
    return None


def get_occupation_by_id(occupation_id: str, occupations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    if occupations is None:
        occupations = load_occupations_seed()
    for o in occupations:
        if o.get("occupation_id") == occupation_id:
            return o
    return None


def validate_ontology() -> Dict[str, Any]:
    skills = load_skills_seed()
    mappings = load_trade_skill_mappings()

    skill_ids = set()
    errors = []

    # 1. Unique skill IDs check
    for s in skills:
        sid = s.get("skill_id")
        if not sid:
            errors.append("Skill missing skill_id")
        elif sid in skill_ids:
            errors.append(f"Duplicate skill_id found: {sid}")
        else:
            skill_ids.add(sid)

        # Ensure no skill is marked VERIFIED without explicit inspected evidence
        if s.get("verification_status") == "VERIFIED":
            errors.append(f"Skill {sid} marked VERIFIED without inspected document evidence")

    # 2. Duplicate mapping prevention check
    mapping_keys = set()
    for m in mappings:
        trade_name = m.get("canonical_trade_name")
        sid = m.get("skill_id")
        key = (trade_name, sid)
        if key in mapping_keys:
            errors.append(f"Duplicate mapping found for trade {trade_name} and skill {sid}")
        else:
            mapping_keys.add(key)

        # 3. Provenance presence check
        if not m.get("evidence_source"):
            errors.append(f"Mapping for {trade_name} missing evidence_source (provenance)")

        # 4. Valid mapping status check (must be NEEDS_REVIEW since external syllabus evidence is uninspected)
        status = m.get("mapping_status")
        if status != "NEEDS_REVIEW":
            errors.append(f"Mapping status must be NEEDS_REVIEW for unsupported mapping: {trade_name} -> {sid} (found {status})")

        # 5. Skill ID existence check
        if sid not in skill_ids:
            errors.append(f"Mapping references non-existent skill_id: {sid}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "skills_count": len(skills),
        "mappings_count": len(mappings)
    }


def validate_occupation_ontology() -> Dict[str, Any]:
    occupations = load_occupations_seed()
    mappings = load_trade_occupation_mappings()

    occupation_ids = set()
    errors = []

    # 1. Unique occupation IDs check & non-empty canonical name check & verification status check
    for o in occupations:
        oid = o.get("occupation_id")
        if not oid:
            errors.append("Occupation missing occupation_id")
        elif oid in occupation_ids:
            errors.append(f"Duplicate occupation_id found: {oid}")
        else:
            occupation_ids.add(oid)

        if not o.get("canonical_occupation_name"):
            errors.append(f"Occupation {oid} missing canonical_occupation_name")

        status = o.get("verification_status")
        if not status:
            errors.append(f"Occupation {oid} missing verification_status")
        elif status == "VERIFIED":
            errors.append(f"Occupation {oid} marked VERIFIED without inspected document evidence")

    # 2. Mapping validation checks
    mapping_keys = set()
    for m in mappings:
        trade_name = m.get("canonical_trade_name")
        oid = m.get("occupation_id")

        if not trade_name:
            errors.append("Mapping missing canonical_trade_name")
        if not oid:
            errors.append(f"Mapping for trade {trade_name} missing occupation_id")

        key = (trade_name, oid)
        if key in mapping_keys:
            errors.append(f"Duplicate mapping found for trade {trade_name} and occupation {oid}")
        else:
            mapping_keys.add(key)

        # Provenance check
        if not m.get("evidence_source"):
            errors.append(f"Mapping for {trade_name} missing evidence_source (provenance)")

        # Mapping status check
        m_status = m.get("mapping_status")
        if m_status != "NEEDS_REVIEW":
            errors.append(f"Mapping status must be NEEDS_REVIEW for trade {trade_name} -> occupation {oid} (found {m_status})")

        # Occupation existence check
        if oid not in occupation_ids:
            errors.append(f"Mapping references non-existent occupation_id: {oid}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "occupations_count": len(occupations),
        "mappings_count": len(mappings)
    }
