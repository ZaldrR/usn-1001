"""Жадная расстановка по карте доступности и выгрузка H-07."""

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from registration.domain.availability import SlotAvailability


def _overlap(a: SlotAvailability, b: SlotAvailability) -> bool:
    return a.start < b.end and b.start < a.end


def _available(row: SlotAvailability) -> set[str]:
    return {email.strip().lower() for email in row.judges if email.strip()}


def assign_judges(
    rows: list[SlotAvailability], ratings: dict[str, float],
) -> dict[str, list[str]]:
    """Заполняет сначала окна с меньшим числом кандидатов."""
    available = {row.slot_id: _available(row) for row in rows}
    ordered = sorted(rows, key=lambda row: (len(available[row.slot_id]), row.start, row.slot_id))
    occupied = defaultdict(list)
    assignments = {}
    for row in ordered:
        candidates = [
            email for email in available[row.slot_id]
            if not any(_overlap(row, other) for other in occupied[email])
        ]
        candidates.sort(key=lambda email: (email not in ratings, -ratings.get(email, 0),
                                            len(occupied[email]), email))
        assigned = candidates[:row.required]
        assignments[row.slot_id] = assigned
        for email in assigned:
            occupied[email].append(row)
    return assignments


def _time_range(start: datetime, end: datetime, next_day: datetime) -> str:
    end_time = "24:00" if end == next_day else end.strftime("%H:%M")
    return f"{start:%H:%M}-{end_time}"


def h07_payload(
    competition_id: str,
    rows: list[SlotAvailability],
    assignments: dict[str, list[str]],
    ratings: dict[str, float],
) -> dict | list[dict]:
    """Представляет оставшиеся дефициты без персональных данных."""
    judges = sorted(set().union(*(_available(row) for row in rows)))
    judge_ids = {email: f"J{index:02d}" for index, email in enumerate(judges, 1)}
    occupied = defaultdict(list)
    for row in rows:
        for email in assignments[row.slot_id]:
            occupied[email].append(row)

    cases = []
    for row in rows:
        assigned = assignments[row.slot_id]
        missing = row.required - len(assigned)
        if missing <= 0:
            continue
        start = row.start.astimezone(timezone.utc)
        end = row.end.astimezone(timezone.utc)
        day = datetime.combine(start.date(), time.min, timezone.utc)
        next_day = day + timedelta(days=1)
        if end > next_day:
            raise ValueError(f"Слот {row.slot_id} пересекает полночь UTC и не помещается в формат H-07")

        available = _available(row)
        candidates = []
        for email in judges:
            if email in assigned:
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
            "problem": "Не хватает одного судьи" if missing == 1 else f"Не хватает судей: {missing}",
            "slot": {
                "id": row.slot_id,
                "date": start.date().isoformat(),
                "time": _time_range(start, end, next_day),
                "required_judges": row.required,
                "assigned_judges": [judge_ids[email] for email in assigned],
            },
            "candidates": candidates,
        })
    return cases[0] if len(cases) == 1 else cases
