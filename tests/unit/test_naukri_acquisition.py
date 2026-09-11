import unittest
import os
import json
from scripts.acquisition.validate_naukri import validate_naukri_historical_dataset

class TestNaukriAcquisition(unittest.TestCase):

    def test_source_metadata_exists_and_valid(self):
        metadata_path = "data/raw/naukri_historical/source_metadata.json"
        self.assertTrue(os.path.exists(metadata_path), "source_metadata.json must exist")

        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["source_id"], "naukri-historical-promptcloud")
        self.assertEqual(meta["source_type"], "SUPPLEMENTARY_HISTORICAL")
        self.assertFalse(meta["official_government_source"])
        self.assertEqual(meta["license_status"], "UNKNOWN")
        self.assertEqual(meta["freshness_class"], "HISTORICAL")

    def test_dataset_exists(self):
        csv_path = "data/raw/naukri_historical/naukri_com-job_sample.csv"
        self.assertTrue(os.path.exists(csv_path), "naukri_com-job_sample.csv must exist")

    def test_validation_script_metrics(self):
        results = validate_naukri_historical_dataset()
        self.assertTrue(results["file_exists"])
        self.assertEqual(results["row_count"], 22000)
        self.assertIn("jobtitle", results["columns"])
        self.assertIn("company", results["columns"])
        self.assertIn("joblocation_address", results["columns"])
        self.assertGreater(results["pune_record_count"], 0)
        self.assertGreater(results["distinct_companies"], 0)
        self.assertGreater(results["distinct_job_titles"], 0)

if __name__ == "__main__":
    unittest.main()
