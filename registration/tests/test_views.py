"""Проверяем, что страницы открываются и заявка сохраняется без дублей (критерий 8)."""
from django.test import TestCase

from registration.models import Registration

URL = "/competition/c-classic-2027-03/register/"
JUDGE = {
    "role": "Voter", "email": "judge@example.com", "last_name": "Петров", "first_name": "Пётр",
    "country": "Россия", "city": "Дубна", "judge_slot_ids": ["2027-03-13-s1", "2027-03-13-s4"],
    "consent_personal_data": "on", "consent_photo_video": "on",
}


class ViewTests(TestCase):
    def test_pages_open(self):
        for url in ["/", URL, "/organizer/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_config_error_page(self):
        r = self.client.get("/competition/c-broken-config/register/")
        self.assertContains(r, "Ошибка конфигурации")

    def test_judge_registration_without_duplicates(self):
        self.client.post(URL, JUDGE)
        self.client.post(URL, {**JUDGE, "judge_slot_ids": ["2027-03-13-s2"]})
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Registration.objects.get().judge_slot_ids, ["2027-03-13-s2"])

    def test_invalid_form_shows_errors(self):
        r = self.client.post(URL, {"role": "Voter"})
        self.assertContains(r, "Судья должен отметить хотя бы один слот")
        self.assertEqual(Registration.objects.count(), 0)
