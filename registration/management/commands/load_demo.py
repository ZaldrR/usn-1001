"""Загружает тестовые заявки из mocks/registrations.json в базу: python manage.py load_demo"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from registration.models import Registration

CAMEL = {"lastName": "last_name", "firstName": "first_name"}


class Command(BaseCommand):
    help = "Загрузить тестовые (выдуманные) заявки из mocks/registrations.json"

    def handle(self, *args, **opts):
        raw = json.loads((settings.USN_MOCKS_DIR / "registrations.json").read_text(encoding="utf-8"))
        Registration.objects.all().delete()
        for r in raw:
            p = {CAMEL.get(k, k): v for k, v in r["profile"].items()}
            Registration.objects.create(
                competition_id=r["competitionId"], role=r["role"], status=r["status"], **p,
                consent_personal_data=r["consentPersonalData"], consent_photo_video=r["consentPhotoVideo"],
                judge_slot_ids=r.get("judgeSlotIds", []),
            )
        self.stdout.write(self.style.SUCCESS(f"Загружено заявок: {len(raw)}"))
