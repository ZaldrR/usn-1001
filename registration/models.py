"""Заявки храним у себя (статусы, слоты судей) и отправляем в систему заказчика через API.
Нужен ли собственный бэкенд в итоге — открытый вопрос 6 документа «Концепция MVP»."""
from django.db import models

from .domain.types import ROLE_LABEL, Profile, RegistrationData


class Registration(models.Model):
    STATUS_CHOICES = [("submitted", "Подана"), ("accepted", "Принята"), ("withdrawn", "Отозвана")]

    competition_id = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=list(ROLE_LABEL.items()))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")

    email = models.EmailField()
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    club = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    about = models.TextField(blank=True)
    telegram = models.CharField(max_length=100, blank=True)
    vk = models.CharField(max_length=200, blank=True)

    consent_personal_data = models.BooleanField(default=False)
    consent_photo_video = models.BooleanField(default=False)
    judge_slot_ids = models.JSONField(default=list, blank=True)
    advised_player_email = models.EmailField(blank=True)
    team_partner_email = models.EmailField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} — {ROLE_LABEL.get(self.role, self.role)} ({self.competition_id})"

    PROFILE_FIELDS = ["email", "last_name", "first_name", "country", "city",
                      "club", "position", "company", "about", "telegram", "vk"]

    def to_data(self) -> RegistrationData:
        return RegistrationData(
            competition_id=self.competition_id, role=self.role, status=self.status,
            profile=Profile(**{f: getattr(self, f) for f in self.PROFILE_FIELDS}),
            consent_personal_data=self.consent_personal_data,
            consent_photo_video=self.consent_photo_video,
            judge_slot_ids=list(self.judge_slot_ids or []),
            advised_player_email=self.advised_player_email,
            team_partner_email=self.team_partner_email,
        )

    @classmethod
    def fields_from_data(cls, d: RegistrationData) -> dict:
        out = {f: getattr(d.profile, f) for f in cls.PROFILE_FIELDS}
        out.update(
            competition_id=d.competition_id, role=d.role,
            consent_personal_data=d.consent_personal_data, consent_photo_video=d.consent_photo_video,
            judge_slot_ids=d.judge_slot_ids, advised_player_email=d.advised_player_email,
            team_partner_email=d.team_partner_email,
        )
        return out
