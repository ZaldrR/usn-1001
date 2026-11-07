"""Правила регистрации. Источники: ТЗ п. 5.2, 6.1.1, 6.1.2;
встреча с заказчиком 21.10 (ч.1 20:14, ч.2 13:00, 14:40)."""
from .types import Competition, RegistrationData

REQUIRED_PROFILE = [
    ("email", "e-mail"), ("last_name", "фамилия"), ("first_name", "имя"),
    ("country", "страна"), ("city", "город"),
]


class ConfigError(Exception):
    """API вернул конфигурацию, которой быть не должно (например, секундант в экспрессе)."""


def adviser_allowed(fmt: str) -> bool:
    """Секундант бывает только в классике (и в смешанном турнире с классикой)."""
    return fmt in ("classic", "mixed")


def available_roles(c: Competition) -> list[str]:
    """Роли, в которые сейчас можно зарегистрироваться.
    Открытый секундант в неклассическом формате — ошибка конфигурации:
    форму не показываем (решение заказчика, встреча ч.2 13:00)."""
    open_roles = [r.role for r in c.roles if r.is_open]
    if "Adviser" in open_roles and not adviser_allowed(c.format):
        raise ConfigError(f"Соревнование «{c.title}»: открыта роль секунданта для формата «{c.format}»")
    return open_roles


def can_combine(existing: list[str], new: str) -> bool:
    """Единственное разрешённое сочетание — игрок + секундант другого игрока.
    Секундант может быть у нескольких игроков (несколько регистраций Adviser)."""
    if not existing:
        return True
    return all(r in ("Player", "Adviser") for r in [*existing, new])


def is_same_application(a: RegistrationData, b: RegistrationData) -> bool:
    """Повторная заявка в ту же роль (для секунданта — к тому же игроку) = та же заявка, не дубль."""
    return (
        a.competition_id == b.competition_id
        and a.role == b.role
        and a.profile.email.strip().lower() == b.profile.email.strip().lower()
        and (a.role != "Adviser" or a.advised_player_email.lower() == b.advised_player_email.lower())
    )


def validate_registration(
    form: RegistrationData, c: Competition, my_registrations: list[RegistrationData] | None = None
) -> list[str]:
    """Возвращает список ошибок формы (пустой — форма корректна)."""
    errors: list[str] = []
    try:
        roles = available_roles(c)
    except ConfigError as e:
        return [str(e)]
    if form.role not in roles:
        errors.append("Регистрация на эту роль закрыта")

    for attr, label in REQUIRED_PROFILE:
        if not getattr(form.profile, attr, "").strip():
            errors.append(f"Не заполнено обязательное поле: {label}")
    if not form.consent_personal_data:
        errors.append("Нужно согласие на обработку персональных данных")
    if not form.consent_photo_video:
        errors.append("Нужно согласие на использование фото и видео")

    if form.role == "Voter":
        if not form.judge_slot_ids:
            errors.append("Судья должен отметить хотя бы один слот")
        known = {s.id for s in c.judge_slots}
        if any(s not in known for s in form.judge_slot_ids):
            errors.append("Выбран несуществующий слот")
    if form.role == "Adviser":
        if not form.advised_player_email.strip():
            errors.append("Секундант должен указать игрока")
        elif form.advised_player_email.strip().lower() == form.profile.email.strip().lower():
            errors.append("Нельзя быть секундантом самого себя")
    if form.role == "Player" and c.format == "team" and not form.team_partner_email.strip():
        errors.append("Игрок командного формата должен указать напарника")

    mine = [
        r for r in (my_registrations or [])
        if r.competition_id == c.id and r.status != "withdrawn"
    ]
    is_update = any(is_same_application(r, form) for r in mine)
    if not is_update and not can_combine([r.role for r in mine], form.role):
        errors.append("Такое сочетание ролей запрещено (можно только «игрок + секундант другого игрока»)")
    return errors
