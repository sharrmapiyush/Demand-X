import unittest
from datetime import datetime, date
from ingestion.adapters.naukri_historical import (
    normalize_naukri_row,
    parse_date,
    parse_seats,
    adapt_naukri_dataset
)
from ingestion.contracts.observations import NormalizedJobPostingObservation

class TestNaukriHistoricalAdapter(unittest.TestCase):

    def setUp(self):
        self.retrieved_at = datetime.utcnow()

    def test_normal_valid_row(self):
        row = {
            "jobtitle": "Software Engineer",
            "company": "Tech Corp",
            "joblocation_address": "Pune",
            "industry": "IT-Software",
            "jobdescription": "Develop software",
            "postdate": "2016-05-21 19:30:00 +0000",
            "jobid": "123456",
            "uniq_id": "abc123uniq",
            "numberofpositions": "5"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertEqual(len(reasons), 0)
        self.assertEqual(obs.job_title, "Software Engineer")
        self.assertEqual(obs.employer_name, "Tech Corp")
        self.assertEqual(obs.district, "Pune")
        self.assertEqual(obs.source_record_id, "123456")
        self.assertEqual(obs.status, "ACTIVE")
        self.assertIsNotNone(obs.record_identity_hash)

    def test_missing_optional_fields(self):
        row = {
            "jobtitle": "Python Developer",
            "company": "",
            "joblocation_address": "",
            "industry": "",
            "jobdescription": "",
            "postdate": "2016-05-21",
            "jobid": "999",
            "numberofpositions": ""
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.employer_name, None)
        self.assertEqual(obs.location_text, None)
        self.assertTrue(flags["missing_company"])
        self.assertTrue(flags["missing_location"])

    def test_missing_title(self):
        row = {
            "jobtitle": "",
            "company": "Tech Corp",
            "joblocation_address": "Pune",
            "postdate": "2016-05-21",
            "jobid": "111"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNone(obs)
        self.assertTrue(flags["missing_title"])
        self.assertIn("Missing job title", reasons)

    def test_malformed_postdate(self):
        row = {
            "jobtitle": "Developer",
            "company": "Tech",
            "joblocation_address": "Mumbai",
            "postdate": "invalid-date-string",
            "jobid": "222"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNone(obs)
        self.assertTrue(flags["malformed_date"])
        self.assertTrue(any("Malformed postdate" in r for r in reasons))

    def test_malformed_numberofpositions(self):
        row = {
            "jobtitle": "Developer",
            "company": "Tech",
            "joblocation_address": "Mumbai",
            "postdate": "2016-05-21",
            "numberofpositions": "not-a-number",
            "jobid": "333"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNone(obs)
        self.assertTrue(flags["malformed_seats"])
        self.assertTrue(any("Malformed numberofpositions" in r for r in reasons))

    def test_pune_single_location(self):
        row = {
            "jobtitle": "Data Analyst",
            "company": "Pune Analytics",
            "joblocation_address": "Pune",
            "postdate": "2016-05-21",
            "jobid": "444"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.district, "Pune")
        self.assertEqual(obs.state, "Maharashtra")

    def test_pune_multi_location(self):
        row = {
            "jobtitle": "Consultant",
            "company": "Global",
            "joblocation_address": "Mumbai , Pune",
            "postdate": "2016-05-21",
            "jobid": "555"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.district, "Pune")

    def test_missing_location(self):
        row = {
            "jobtitle": "Remote Dev",
            "company": "Remote Inc",
            "joblocation_address": None,
            "postdate": "2016-05-21",
            "jobid": "666"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertTrue(flags["missing_location"])
        self.assertIsNone(obs.location_text)
        self.assertIsNone(obs.district)

    def test_provenance_fields(self):
        row = {
            "jobtitle": "Engineer",
            "company": "Corp",
            "joblocation_address": "Delhi",
            "postdate": "2016-05-21",
            "jobid": "777"
        }
        obs, reasons, flags = normalize_naukri_row(row, self.retrieved_at)
        self.assertIsNotNone(obs)
        self.assertEqual(obs.source_id, "naukri-historical-promptcloud")
        self.assertEqual(obs.retrieved_at, self.retrieved_at)

    def test_deterministic_identity_behavior(self):
        row1 = {
            "jobtitle": "Engineer",
            "company": "Corp",
            "joblocation_address": "Delhi",
            "postdate": "2016-05-21",
            "jobid": "888"
        }
        row2 = {
            "jobtitle": "Engineer",
            "company": "Corp",
            "joblocation_address": "Delhi",
            "postdate": "2016-05-21",
            "jobid": "888"
        }
        obs1, _, _ = normalize_naukri_row(row1, self.retrieved_at)
        obs2, _, _ = normalize_naukri_row(row2, self.retrieved_at)
        self.assertEqual(obs1.record_identity_hash, obs2.record_identity_hash)

if __name__ == "__main__":
    unittest.main()
