"""Жадная расстановка по карте доступности и выгрузка H-07."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from registration.domain.availability import SlotAvailability


@dataclass
class SlotAssignment:
    main: list[str] = field(default_factory=list)
    reserve: list[str] = field(default_factory=list)

    def is_problem(self, required: int) -> bool:
        return len(self.main) < required or not self.reserve


def _overlap(a: SlotAvailability, b: SlotAvailability) -> bool:
    return a.start < b.end and b.start < a.end


def _available(row: SlotAvailability) -> set[str]:
    return {email.strip().lower() for email in row.judges if email.strip()}


def assign_judges(
    rows: list[SlotAvailability], ratings: dict[str, float],
    *, reserve_limit: int = 3,
) -> dict[str, SlotAssignment]:
    """Сначала заполняет основные места, затем назначает резерв по одному за проход."""
    available = {row.slot_id: _available(row) for row in rows}
    ordered = sorted(rows, key=lambda row: (len(available[row.slot_id]), row.start, row.slot_id))
    occupied = defaultdict(list)
    assignments = {row.slot_id: SlotAssignment() for row in rows}

    def free_candidates(row: SlotAvailability) -> list[str]:
        return [
            email for email in available[row.slot_id]
            if not any(_overlap(row, other) for other in occupied[email])
        ]

    def pick(row: SlotAvailability, count: int) -> list[str]:
        candidates = free_candidates(row)
        candidates.sort(key=lambda email: (email not in ratings, -ratings.get(email, 0),
                                            len(occupied[email]), email))
        assigned = candidates[:count]
        for email in assigned:
            occupied[email].append(row)
        return assigned

    for row in ordered:
        assignments[row.slot_id].main = pick(row, row.required)

    reserve_order = sorted(ordered, key=lambda row: len(free_candidates(row)))
    for _ in range(reserve_limit):
        for row in reserve_order:
            assignments[row.slot_id].reserve.extend(pick(row, 1))

    return assignments


def _time_range(start: datetime, end: datetime, next_day: datetime) -> str:
    end_time = "24:00" if end == next_day else end.strftime("%H:%M")
    return f"{start:%H:%M}-{end_time}"


def h07_payload(
    competition_id: str,
    rows: list[SlotAvailability],
    assignments: dict[str, SlotAssignment],
    ratings: dict[str, float],
) -> dict | list[dict]:
    """Представляет оставшиеся дефициты без персональных данных."""
    judges = sorted(set().union(*(_available(row) for row in rows)))
    judge_ids = {email: f"J{index:02d}" for index, email in enumerate(judges, 1)}
    occupied = defaultdict(list)
    for row in rows:
        panel = assignments[row.slot_id]
        for email in panel.main + panel.reserve:
            occupied[email].append(row)

    cases = []
    for row in rows:
        panel = assignments[row.slot_id]
        if not panel.is_problem(row.required):
            continue
        assigned_in_slot = set(panel.main + panel.reserve)
        missing_main = row.required - len(panel.main)
        if missing_main > 0:
            required = row.required
            assigned = panel.main
            problem = f"Не хватает основных судей: {missing_main}"
            if not panel.reserve:
                problem += ". Нет резервного судьи"
        else:
            required = 1
            assigned = panel.reserve
            problem = "Нет резервного судьи"

        start = row.start.astimezone(timezone.utc)
        end = row.end.astimezone(timezone.utc)
        day = datetime.combine(start.date(), time.min, timezone.utc)
        next_day = day + timedelta(days=1)
        if end > next_day:
            raise ValueError(f"Слот {row.slot_id} пересекает полночь UTC и не помещается в формат H-07")

        available = _available(row)
        candidates = []
        for email in judges:
            if email in assigned_in_slot:
                continue
            busy_slots = {
                _time_range(max(other.start.astimezone(timezone.utc), day),
                            min(other.end.astimezone(timezone.utc), next_day), next_day)
                for other in occupied[email] if other.start < next_day and day < other.end
            }
            candidates.append({
                "id": judge_ids[email],
                "available": email in available and not any(_overlap(row, other) for other in occupied[email]),
                "rating": ratings.get(email),
                "busy_slots": sorted(busy_slots),
            })
        cases.append({
            "case_id": f"USN-{competition_id}-{row.slot_id}",
            "problem": problem,
            "slot": {
                "id": row.slot_id,
                "date": start.date().isoformat(),
                "time": _time_range(start, end, next_day),
                "required_judges": required,
                "assigned_judges": [judge_ids[email] for email in assigned],
            },
            "candidates": candidates,
        })
    return cases[0] if len(cases) == 1 else cases
