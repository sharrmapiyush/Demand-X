import unittest
from core.geography.location_normalizer import normalize_location

class TestLocationNormalizer(unittest.TestCase):

    def test_single_pune(self):
        res = normalize_location("Pune")
        self.assertEqual(res.location_evidence_level, "EXACT_SINGLE")
        self.assertEqual(res.pune_exclusivity, "EXCLUSIVE")
        self.assertTrue(res.has_pune_evidence)

    def test_pune_maharashtra(self):
        res = normalize_location("Pune, Maharashtra")
        self.assertEqual(res.location_evidence_level, "EXACT_SINGLE")
        self.assertEqual(res.pune_exclusivity, "EXCLUSIVE")
        self.assertTrue(res.has_pune_evidence)

    def test_pimpri_chinchwad(self):
        res = normalize_location("Pimpri-Chinchwad")
        self.assertEqual(res.location_evidence_level, "EXACT_SINGLE")
        self.assertEqual(res.pune_exclusivity, "EXCLUSIVE")
        self.assertTrue(res.has_pune_evidence)

    def test_pune_mumbai_slash(self):
        res = normalize_location("Pune / Mumbai")
        self.assertEqual(res.location_evidence_level, "MULTI_EXPLICIT")
        self.assertEqual(res.pune_exclusivity, "SHARED")
        self.assertTrue(res.has_pune_evidence)

    def test_multi_location_many_cities(self):
        loc = "Bengaluru/Bangalore , Mumbai , Chennai , Pune , Hyderabad / Secunderabad , Delhi/NCR(National Capital Region)"
        res = normalize_location(loc)
        self.assertEqual(res.location_evidence_level, "MULTI_EXPLICIT")
        self.assertEqual(res.pune_exclusivity, "SHARED")
        self.assertTrue(res.has_pune_evidence)

    def test_city_mention_irregular(self):
        # Irregular: "PUNE Mumbai, Chennai Kolkata, Bangalore Hyderabad"
        # Has spaces and mixed delimiters
        loc = "PUNE Mumbai, Chennai Kolkata, Bangalore Hyderabad"
        res = normalize_location(loc)
        self.assertEqual(res.location_evidence_level, "CITY_MENTION")
        self.assertEqual(res.pune_exclusivity, "MENTIONED")
        self.assertTrue(res.has_pune_evidence)

    def test_empty_location(self):
        res = normalize_location("")
        self.assertEqual(res.location_evidence_level, "UNKNOWN")
        self.assertEqual(res.pune_exclusivity, "UNKNOWN")
        self.assertFalse(res.has_pune_evidence)

    def test_unknown_location(self):
        res = normalize_location("Atlantis")
        self.assertEqual(res.location_evidence_level, "UNKNOWN")
        self.assertEqual(res.pune_exclusivity, "UNKNOWN")
        self.assertFalse(res.has_pune_evidence)

if __name__ == "__main__":
    unittest.main()
