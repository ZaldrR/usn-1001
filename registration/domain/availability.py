"""Карта доступности судей по слотам (ТЗ п. 5.4, критерий готовности 6)."""
from dataclasses import dataclass
from datetime import datetime

from .types import Competition, RegistrationData


@dataclass
class SlotAvailability:
    slot_id: str
    start: datetime
    end: datetime
    required: int
    available: int
    judges: list[str]  # e-mail или обезличенный ID
    problem: bool  # судей меньше, чем нужно


def judge_availability(c: Competition, regs: list[RegistrationData]) -> list[SlotAvailability]:
    judges = [r for r in regs if r.competition_id == c.id and r.role == "Voter" and r.status != "withdrawn"]
    rows = []
    for s in c.judge_slots:
        who = [j.profile.email for j in judges if s.id in j.judge_slot_ids]
        rows.append(SlotAvailability(
            slot_id=s.id, start=s.start, end=s.end, required=s.required_judges,
            available=len(who), judges=who, problem=len(who) < s.required_judges,
        ))
    return rows
