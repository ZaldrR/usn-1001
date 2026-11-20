import unittest
from datetime import datetime, timedelta, timezone

from registration.domain.types import JudgeSlot

from .benchmark.validators import validate_recommendation
from .solver import Judge, Panel, distribute


def at(value: str) -> datetime:
    return datetime.fromisoformat(value + "+03:00")


def slot(sid: str, start: str, end: str, required: int = 1) -> JudgeSlot:
    return JudgeSlot(sid, at(start), at(end), required)


class DistributionTests(unittest.TestCase):
    def test_scarce_slot_first_and_highest_rating(self):
        slots = [
            slot("wide", "2026-11-20T14:00", "2026-11-20T15:00"),
            slot("scarce", "2026-11-20T14:30", "2026-11-20T15:00"),
            slot("adjacent", "2026-11-20T15:00", "2026-11-20T15:30"),
        ]
        judges = [
            Judge("J01", 5.0, frozenset({"wide", "scarce", "adjacent"})),
            Judge("J02", 4.0, frozenset({"wide"})),
            Judge("J03", 4.5, frozenset({"wide"})),
        ]

        result = distribute(slots, judges)
        self.assertEqual(result.panels["scarce"], Panel(("J01",)))
        self.assertEqual(result.panels["wide"], Panel(("J03",)))
        self.assertEqual(result.panels["adjacent"], Panel(("J01",)))
        self.assertEqual(result.problem_cases, [])

    def test_single_case_matches_h07_and_uses_local_busy_intervals(self):
        slots = [slot("S001", "2026-11-20T14:00", "2026-11-20T14:30", 3)]
        judges = [
            Judge("J01", 4.8, frozenset()),
            Judge("J02", 4.5, frozenset({"S001"})),
            Judge("J04", 4.9, frozenset({"S001"}), (
                (at("2026-11-20T14:00"), at("2026-11-20T14:30")),
                (at("2026-11-21T14:00"), at("2026-11-21T14:30")),
            )),
        ]
        confirmed = {"S001": Panel(("J01",))}
        result = distribute(slots, judges, existing=confirmed, output_timezone=timezone(timedelta(hours=3)))
        case = result.problem_cases
        self.assertEqual(case, {
            "case_id": "USN-S001",
            "problem": "Не хватает одного судьи",
            "slot": {
                "id": "S001",
                "date": "2026-11-20",
                "time": "14:00-14:30",
                "required_judges": 3,
                "assigned_judges": ["J01", "J02"],
            },
            "candidates": [{"id": "J04", "available": False, "rating": 4.9, "busy_slots": ["14:00-14:30"]}],
        })
        self.assertEqual(validate_recommendation(case, {"judge_id": None}), [])
        self.assertTrue(validate_recommendation(case, {"judge_id": "J04"}))
        self.assertEqual(confirmed["S001"], Panel(("J01",)))

    def test_reserve_cannot_preempt_active_and_multiple_cases_are_an_array(self):
        slots = [
            slot("reserve", "2026-11-20T14:00", "2026-11-20T14:30", 0),
            slot("active", "2026-11-20T14:10", "2026-11-20T14:30"),
            slot("empty", "2026-11-20T15:00", "2026-11-20T15:30"),
        ]
        judges = [Judge("J01", 4.5, frozenset({"reserve", "active"}))]
        result = distribute(slots, judges, reserve_required={"reserve": 1})

        reserve_case, empty_case = result.problem_cases
        self.assertEqual(result.panels["active"], Panel(("J01",)))
        self.assertIn("резервных: 1", reserve_case["problem"])
        self.assertEqual(reserve_case["candidates"][0]["busy_slots"], ["11:10-11:30"])
        self.assertEqual(empty_case["slot"]["assigned_judges"], [])
        self.assertEqual(validate_recommendation(reserve_case, {"judge_id": None}), [])
        self.assertEqual(validate_recommendation(empty_case, {"judge_id": None}), [])

    def test_rejects_duplicate_confirmed_assignment(self):
        slots = [slot("S001", "2026-11-20T14:00", "2026-11-20T14:30", 2)]
        judges = [Judge("J01", 4.5, frozenset({"S001"}))]
        with self.assertRaisesRegex(ValueError, "пересечение"):
            distribute(slots, judges, existing={"S001": Panel(("J01", "J01"))})
