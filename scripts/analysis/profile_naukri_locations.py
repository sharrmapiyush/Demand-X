import os
import json
import pandas as pd
from core.geography.location_normalizer import normalize_location

def profile_locations():
    csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    df = pd.read_csv(csv_path)
    total_records = len(df)

    has_location_col = "joblocation_address" in df.columns
    records_with_location = 0
    single_location_count = 0
    multi_location_count = 0
    unknown_count = 0

    pune_single_count = 0
    pune_multi_count = 0

    normalized_locations_list = []
    raw_locations_list = []
    pune_raw_examples = []

    for idx, row in df.iterrows():
        loc_text = str(row["joblocation_address"]) if has_location_col and pd.notnull(row["joblocation_address"]) else None
        if loc_text is not None and loc_text.strip():
            records_with_location += 1
            raw_locations_list.append(loc_text)

        res = normalize_location(loc_text)
        norm_str = f"District: {res.district} | Scope: {res.location_scope} | Matched: {res.matched_locations}"
        normalized_locations_list.append(norm_str)

        if res.location_scope == "SINGLE_LOCATION":
            single_location_count += 1
            if res.district == "Pune":
                pune_single_count += 1
        elif res.location_scope == "MULTI_LOCATION":
            multi_location_count += 1
            if res.district == "Pune":
                pune_multi_count += 1
                if len(pune_raw_examples) < 20:
                    pune_raw_examples.append(loc_text)
        else:
            unknown_count += 1
            if res.district == "Pune" or (loc_text and "pune" in loc_text.lower()):
                if len(pune_raw_examples) < 20:
                    pune_raw_examples.append(loc_text)

    # Top 50 normalized and raw locations
    raw_series = pd.Series(raw_locations_list)
    top_50_raw = raw_series.value_counts().head(50).to_dict() if not raw_series.empty else {}

    norm_series = pd.Series(normalized_locations_list)
    top_50_norm = norm_series.value_counts().head(50).to_dict() if not norm_series.empty else {}

    profile_data = {
        "total_records": total_records,
        "records_with_location": records_with_location,
        "single_location_count": single_location_count,
        "multi_location_count": multi_location_count,
        "unknown_count": unknown_count,
        "pune_single_location_count": pune_single_count,
        "pune_multi_location_count": pune_multi_count,
        "top_50_normalized_locations": top_50_norm,
        "top_50_raw_locations": top_50_raw,
        "pune_related_raw_examples": pune_raw_examples[:10]
    }

    output_path = "data/raw/naukri_historical/location_profile.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)

    print("Location profiling complete. Saved to data/raw/naukri_historical/location_profile.json")

    # Print required summary to stdout
    print(f"Total rows: {total_records}")
    print(f"Pune SINGLE_LOCATION count: {pune_single_count}")
    print(f"Pune MULTI_LOCATION count: {pune_multi_count}")
    print(f"UNKNOWN count: {unknown_count}")
    print("10 examples of problematic/ambiguous Pune location strings:")
    for ex in pune_raw_examples[:10]:
        print(f"  - {ex}")

if __name__ == "__main__":
    profile_locations()
