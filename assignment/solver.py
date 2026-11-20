"""Жадная расстановка судей и выгрузка оставшихся дефицитов для H-07."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone, tzinfo
from math import isfinite

from registration.domain.types import JudgeSlot

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Judge:
    id: str
    rating: float
    available_slots: frozenset[str]
    busy_slots: tuple[Interval, ...] = ()


@dataclass(frozen=True)
class Panel:
    active: tuple[str, ...] = ()
    reserve: tuple[str, ...] = ()


@dataclass(frozen=True)
class Distribution:
    panels: dict[str, Panel]
    problem_cases: dict | list[dict]


def _interval(start: datetime, end: datetime) -> Interval:
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Укажите часовой пояс начала и конца интервала")
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if start >= end or any(t.second or t.microsecond for t in (start, end)):
        raise ValueError("Интервал должен быть положительным и заданным с точностью до минуты")
    return start, end


def _overlap(first: Interval, second: Interval) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def _local_day(start: datetime, zone: tzinfo) -> Interval:
    day = start.astimezone(zone).date()
    return (
        datetime.combine(day, time.min, zone).astimezone(timezone.utc),
        datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc),
    )


def _format_time(interval: Interval, day: Interval, zone: tzinfo) -> str:
    start, end = interval
    start_text = start.astimezone(zone).strftime("%H:%M")
    end_text = "24:00" if end == day[1] else end.astimezone(zone).strftime("%H:%M")
    if start_text >= end_text:
        raise ValueError("Интервал нельзя представить в H-07 в пределах одних суток")
    return f"{start_text}-{end_text}"


def _problem(active_missing: int, reserve_missing: int, empty: bool, has_reserve: bool) -> str:
    if has_reserve:
        return f"Не хватает основных судей: {active_missing}, резервных: {reserve_missing}."
    if empty:
        return f"Пустой слот. Требуется судей: {active_missing}."
    if active_missing == 1:
        return "Не хватает одного судьи"
    return f"Не хватает судей: {active_missing}."


def distribute(
    slots: Sequence[JudgeSlot],
    judges: Sequence[Judge],
    *,
    reserve_required: Mapping[str, int] | None = None,
    existing: Mapping[str, Panel] | None = None,
    output_timezone: tzinfo = timezone.utc,
) -> Distribution:
    """Дополняет подтверждённые назначения и формирует снимок дефицитов."""
    reserve_required = reserve_required or {}
    existing = existing or {}
    active_required = {slot.id: slot.required_judges for slot in slots}
    if len(active_required) != len(slots) or len({judge.id for judge in judges}) != len(judges):
        raise ValueError("ID судей и ID слотов должны быть уникальны")
    if (reserve_required.keys() | existing.keys()) - active_required.keys():
        raise ValueError("В требованиях к резерву или назначениях есть неизвестный слот")
    for required in (active_required, reserve_required):
        if any(type(count) is not int or count < 0 for count in required.values()):
            raise ValueError("Количество мест должно быть целым неотрицательным числом")
    if any(not isfinite(judge.rating) for judge in judges):
        raise ValueError("Оценка H-06 должна быть конечным числом")

    intervals = {slot.id: _interval(slot.start, slot.end) for slot in slots}
    ordered_slots = sorted(intervals, key=lambda sid: (*intervals[sid], sid))
    ranked_judges = sorted(judges, key=lambda judge: (-judge.rating, judge.id))
    busy = {judge.id: [_interval(*period) for period in judge.busy_slots] for judge in judges}
    active = {}
    reserve = {}
    for sid in ordered_slots:
        panel = existing.get(sid, Panel())
        active[sid], reserve[sid] = list(panel.active), list(panel.reserve)
        if len(active[sid]) > active_required[sid]:
            raise ValueError(f"Слот {sid}: назначений больше, чем основных мест")
        if len(reserve[sid]) > reserve_required.get(sid, 0):
            raise ValueError(f"Слот {sid}: назначений больше, чем резервных мест")
        for judge_id in active[sid] + reserve[sid]:
            if judge_id not in busy:
                raise ValueError(f"Слот {sid}: неизвестный судья {judge_id}")
            if any(_overlap(intervals[sid], period) for period in busy[judge_id]):
                raise ValueError(f"Слот {sid}: пересечение назначений судьи {judge_id}")
            busy[judge_id].append(intervals[sid])

    def is_available(judge: Judge, sid: str) -> bool:
        return sid in judge.available_slots and not any(
            _overlap(intervals[sid], period) for period in busy[judge.id]
        )

    def fill(panels: dict[str, list[str]], required: Mapping[str, int]) -> None:
        while True:
            options = []
            for sid in ordered_slots:
                missing = required.get(sid, 0) - len(panels[sid])
                if missing <= 0:
                    continue
                free = [judge for judge in ranked_judges if is_available(judge, sid)]
                if free:
                    options.append((len(free) - missing, sid, free[0]))
            if not options:
                return
            _, sid, judge = min(options, key=lambda option: option[0])
            panels[sid].append(judge.id)
            busy[judge.id].append(intervals[sid])

    fill(active, active_required)
    fill(reserve, reserve_required)

    cases = []
    for sid in ordered_slots:
        required_active = active_required[sid]
        required_reserve = reserve_required.get(sid, 0)
        active_missing = required_active - len(active[sid])
        reserve_missing = required_reserve - len(reserve[sid])
        if active_missing + reserve_missing == 0:
            continue

        interval = intervals[sid]
        day = _local_day(interval[0], output_timezone)
        if interval[1] > day[1]:
            raise ValueError(f"Слот {sid} пересекает полночь и не помещается в формат H-07")
        assigned = active[sid] + reserve[sid]
        candidates = [
            {
                "id": judge.id,
                "available": is_available(judge, sid),
                "rating": judge.rating,
                "busy_slots": sorted({
                    _format_time((max(start, day[0]), min(end, day[1])), day, output_timezone)
                    for start, end in busy[judge.id] if _overlap((start, end), day)
                }),
            }
            for judge in ranked_judges if judge.id not in assigned
        ]
        cases.append({
            "case_id": f"USN-{sid}",
            "problem": _problem(active_missing, reserve_missing, not assigned, bool(required_reserve)),
            "slot": {
                "id": sid,
                "date": interval[0].astimezone(output_timezone).date().isoformat(),
                "time": _format_time(interval, day, output_timezone),
                "required_judges": required_active + required_reserve,
                "assigned_judges": assigned,
            },
            "candidates": candidates,
        })

    return Distribution(
        panels={sid: Panel(tuple(active[sid]), tuple(reserve[sid])) for sid in ordered_slots},
        problem_cases=cases[0] if len(cases) == 1 else cases,
    )
