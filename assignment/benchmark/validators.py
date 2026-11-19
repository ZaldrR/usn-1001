def time_to_minutes(value):
    """Переводит время HH:MM в количество минут."""
    hours, minutes = map(int, value.strip().split(":"))
    return hours * 60 + minutes


def slots_overlap(slot_a, slot_b):
    """Проверяет пересечение двух интервалов времени."""
    start_a, end_a = slot_a.split("-")
    start_b, end_b = slot_b.split("-")

    a_start = time_to_minutes(start_a)
    a_end = time_to_minutes(end_a)

    b_start = time_to_minutes(start_b)
    b_end = time_to_minutes(end_b)

    return a_start < b_end and b_start < a_end


def validate_recommendation(case_data, recommendation):
    """
    Проверяет рекомендацию модели по исходным данным.
    Возвращает список обнаруженных ошибок.
    """
    errors = []

    assigned = set(
        case_data["slot"]["assigned_judges"]
    )

    current_slot = case_data["slot"]["time"]

    required_judges = case_data["slot"]["required_judges"]

    slot_is_full = len(assigned) >= required_judges

    candidates = {
        candidate["id"]: candidate
        for candidate in case_data["candidates"]
    }

    def is_eligible(candidate):
        """Проверяет допустимость кандидата."""
        return (
            not slot_is_full
            and candidate.get("available") is True
            and candidate["id"] not in assigned
            and not any(
                slots_overlap(current_slot, busy_slot)
                for busy_slot in candidate.get("busy_slots", [])
            )
        )

    judge_id = recommendation.get("judge_id")

    # Случай: модель никого не предлагает.
    if judge_id is None:
        if any(is_eligible(c) for c in candidates.values()):
            errors.append(
                "Есть подходящие кандидаты, "
                "но модель никого не предложила"
            )

        return errors

    # Проверяем тип идентификатора.
    if not isinstance(judge_id, str):
        errors.append("judge_id должен быть строкой или null")
        return errors

    # Проверяем существование кандидата.
    if judge_id not in candidates:
        errors.append(
            f"Судья {judge_id} отсутствует "
            "в списке кандидатов"
        )
        return errors

    # Проверяем заполненность слота.
    if slot_is_full:
        errors.append(
            "Слот уже заполнен: дополнительный судья не требуется"
        )

    # Проверяем повторное назначение.
    if judge_id in assigned:
        errors.append(
            f"Судья {judge_id} уже назначен"
        )

    # Проверяем доступность.
    if candidates[judge_id].get("available") is not True:
        errors.append(
            f"Судья {judge_id} недоступен"
        )


    # Проверяем занятость в текущем слоте.
    busy_slots = candidates[judge_id].get(
        "busy_slots", []
    )

    if any(
        slots_overlap(current_slot, busy_slot)
        for busy_slot in busy_slots
    ):
        errors.append(
            f"Судья {judge_id} занят "
            f"в интервале, пересекающемся с {current_slot}"
        )

    return errors