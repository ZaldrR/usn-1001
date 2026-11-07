"""Связь с системой заказчика USN (критерии готовности 1 и 9).

Пока USN_USE_MOCKS=true, данные берутся из mocks/competitions.json.
Пути API — заглушки: реальные сверяем со Swagger заказчика
(по договорённости команды — вручную или только локальной нейросетью)."""
import json
import urllib.request
from datetime import datetime

from django.conf import settings

from .domain.types import Competition, JudgeSlot, RegistrationData, RoleRegistration

ENDPOINTS = {
    "open_competitions": "/TODO-swagger/competitions?registration=open",
    "submit_registration": "/TODO-swagger/registrations",
}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_competition(raw: dict) -> Competition:
    """Перевод формата API (camelCase) во внутренние классы. TODO: сверить поля со Swagger."""
    return Competition(
        id=raw["id"], title=raw["title"], format=raw["format"],
        starts_at=_dt(raw["startsAt"]), ends_at=_dt(raw["endsAt"]),
        roles=[RoleRegistration(r["role"], r["isOpen"], _dt(r["closesAt"])) for r in raw["roles"]],
        judge_slots=[JudgeSlot(s["id"], _dt(s["start"]), _dt(s["end"]), s["requiredJudges"])
                     for s in raw["judgeSlots"]],
    )


def get_open_competitions() -> list[Competition]:
    if settings.USN_USE_MOCKS:
        raw = json.loads((settings.USN_MOCKS_DIR / "competitions.json").read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(settings.USN_API_BASE_URL + ENDPOINTS["open_competitions"], timeout=10) as r:
            raw = json.loads(r.read())
    return [_parse_competition(c) for c in raw]


def get_competition(competition_id: str) -> Competition | None:
    return next((c for c in get_open_competitions() if c.id == competition_id), None)


def submit_registration(data: RegistrationData) -> None:
    """Отправка данных формы в систему заказчика. В режиме моков ничего не отправляем."""
    if settings.USN_USE_MOCKS:
        return
    body = json.dumps({
        "competitionId": data.competition_id, "role": data.role, "profile": data.profile.__dict__,
        "judgeSlotIds": data.judge_slot_ids, "advisedPlayerEmail": data.advised_player_email,
        "teamPartnerEmail": data.team_partner_email,
    }).encode()
    req = urllib.request.Request(settings.USN_API_BASE_URL + ENDPOINTS["submit_registration"],
                                 data=body, headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=10)
