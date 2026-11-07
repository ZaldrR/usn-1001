"""Модель данных по ТЗ USN (п. 5.2, 6.1.2) и документу «Концепция MVP» v0.4.
Коды ролей совпадают с кодом заказчика."""
from dataclasses import dataclass, field
from datetime import datetime

ROLES = ("Player", "Voter", "Adviser", "Viewer")
ROLE_LABEL = {"Player": "Игрок", "Voter": "Судья", "Adviser": "Секундант", "Viewer": "Зритель"}
FORMAT_LABEL = {"classic": "классика", "express": "экспресс", "team": "командный", "mixed": "смешанный"}


@dataclass
class RoleRegistration:
    role: str
    is_open: bool
    closes_at: datetime  # задаёт организатор в Django Admin заказчика


@dataclass
class JudgeSlot:
    id: str
    start: datetime  # UTC
    end: datetime
    required_judges: int  # сколько судей нужно в слоте (задаёт организатор)


@dataclass
class Competition:
    id: str
    title: str
    format: str  # classic | express | team | mixed
    starts_at: datetime
    ends_at: datetime
    roles: list[RoleRegistration] = field(default_factory=list)
    judge_slots: list[JudgeSlot] = field(default_factory=list)


@dataclass
class Profile:
    email: str = ""
    last_name: str = ""
    first_name: str = ""
    country: str = ""
    city: str = ""
    club: str = ""
    position: str = ""
    company: str = ""
    about: str = ""
    telegram: str = ""
    vk: str = ""


@dataclass
class RegistrationData:
    """Заявка участника (то, что приходит из формы и уходит в API заказчика)."""
    competition_id: str
    role: str
    profile: Profile
    consent_personal_data: bool = False
    consent_photo_video: bool = False
    judge_slot_ids: list[str] = field(default_factory=list)  # только Судья
    advised_player_email: str = ""  # только Секундант
    team_partner_email: str = ""  # только Игрок в командном формате
    status: str = "submitted"  # submitted | accepted | withdrawn
