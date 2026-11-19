
import json
import unittest
from pathlib import Path

from validators import (
    slots_overlap,
    validate_recommendation,
)


BENCHMARK_DIR = Path(__file__).resolve().parent


class TestTimeOverlap(unittest.TestCase):

    def test_identical_intervals(self):
        self.assertTrue(
            slots_overlap("16:00-16:30", "16:00-16:30")
        )

    def test_partial_overlap(self):
        self.assertTrue(
            slots_overlap("16:00-16:30", "16:15-16:45")
        )

    def test_touching_boundaries(self):
        self.assertFalse(
            slots_overlap("16:00-16:30", "16:30-17:00")
        )

    def test_separate_intervals(self):
        self.assertFalse(
            slots_overlap("16:00-16:30", "17:00-17:30")
        )


class TestRecommendationValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        path = BENCHMARK_DIR / "case_06.json"

        with path.open("r", encoding="utf-8") as file:
            cls.case_data = json.load(file)

    def test_valid_judge(self):
        errors = validate_recommendation(
            self.case_data,
            {"judge_id": "J04"}
        )
        self.assertEqual(errors, [])

    def test_other_valid_judge(self):
        errors = validate_recommendation(
            self.case_data,
            {"judge_id": "J05"}
        )
        self.assertEqual(errors, [])

    def test_busy_judge(self):
        errors = validate_recommendation(
            self.case_data,
            {"judge_id": "J03"}
        )
        self.assertTrue(errors)

    def test_unknown_judge(self):
        errors = validate_recommendation(
            self.case_data,
            {"judge_id": "J99"}
        )
        self.assertTrue(errors)

    def test_missing_recommendation(self):
        errors = validate_recommendation(
            self.case_data,
            {"judge_id": None}
        )
        self.assertTrue(errors)


    def test_full_slot_rejects_new_judge(self):
        case = {
            "slot": {
                "time": "16:00-16:30",
                "required_judges": 2,
                "assigned_judges": ["J01", "J02"]
            },
            "candidates": [
                {
                    "id": "J03",
                    "available": True,
                    "busy_slots": []
                }
            ]
        }

        errors = validate_recommendation(
            case,
            {"judge_id": "J03"}
        )

        self.assertTrue(errors)

    def test_full_slot_accepts_no_assignment(self):
        case = {
            "slot": {
                "time": "16:00-16:30",
                "required_judges": 2,
                "assigned_judges": ["J01", "J02"]
            },
            "candidates": [
                {
                    "id": "J03",
                    "available": True,
                    "busy_slots": []
                }
            ]
        }

        errors = validate_recommendation(
            case,
            {"judge_id": None}
        )

        self.assertEqual(errors, [])



if __name__ == "__main__":
    unittest.main()
