import unittest
from datetime import datetime, timezone

from assignment.benchmark.validators import validate_recommendation
from assignment.solver import assign_judges, h07_payload
from registration.domain.availability import SlotAvailability


def slot(slot_id, start, end, required, judges):
    day = datetime(2026, 11, 21, tzinfo=timezone.utc)
    return SlotAvailability(
        slot_id, day.replace(hour=start // 60, minute=start % 60),
        day.replace(hour=end // 60, minute=end % 60),
        required, len(judges), judges, len(judges) < required,
    )


class ReserveAssignmentTests(unittest.TestCase):
    def test_one_reserve_is_enough_and_zero_reserves_exports_a_case(self):
        rows = [slot("S1", 840, 870, 1, ["main"])]
        main_only = assign_judges(rows, {})
        case = h07_payload("demo", rows, main_only, {})

        self.assertEqual(case["slot"]["required_judges"], 1)
        self.assertEqual(case["slot"]["assigned_judges"], [])
        self.assertEqual(case["problem"], "Нет резервного судьи")
        self.assertEqual(case["candidates"], [])
        self.assertEqual(validate_recommendation(case, {"judge_id": None}), [])

        rows[0].judges.append("reserve")
        with_reserve = assign_judges(rows, {"main": 4.5})
        self.assertEqual(with_reserve["S1"].reserve, ["reserve"])
        self.assertEqual(h07_payload("demo", rows, with_reserve, {}), [])

    def test_main_assignments_and_first_reserves_take_priority(self):
        rows = [
            slot("S1", 840, 870, 1, ["main1", "main2", "r1", "r2"]),
            slot("S2", 855, 885, 1, ["main2", "r1", "r2"]),
            slot("S3", 885, 915, 1, ["main3", "r1"]),
        ]
        ratings = {"main1": 5, "main2": 4.9, "main3": 4.8, "r1": 4, "r2": 3}
        assignments = assign_judges(rows, ratings)

        self.assertEqual(assignments["S1"].main, ["main1"])
        self.assertEqual(assignments["S2"].main, ["main2"])
        self.assertEqual(assignments["S3"].main, ["main3"])
        self.assertEqual(assignments["S3"].reserve, ["r1"])
        self.assertEqual(
            set(assignments["S1"].reserve + assignments["S2"].reserve),
            {"r1", "r2"},
        )
        self.assertEqual(len(assignments["S1"].reserve), 1)
        self.assertEqual(len(assignments["S2"].reserve), 1)

    def test_main_shortage_and_reserve_limit(self):
        rows = [slot("S1", 840, 870, 2, ["a"])]
        assignments = assign_judges(rows, {})
        case = h07_payload("demo", rows, assignments, {})
        self.assertEqual(case["slot"]["required_judges"], 2)
        self.assertEqual(case["slot"]["assigned_judges"], ["J01"])

        rows = [slot("S1", 840, 870, 1, ["a", "b", "c", "d", "e"])]
        self.assertEqual(assign_judges(rows, {}, reserve_limit=1)["S1"].reserve, ["b"])
        self.assertEqual(assign_judges(rows, {})["S1"].reserve, ["b", "c", "d"])

    def test_reserve_assignment_is_busy_in_an_overlapping_case(self):
        rows = [
            slot("S1", 840, 870, 1, ["main1", "reserve"]),
            slot("S2", 855, 885, 1, ["main2", "reserve"]),
        ]
        assignments = assign_judges(rows, {})
        case = h07_payload("demo", rows, assignments, {})

        self.assertEqual(case["slot"]["id"], "S2")
        self.assertEqual(case["problem"], "Нет резервного судьи")
        self.assertEqual(
            next(judge for judge in case["candidates"] if judge["id"] == "J03"),
            {"id": "J03", "available": False, "rating": None, "busy_slots": ["14:00-14:30"]},
        )
        self.assertTrue(validate_recommendation(case, {"judge_id": "J03"}))
