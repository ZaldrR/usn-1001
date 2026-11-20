# ИИ-помощник по судьям (спринт 3)

Модуль расстановки судей по слотам и коллегиям (ТЗ п. 6.1.3, критерии готовности 10–13).
Схема, которую проверяем гипотезами H-03…H-05 спринта 2:

1. **Алгоритм** (жадный / OR-Tools CP-SAT) строит расстановку, которая гарантированно соблюдает правила.
2. **LLM-советник** объясняет решения, находит проблемные слоты, предлагает, кого пригласить, пишет текст приглашения.
3. Перед отправкой в LLM данные анонимизируются (ФИО → `judge_N`), таблица соответствия хранится у нас.
4. Окончательное решение всегда за организатором.

## Распределение и выгрузка H-07

`solver.distribute()` принимает слоты проекта (`JudgeSlot`) и судей
с обезличенным ID, оценкой H-06 и списком выбранных слотов.
Доступность для расписания можно взять из `registration/domain/availability.py`,
сопоставив email заявок с обезличенными ID H-06 внутри проекта.
Для подтверждённых назначений предусмотрен параметр `existing`.

Алгоритм сначала заполняет основные места, затем резервные, если для них
задана квота. На каждом шаге выбирает окно с наименьшей разницей между
числом свободных кандидатов и числом незакрытых мест. Из кандидатов берёт
судью с наивысшей оценкой, при равных оценках — по ID.
Подтверждённые назначения сохраняются и учитываются вместе с внешней занятостью.

### Данные из Colab H-06

Ноутбук читает тайминг, ответы судей и `scores = parse_scores(xls)`
из исходного Excel. В `h06_assignment_final.csv` записан результат CP-SAT.
Оценки в этом CSV есть только у судей, попавших в расстановку.

После разбора Excel в ноутбуке можно выполнить этот фрагмент в своей копии,
чтобы сформировать `schedule.json` из исходных оценок и доступности.
Укажи фактические даты турнира в порядке индексов `window.day`.
Используются квоты жадного эксперимента H-06 без категорий.

```python
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

dates_by_day = {0: date(2026, 11, 20), 1: date(2026, 11, 21)}  # Пример дат
zone = timezone(timedelta(hours=3))
timing_name = timing_dd.value
windows = parse_timing(pd.read_excel(xls, sheet_name=timing_name, header=None), timing_name)
availability = parse_responses(pd.read_excel(xls, sheet_name=responses_dd.value, header=None))
scores = parse_scores(xls)
is_express = "экспресс" in timing_name.lower() and "классик" not in timing_name.lower()
active_count, reserve_count = (5, 1) if is_express else (9, 3)


def timestamp(day, minutes):
    midnight = datetime.combine(dates_by_day[day], time.min, zone)
    return (midnight + timedelta(minutes=int(minutes))).isoformat()


missing_scores = sorted(availability.keys() - scores.keys())
if missing_scores:
    raise ValueError(f"В исходном Excel нет оценок H-06 для {', '.join(missing_scores)}")

schedule = {
    "slots": [
        {
            "id": window.key,
            "start": timestamp(window.day, window.start),
            "end": timestamp(window.day, window.end),
            "required_judges": active_count,
            "required_reserve": reserve_count,
        }
        for window in windows
    ],
    "judges": [
        {
            "id": judge_id,
            "rating": float(scores[judge_id]),
            "available_slots": [
                window.key for window in windows
                if is_available(periods, window.day, window.start, window.end)
            ],
        }
        for judge_id, periods in sorted(availability.items())
    ],
}
Path("schedule.json").write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
```

### Запуск из корня репозитория

```powershell
python -m assignment schedule.json --utc-offset +03:00 --output h07_cases.json
```

Входной `schedule.json` содержит слоты и доступность всех рассматриваемых судей.
Минимальный пример с одним назначением и одним незакрытым местом:

```json
{
  "slots": [
    {
      "id": "S001",
      "start": "2026-11-20T14:00:00+03:00",
      "end": "2026-11-20T14:30:00+03:00",
      "required_judges": 2
    }
  ],
  "judges": [
    {"id": "JUDGE_046", "available_slots": ["S001"], "rating": 3.0},
    {"id": "JUDGE_105", "available_slots": [], "rating": 3.0}
  ]
}
```

- `judges[].rating` — оценка из `parse_scores(xls)` по обезличенному ID судьи.
- В слоте можно указать `required_reserve`, `assigned_judges` и `assigned_reserve`.
  В выгрузке H-07 `required_judges` и `assigned_judges` включают обе группы,
  а `problem` показывает дефицит каждой. В Python группы доступны отдельно
  в `result.panels`.
- Необязательный `judges[].busy_slots` содержит внешнюю занятость в виде
  объектов с `start` и `end` в ISO 8601 со смещением. Занятость по назначениям
  из того же расписания вычисляется при распределении. По умолчанию дата
  и время в выходном JSON указаны в UTC. Флаг `--utc-offset` задаёт
  часовой пояс выгрузки. Одно окно H-07 должно помещаться в одни сутки
  в этом часовом поясе.

В `h07_cases.json` попадут только окна с дефицитом после расстановки.
Для одного окна файл содержит объект, для нескольких — массив, без дефицита — `[]`.
`available` отражает доступность с учётом занятости по итоговой расстановке.
Если для проверки GigaChat используется тот же список судей, корректный
ответ на оставшийся дефицит — `judge_id: null`: жадный алгоритм уже
использовал всех доступных кандидатов для этого окна.

### Передача в GigaChat

`distribute(...).problem_cases` можно передать в существующий клиент.
Клиент принимает по одному объекту за вызов.

```python
import json
from pathlib import Path

from assignment.benchmark.gigachat_client import get_recommendation

payload = json.loads(Path("h07_cases.json").read_text(encoding="utf-8"))
cases = payload if isinstance(payload, list) else [payload]
recommendations = [get_recommendation(case) for case in cases]
```

Сама выгрузка работает без ключа GigaChat. Настройка клиента описана
в [инструкции H-07](benchmark/README.md).
