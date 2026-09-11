import unittest
from scripts.analysis.audit_identity_collisions import classify_collision_group


class TestIdentityCollisionClassification(unittest.TestCase):

    def _make_row(self, jobid, title, company, location, date, industry="", description="", skills="", positions=""):
        """Helper to create a mock row dict."""
        return {
            "jobid": jobid,
            "uniq_id": f"uniq_{jobid}",
            "jobtitle": title,
            "company": company,
            "joblocation_address": location,
            "postdate": date,
            "industry": industry,
            "jobdescription": description,
            "skills": skills,
            "numberofpositions": positions
        }

    def test_true_duplicate_identical_jobid(self):
        """Same jobid, all fields identical."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "TRUE_DUPLICATE")
        self.assertEqual(confidence, "HIGH")

    def test_true_duplicate_different_jobid(self):
        """All fields identical but different jobids."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J002", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "TRUE_DUPLICATE")
        self.assertEqual(confidence, "MEDIUM")

    def test_multi_location_same_jobid(self):
        """Same jobid, title, company, date; different locations."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J001", "Software Engineer", "TechCorp", "Mumbai", "2016-05-21 19:30:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "MULTI_LOCATION_POSTING")
        self.assertEqual(confidence, "HIGH")

    def test_multi_location_different_jobid(self):
        """Different jobids, same title, company, date; different locations."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J002", "Software Engineer", "TechCorp", "Mumbai", "2016-05-21 19:30:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "MULTI_LOCATION_POSTING")
        self.assertEqual(confidence, "MEDIUM")

    def test_reposting(self):
        """Same title, company, location; different dates."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J002", "Software Engineer", "TechCorp", "Pune", "2016-06-15 10:00:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "REPOSTING")
        self.assertEqual(confidence, "HIGH")

    def test_source_duplicate(self):
        """Different jobids, all other fields identical."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J002", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        # This should be TRUE_DUPLICATE since all fields match
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertIn(classification, ["TRUE_DUPLICATE", "SOURCE_DUPLICATE"])

    def test_uncertain_multiple_variations(self):
        """Multiple field variations."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        row2 = self._make_row("J002", "Data Analyst", "OtherCorp", "Mumbai", "2016-06-15 10:00:00 +0000")
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertEqual(classification, "UNCERTAIN")
        self.assertEqual(confidence, "LOW")

    def test_single_record(self):
        """Single record should not be a collision."""
        row1 = self._make_row("J001", "Software Engineer", "TechCorp", "Pune", "2016-05-21 19:30:00 +0000")
        classification, reason, confidence = classify_collision_group([row1])
        self.assertEqual(classification, "NONE")

    def test_empty_fields_handled(self):
        """Records with empty fields should not crash."""
        row1 = {"jobid": "J001", "jobtitle": "", "company": "", "joblocation_address": "", "postdate": ""}
        row2 = {"jobid": "J002", "jobtitle": "", "company": "", "joblocation_address": "", "postdate": ""}
        classification, reason, confidence = classify_collision_group([row1, row2])
        self.assertIn(classification, ["TRUE_DUPLICATE", "SOURCE_DUPLICATE", "UNCERTAIN"])


if __name__ == "__main__":
    unittest.main()
