import os
import json
import pandas as pd
from typing import Dict, Any

def validate_naukri_historical_dataset(csv_path: str = "data/raw/naukri_historical/naukri_com-job_sample.csv") -> Dict[str, Any]:
    """
    Validates the downloaded Naukri historical dataset and computes required metrics:
    - row count
    - columns
    - null percentages per column
    - Pune-containing records count
    - distinct companies
    - distinct job titles
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    # Read CSV
    df = pd.read_csv(csv_path)

    row_count = len(df)
    columns = list(df.columns)

    # Null percentages
    null_counts = df.isnull().sum()
    null_percentages = {col: float((null_counts[col] / row_count) * 100) for col in columns}

    # Pune-containing records count (checking joblocation_address or any column)
    # Typically joblocation_address contains location strings like "Pune", "Mumbai, Pune", etc.
    pune_count = 0
    if "joblocation_address" in df.columns:
        pune_mask = df["joblocation_address"].fillna("").str.lower().str.contains("pune")
        pune_count = int(pune_mask.sum())

    # Distinct companies
    distinct_companies = 0
    if "company" in df.columns:
        distinct_companies = int(df["company"].nunique())

    # Distinct job titles
    distinct_job_titles = 0
    if "jobtitle" in df.columns:
        distinct_job_titles = int(df["jobtitle"].nunique())

    return {
        "file_exists": True,
        "row_count": row_count,
        "columns": columns,
        "null_percentages": null_percentages,
        "pune_record_count": pune_count,
        "distinct_companies": distinct_companies,
        "distinct_job_titles": distinct_job_titles
    }

if __name__ == "__main__":
    results = validate_naukri_historical_dataset()
    print(json.dumps(results, indent=2))
