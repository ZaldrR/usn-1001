"""Выгрузка проблемных слотов из локального расписания."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from registration.domain.types import JudgeSlot

from .solver import Judge, Panel, distribute


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schedule", type=Path, help="JSON со слотами и доступностью судей")
    parser.add_argument("--output", type=Path, help="файл JSON для H-07")
    parser.add_argument("--utc-offset", default="+00:00", help="смещение времени выгрузки, например +03:00")
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() == args.schedule.resolve():
            raise ValueError("Файл выгрузки должен отличаться от входного файла")
        zone = datetime.fromisoformat(f"2000-01-01T00:00:00{args.utc_offset}").tzinfo
        if zone is None:
            raise ValueError("Укажите смещение от UTC, например +03:00")
        data = json.loads(args.schedule.read_text(encoding="utf-8-sig"))
        slots = [
            JudgeSlot(row["id"], datetime.fromisoformat(row["start"]),
                      datetime.fromisoformat(row["end"]), row["required_judges"])
            for row in data["slots"]
        ]
        judges = []
        for row in data["judges"]:
            judge_id = row["id"]
            rating = row.get("rating")
            if rating is None:
                raise ValueError(f"Нет оценки H-06 для судьи {judge_id}")
            judges.append(Judge(
                judge_id, rating, frozenset(row["available_slots"]),
                tuple(
                    (datetime.fromisoformat(period["start"]), datetime.fromisoformat(period["end"]))
                    for period in row.get("busy_slots", [])
                ),
            ))
        result = distribute(
            slots,
            judges,
            reserve_required={row["id"]: row.get("required_reserve", 0) for row in data["slots"]},
            existing={
                row["id"]: Panel(tuple(row.get("assigned_judges", [])), tuple(row.get("assigned_reserve", [])))
                for row in data["slots"]
            },
            output_timezone=zone,
        )
        output = json.dumps(result.problem_cases, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(2, f"Ошибка выгрузки H-07: {error}\n")


if __name__ == "__main__":
    main()
