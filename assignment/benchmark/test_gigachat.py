
import json
import os
from pathlib import Path

import truststore
from dotenv import load_dotenv
from gigachat import GigaChat

from validators import validate_recommendation


truststore.inject_into_ssl()

ROOT_DIR = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GIGACHAT_AUTH_KEY")

if not api_key:
    raise RuntimeError("Не найден GIGACHAT_AUTH_KEY в .env")


# Пока проверяем второй случай, где доступных
# кандидатов вообще нет.
case_path = BENCHMARK_DIR / "case_01.json"

with case_path.open("r", encoding="utf-8") as file:
    case_data = json.load(file)


prompt = f"""
Ты ИИ-помощник организатора соревнований USN.

Нужно предложить одного дополнительного судью
для проблемного слота.

Правила:
1. Выбирай только из массива candidates.
2. Судья должен иметь available = true.
3. Судья не должен присутствовать в assigned_judges.
4. Нельзя придумывать судей или их характеристики.
5. Если подходящих судей нет, верни judge_id = null.
6. Не делай выводов о квалификации без заданных правил.

Верни только корректный JSON без Markdown
и дополнительного текста.

Формат:
{{
  "judge_id": "ID судьи или null",
  "reason": "Краткое обоснование"
}}

Для отсутствующего судьи используй настоящий
JSON null, а не строку "null".

Исходные данные:
{json.dumps(case_data, ensure_ascii=False, indent=2)}
"""


with GigaChat(
    credentials=api_key,
    scope="GIGACHAT_API_PERS",
    model="GigaChat-3-Lightning",
    ca_bundle_file=str(
        BENCHMARK_DIR
        / "certs"
        / "russian_trusted_root_ca_pem.crt"
    ),
) as client:
    response = client.chat(prompt)


raw_answer = response.choices[0].message.content

print("\nОтвет модели:")
print(raw_answer)

try:
    recommendation = json.loads(raw_answer)

    if not isinstance(recommendation, dict):
        raise ValueError(
            "Ответ должен быть JSON-объектом"
        )

    if "judge_id" not in recommendation:
        raise ValueError(
            "Отсутствует поле judge_id"
        )

    errors = validate_recommendation(
        case_data,
        recommendation
    )

    print("\nРезультат проверки:")

    if errors:
        print("ПРОВАЛЕНО")

        for error in errors:
            print("-", error)
    else:
        print("ПРОЙДЕНО")

except (json.JSONDecodeError, ValueError) as error:
    print("\nПРОВАЛЕНО: некорректный формат ответа")
    print(error)
