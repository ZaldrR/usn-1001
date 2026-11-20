
import csv
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

import truststore
from dotenv import load_dotenv
from gigachat import GigaChat

try:
    from .validators import validate_recommendation
    from .prompt import PROMPT_TEMPLATE, PROMPT_VERSION, build_prompt
except ImportError:
    from validators import validate_recommendation
    from prompt import PROMPT_TEMPLATE, PROMPT_VERSION, build_prompt


# SSL
truststore.inject_into_ssl()

# Пути
ROOT_DIR = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BENCHMARK_DIR / "results"

load_dotenv(ROOT_DIR / ".env")

API_KEY = os.getenv("GIGACHAT_AUTH_KEY")

if not API_KEY:
    raise RuntimeError("GIGACHAT_AUTH_KEY не найден")


# ==========================================
# НАСТРОЙКИ ЭКСПЕРИМЕНТА
# ==========================================

MODEL_NAMES = [
    "GigaChat-3-Lightning",
    "GigaChat-3-Pro",
    "GigaChat-2-Pro",
]

REPEATS = 3

# None = все case_*.json
# Например: ["case_07.json"]
SELECTED_CASES = None


# ==========================================
# ПРОВЕРКА ОДНОГО СЛУЧАЯ
# ==========================================

def run_case(client, case_path, model_name, repeat):
    with case_path.open(
        "r", encoding="utf-8"
    ) as file:
        case_data = json.load(file)

    result = {
        "case_id": case_data["case_id"],
        "model": model_name,
        "repeat": repeat,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": hashlib.sha256(
            PROMPT_TEMPLATE.encode("utf-8")
        ).hexdigest(),
        "judge_id": None,
        "reason": "",
        "status": "",
        "passed": "",
        "errors": "",
        "duration_sec": "",
        "raw_answer": "",
    }

    start = time.perf_counter()

    try:
        response = client.chat(
            build_prompt(case_data)
        )

        result["duration_sec"] = round(
            time.perf_counter() - start, 3
        )

    except Exception as error:
        result["status"] = "api_error"
        result["errors"] = type(error).__name__

        return result

    raw_answer = response.choices[0].message.content

    result["raw_answer"] = raw_answer

    try:
        recommendation = json.loads(raw_answer)

        if not isinstance(recommendation, dict):
            raise ValueError(
                "Ответ не является JSON-объектом"
            )

        if "judge_id" not in recommendation:
            raise ValueError(
                "Отсутствует поле judge_id"
            )

    except (json.JSONDecodeError, ValueError) as error:
        result["status"] = "format_error"
        result["passed"] = False
        result["errors"] = str(error)

        return result

    result["judge_id"] = recommendation["judge_id"]
    result["reason"] = recommendation.get("reason", "")

    try:
        errors = validate_recommendation(
            case_data,
            recommendation
        )

    except (KeyError, TypeError, ValueError) as error:
        result["status"] = "validation_error"
        result["passed"] = False
        result["errors"] = str(error)

        return result

    if errors:
        result["status"] = "invalid_recommendation"
        result["passed"] = False
        result["errors"] = "; ".join(errors)

    else:
        result["status"] = "passed"
        result["passed"] = True

    return result


# ==========================================
# ОСНОВНОЙ ЗАПУСК
# ==========================================

def main():
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    if SELECTED_CASES is None:
        case_paths = sorted(
            BENCHMARK_DIR.glob("case_*.json")
        )
    else:
        case_paths = [
            BENCHMARK_DIR / name
            for name in SELECTED_CASES
        ]

    if not case_paths:
        raise RuntimeError(
            "Тестовые случаи не найдены"
        )

    for path in case_paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    results = []

    for model_name in MODEL_NAMES:
        print(f"\n{'=' * 45}")
        print(f"МОДЕЛЬ: {model_name}")
        print(f"{'=' * 45}")

        with GigaChat(
            credentials=API_KEY,
            scope="GIGACHAT_API_PERS",
            model=model_name,
            ca_bundle_file=str(
                BENCHMARK_DIR
                / "certs"
                / "russian_trusted_root_ca_pem.crt"
            ),
        ) as client:

            for case_path in case_paths:

                print(
                    f"\nПроверяем {case_path.name}"
                )

                for repeat in range(1, REPEATS + 1):

                    print(
                        f"Повтор {repeat}/{REPEATS}"
                    )

                    result = run_case(
                        client,
                        case_path,
                        model_name,
                        repeat
                    )

                    results.append(result)

                    print(
                        "Статус:",
                        result["status"]
                    )

                    print(
                        "Выбор:",
                        result["judge_id"]
                    )

                    if result["errors"]:
                        print(
                            "Ошибки:",
                            result["errors"]
                        )

                    if result["duration_sec"] != "":
                        print(
                            "Время:",
                            result["duration_sec"],
                            "с"
                        )

    # Уникальное имя файла для каждого запуска.
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = (
        RESULTS_DIR
        / f"benchmark_{timestamp}.csv"
    )

    fieldnames = [
        "case_id",
        "model",
        "repeat",
        "prompt_version",
        "prompt_hash",
        "judge_id",
        "reason",
        "status",
        "passed",
        "errors",
        "duration_sec",
        "raw_answer",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 45}")
    print("ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'=' * 45}")

    for model_name in MODEL_NAMES:

        model_results = [
            row for row in results
            if row["model"] == model_name
        ]

        successful = sum(
            row["status"] == "passed"
            for row in model_results
        )

        api_errors = sum(
            row["status"] == "api_error"
            for row in model_results
        )

        durations = [
            row["duration_sec"]
            for row in model_results
            if isinstance(
                row["duration_sec"], (int, float)
            )
        ]

        average = (
            round(sum(durations) / len(durations), 3)
            if durations else None
        )

        print(f"\n{model_name}")
        print(
            f"Успешно: {successful}/{len(model_results)}"
        )
        print(f"Ошибок API: {api_errors}")
        print(f"Среднее время: {average} с")

    print(f"\nCSV сохранён: {output_path}")


if __name__ == "__main__":
    main()
