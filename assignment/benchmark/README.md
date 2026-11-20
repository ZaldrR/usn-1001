
# H-07 — рекомендации по назначению судей

Модуль получает данные проблемного слота,
обращается к GigaChat и проверяет рекомендацию.

## Использование

```python
from assignment.benchmark.gigachat_client import get_recommendation

result = get_recommendation(case_data)
```

По умолчанию используется GigaChat-2-Pro.

## Входные данные

Один проблемный слот передаётся как Python-словарь:

```json
{
  "case_id": "USN-001",
  "problem": "Не хватает одного судьи",
  "slot": {
    "id": "S001",
    "date": "2026-11-20",
    "time": "14:00-14:30",
    "required_judges": 3,
    "assigned_judges": ["J01", "J02"]
  },
  "candidates": [
    {
      "id": "J03",
      "available": true,
      "rating": 4.5,
      "busy_slots": []
    }
  ]
}
```

`busy_slots` содержит интервалы занятости
на дату рассматриваемого слота.

Поля `slot.id` и `slot.date` передаются для
идентификации слота, но текущий валидатор
не проверяет даты.

Оценка `rating` передаётся как дополнительная
информация. Минимальный допустимый рейтинг
пока не задан.

## Выходные данные

```json
{
  "case_id": "USN-001",
  "model": "GigaChat-2-Pro",
  "status": "passed",
  "judge_id": "J03",
  "reason": "Судья доступен",
  "errors": [],
  "duration_sec": 0.8
}
```

Пример иллюстрирует структуру результата.

Возможные статусы:

- `passed` — ответ прошёл проверку.
- `invalid_recommendation` — нарушены ограничения.
- `format_error` — некорректный ответ модели.
- `api_error` — ошибка обращения к GigaChat.
- `config_error` — отсутствует API-ключ.
- `validation_error` — ошибка обработки данных валидатором.

Использовать рекомендацию можно только
при `status == "passed"`.

При этом даже `passed` не означает, что
рекомендация автоматически утверждена
организатором.

## Настройка

Необходимые Python-пакеты:

- gigachat
- python-dotenv
- truststore

API-ключ хранится только в локальном `.env`:

GIGACHAT_AUTH_KEY=значение_ключа

Файл `.env` запрещено добавлять в Git.

Для TLS используется публичный сертификат
из `assignment/benchmark/certs/`.

## Проверка

Из корня репозитория:

```powershell
python -m unittest assignment.benchmark.test_gigachat_client -v
python assignment/benchmark/test_validators.py -v
```

Запуск одного реального API-запроса:

```powershell
python -m assignment.benchmark.gigachat_client
```

## Ограничения

- Модуль обрабатывает один слот за вызов.
- Назначения в базе данных не изменяются.
- Валидатор проверяет доступность, занятость,
  повторные назначения и заполненность слота.
- Качество объяснений пока не проверяется.
- Формат данных должен быть согласован с
  выходными данными алгоритма H-06.
