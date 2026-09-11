import os
import csv
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Tuple

from ingestion.adapters.naukri_historical import load_naukri_historical, normalize_naukri_row


def normalize_text_for_comparison(text: Any) -> str:
    """Normalize text for comparison by lowercasing and removing extra whitespace."""
    if text is None or str(text).strip() == "":
        return ""
    return " ".join(str(text).lower().strip().split())


def classify_collision_group(rows: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """
    Classifies a collision group using deterministic rules.
    Returns (classification, reason, confidence).

    Classifications:
    - TRUE_DUPLICATE: Identical records
    - MULTI_LOCATION_POSTING: Same job, different locations
    - REPOSTING: Same job, different dates
    - SOURCE_DUPLICATE: Duplicates in source without distinguishing features
    - UNCERTAIN: Cannot determine safely
    """
    if len(rows) < 2:
        return "NONE", "Single record", "HIGH"

    # Extract fields for comparison
    jobids = set(str(r.get("jobid", "")).strip() for r in rows)
    uniq_ids = set(str(r.get("uniq_id", "")).strip() for r in rows)
    titles = set(normalize_text_for_comparison(r.get("jobtitle")) for r in rows)
    companies = set(normalize_text_for_comparison(r.get("company")) for r in rows)
    locations = set(normalize_text_for_comparison(r.get("joblocation_address")) for r in rows)
    postdates = set(str(r.get("postdate", "")).strip() for r in rows)
    industries = set(normalize_text_for_comparison(r.get("industry")) for r in rows)
    descriptions = set(normalize_text_for_comparison(r.get("jobdescription")) for r in rows)
    skills = set(normalize_text_for_comparison(r.get("skills")) for r in rows)
    positions = set(str(r.get("numberofpositions", "")).strip() for r in rows)

    # Remove empty strings from sets
    jobids.discard("")
    uniq_ids.discard("")
    titles.discard("")
    companies.discard("")
    locations.discard("")
    postdates.discard("")
    industries.discard("")
    descriptions.discard("")
    skills.discard("")
    positions.discard("")

    # TRUE_DUPLICATE: All fields identical
    all_fields_match = (
        len(titles) <= 1 and
        len(companies) <= 1 and
        len(locations) <= 1 and
        len(postdates) <= 1 and
        len(industries) <= 1 and
        len(descriptions) <= 1 and
        len(skills) <= 1 and
        len(positions) <= 1
    )

    if all_fields_match:
        # Check if jobids are the same
        if len(jobids) == 1:
            return "TRUE_DUPLICATE", "All fields identical including jobid", "HIGH"
        else:
            return "TRUE_DUPLICATE", "All fields identical, different jobids suggest source duplication", "MEDIUM"

    # MULTI_LOCATION_POSTING: Same job/company/date but different locations
    if len(locations) > 1 and len(titles) <= 1 and len(companies) <= 1 and len(postdates) <= 1:
        if len(jobids) == 1:
            return "MULTI_LOCATION_POSTING", "Same jobid, title, company, date; different locations", "HIGH"
        else:
            return "MULTI_LOCATION_POSTING", "Same title, company, date; different locations and jobids", "MEDIUM"

    # REPOSTING: Same job/company/location but different dates
    if len(postdates) > 1 and len(titles) <= 1 and len(companies) <= 1 and len(locations) <= 1:
        return "REPOSTING", "Same title, company, location; different posting dates", "HIGH"

    # SOURCE_DUPLICATE: Different jobids but everything else matches
    if len(jobids) > 1 and all_fields_match:
        return "SOURCE_DUPLICATE", "Different jobids, all other fields identical", "HIGH"

    # UNCERTAIN: Complex variation pattern
    variations = []
    if len(titles) > 1:
        variations.append(f"{len(titles)} titles")
    if len(companies) > 1:
        variations.append(f"{len(companies)} companies")
    if len(locations) > 1:
        variations.append(f"{len(locations)} locations")
    if len(postdates) > 1:
        variations.append(f"{len(postdates)} dates")

    reason = f"Multiple variations: {', '.join(variations)}"
    return "UNCERTAIN", reason, "LOW"


def audit_identity_collisions():
    """Audit all identity collisions in the Naukri historical dataset."""
    csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    print("Loading raw dataset...")
    raw_rows = load_naukri_historical(csv_path)
    total_input_rows = len(raw_rows)

    print("Computing identity hashes for all rows...")
    retrieved_at = datetime.utcnow()

    # Group rows by identity hash
    identity_to_rows = defaultdict(list)
    for row in raw_rows:
        obs, reasons, flags = normalize_naukri_row(row, retrieved_at)
        if obs:
            identity_to_rows[obs.record_identity_hash].append(row)

    # Find collision groups (identity hash with > 1 row)
    collision_groups = {
        identity: rows
        for identity, rows in identity_to_rows.items()
        if len(rows) > 1
    }

    print(f"Found {len(collision_groups)} collision groups...")

    # Classify each collision group
    classifications = {
        "TRUE_DUPLICATE": [],
        "MULTI_LOCATION_POSTING": [],
        "REPOSTING": [],
        "SOURCE_DUPLICATE": [],
        "UNCERTAIN": []
    }

    collision_details = []

    for identity_hash, rows in collision_groups.items():
        classification, reason, confidence = classify_collision_group(rows)
        classifications[classification].append(identity_hash)

        # Extract representative fields for CSV
        jobids = list(set(str(r.get("jobid", "")).strip() for r in rows if str(r.get("jobid", "")).strip()))
        uniq_ids = list(set(str(r.get("uniq_id", "")).strip() for r in rows if str(r.get("uniq_id", "")).strip()))
        job_titles = list(set(str(r.get("jobtitle", "")).strip() for r in rows if str(r.get("jobtitle", "")).strip()))
        companies = list(set(str(r.get("company", "")).strip() for r in rows if str(r.get("company", "")).strip()))
        locations = list(set(str(r.get("joblocation_address", "")).strip() for r in rows if str(r.get("joblocation_address", "")).strip()))
        post_dates = list(set(str(r.get("postdate", "")).strip() for r in rows if str(r.get("postdate", "")).strip()))

        collision_details.append({
            "identity": identity_hash[:16],  # Truncate for readability
            "collision_size": len(rows),
            "classification": classification,
            "jobids": " | ".join(jobids[:3]),  # Limit to first 3
            "uniq_ids": " | ".join(uniq_ids[:3]),
            "job_titles": " | ".join(job_titles[:2]),
            "companies": " | ".join(companies[:2]),
            "locations": " | ".join(locations[:2]),
            "post_dates": " | ".join(post_dates[:2]),
            "reason": reason,
            "confidence": confidence
        })

    # Calculate metrics
    duplicate_identity_rows = sum(len(rows) for rows in collision_groups.values())

    # Determine recommended persistence policy
    true_dup_count = len(classifications["TRUE_DUPLICATE"])
    multi_loc_count = len(classifications["MULTI_LOCATION_POSTING"])
    repost_count = len(classifications["REPOSTING"])
    source_dup_count = len(classifications["SOURCE_DUPLICATE"])
    uncertain_count = len(classifications["UNCERTAIN"])

    if true_dup_count + source_dup_count > 0 and (true_dup_count + source_dup_count) > (len(collision_groups) * 0.5):
        policy = "DEDUPLICATE_BEFORE_PERSISTENCE"
        policy_detail = "Majority are true or source duplicates. Recommend keeping only first occurrence per identity hash."
    elif repost_count > (len(collision_groups) * 0.5):
        policy = "PERSIST_ALL_FLAG_REPOSTINGS"
        policy_detail = ("Majority are repostings (same source jobid, distinct postdate via distinct uniq_id). "
                         "Each repost is a distinct hiring signal and should be persisted as its own observation, "
                         "flagged with its collision group id so demand aggregation can weight reposts separately.")
    elif uncertain_count > (len(collision_groups) * 0.5):
        policy = "PERSIST_ALL_WITH_COLLISION_FLAG"
        policy_detail = "Significant uncertainty. Persist all records with collision group metadata for manual review."
    else:
        policy = "PERSIST_ALL_WITH_CLASSIFICATION"
        policy_detail = "Mixed collision types. Persist all records with classification metadata."

    # Build audit report
    audit_report = {
        "audit_timestamp": datetime.utcnow().isoformat(),
        "total_input_rows": total_input_rows,
        "unique_identities": len(identity_to_rows),
        "duplicate_identity_groups": len(collision_groups),
        "duplicate_identity_rows": duplicate_identity_rows,
        "true_duplicate_groups": true_dup_count,
        "multi_location_groups": multi_loc_count,
        "reposting_groups": repost_count,
        "source_duplicate_groups": source_dup_count,
        "uncertain_groups": uncertain_count,
        "recommended_persistence_policy": policy,
        "policy_detail": policy_detail,
        "classification_distribution": {
            "TRUE_DUPLICATE": true_dup_count,
            "MULTI_LOCATION_POSTING": multi_loc_count,
            "REPOSTING": repost_count,
            "SOURCE_DUPLICATE": source_dup_count,
            "UNCERTAIN": uncertain_count
        },
        "representative_examples": {}
    }

    # Get representative examples for each classification
    for classification, identities in classifications.items():
        if identities:
            examples = []
            for identity_hash in identities[:5]:  # First 5 examples
                rows = collision_groups[identity_hash]
                example = {
                    "identity_hash": identity_hash[:16],
                    "collision_size": len(rows),
                    "jobids": [str(r.get("jobid", "")) for r in rows],
                    "uniq_ids": [str(r.get("uniq_id", "")) for r in rows],
                    "titles": list(set(str(r.get("jobtitle", "")).strip() for r in rows)),
                    "companies": list(set(str(r.get("company", "")).strip() for r in rows)),
                    "locations": list(set(str(r.get("joblocation_address", "")).strip() for r in rows)),
                    "dates": list(set(str(r.get("postdate", "")).strip() for r in rows))
                }
                examples.append(example)
            audit_report["representative_examples"][classification] = examples

    # Write JSON audit report
    json_path = "data/raw/naukri_historical/identity_collision_audit.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)
    print(f"Audit report saved to {json_path}")

    # Write CSV collision groups
    csv_output_path = "data/raw/naukri_historical/identity_collision_groups.csv"
    with open(csv_output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "identity", "collision_size", "classification", "jobids", "uniq_ids",
            "job_titles", "companies", "locations", "post_dates", "reason", "confidence"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(collision_details)
    print(f"Collision groups CSV saved to {csv_output_path}")

    # Print summary
    print("\n" + "="*80)
    print("IDENTITY COLLISION AUDIT SUMMARY")
    print("="*80)
    print(f"Total input rows: {total_input_rows}")
    print(f"Unique identities: {len(identity_to_rows)}")
    print(f"Collision groups: {len(collision_groups)}")
    print(f"Rows involved in collisions: {duplicate_identity_rows}")
    print()
    print("Classification Counts:")
    print(f"  TRUE_DUPLICATE: {true_dup_count}")
    print(f"  MULTI_LOCATION_POSTING: {multi_loc_count}")
    print(f"  REPOSTING: {repost_count}")
    print(f"  SOURCE_DUPLICATE: {source_dup_count}")
    print(f"  UNCERTAIN: {uncertain_count}")
    print()
    print("Recommended Persistence Policy:")
    print(f"  {policy}")
    print(f"  {policy_detail}")
    print("="*80)

    return audit_report


if __name__ == "__main__":
    audit_identity_collisions()
