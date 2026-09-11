import os
import json
from ingestion.adapters.naukri_historical import adapt_naukri_dataset

def run_smoke_test():
    csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"
    if not os.path.exists(csv_path):
        print(f"Dataset not found at {csv_path}")
        return

    print("Adapting full Naukri historical dataset (22,000 rows)...")
    observations, profile = adapt_naukri_dataset(csv_path)

    output_path = "data/raw/naukri_historical/adapter_profile.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    print("Adapter execution complete.")
    print(json.dumps(profile, indent=2))

if __name__ == "__main__":
    run_smoke_test()
