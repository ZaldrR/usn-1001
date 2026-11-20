
import json
import os
import time
from pathlib import Path

import truststore
from dotenv import load_dotenv
from gigachat import GigaChat

from .validators import validate_recommendation
from .prompt import build_prompt


ROOT_DIR = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = Path(__file__).resolve().parent

CERT_PATH = (
    BENCHMARK_DIR
    / "certs"
    / "russian_trusted_root_ca_pem.crt"
)

DEFAULT_MODEL = "GigaChat-2-Pro"

load_dotenv(ROOT_DIR / ".env")
truststore.inject_into_ssl()


def get_recommendation(case_data, model=DEFAULT_MODEL):
    """
    Получает и проверяет рекомендацию GigaChat.

    case_data: словарь с данными проблемного слота.
    model: идентификатор модели GigaChat.

    Возвращает словарь с результатом проверки.
    Никаких назначений в базе данных не выполняет.
    """

    result = {
        "case_id": case_data.get("case_id"),
        "model": model,
        "status": None,
        "judge_id": None,
        "reason": "",
        "errors": [],
        "duration_sec": None,
    }

    api_key = os.getenv("GIGACHAT_AUTH_KEY")

    if not api_key:
        result["status"] = "config_error"
        result["errors"] = [
            "Не найден GIGACHAT_AUTH_KEY в .env"
        ]
        return result

    try:
        prompt = build_prompt(case_data)

        start = time.perf_counter()

        with GigaChat(
            credentials=api_key,
            scope="GIGACHAT_API_PERS",
            model=model,
            ca_bundle_file=str(CERT_PATH),
        ) as client:
            response = client.chat(prompt)

        result["duration_sec"] = round(
            time.perf_counter() - start,
            3
        )

    except Exception as error:
        result["status"] = "api_error"
        result["errors"] = [
            f"Ошибка обращения к GigaChat: "
            f"{type(error).__name__}"
        ]
        return result

    try:
        raw_answer = response.choices[0].message.content
        recommendation = json.loads(raw_answer)

        if not isinstance(recommendation, dict):
            raise ValueError(
                "Ответ должен быть JSON-объектом"
            )

        if "judge_id" not in recommendation:
            raise ValueError(
                "В ответе отсутствует judge_id"
            )

        judge_id = recommendation["judge_id"]
        reason = recommendation.get("reason", "")

        if judge_id is not None and not isinstance(
            judge_id, str
        ):
            raise ValueError(
                "judge_id должен быть строкой или null"
            )

        if not isinstance(reason, str):
            raise ValueError(
                "reason должен быть строкой"
            )

        result["judge_id"] = judge_id
        result["reason"] = reason

    except (ValueError, TypeError, KeyError, IndexError) as error:
        result["status"] = "format_error"
        result["errors"] = [str(error)]
        return result

    try:
        errors = validate_recommendation(
            case_data,
            recommendation
        )

    except (KeyError, TypeError, ValueError) as error:
        result["status"] = "validation_error"
        result["errors"] = [str(error)]
        return result

    if errors:
        result["status"] = "invalid_recommendation"
        result["errors"] = errors
    else:
        result["status"] = "passed"

    return result


if __name__ == "__main__":
    test_path = BENCHMARK_DIR / "case_01.json"

    with test_path.open("r", encoding="utf-8") as file:
        test_case = json.load(file)

    result = get_recommendation(test_case)

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )
