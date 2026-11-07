"""Пограничные случаи из паспорта кейса (блоки 08, 11) и «Концепции MVP» v0.4, раздел 8."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from registration.domain.availability import judge_availability
from registration.domain.rules import ConfigError, available_roles, can_combine, validate_registration
from registration.domain.types import Profile, RegistrationData
from registration.usn_client import _parse_competition

MOCKS = Path(__file__).resolve().parents[2] / "mocks"
COMPS = {c["id"]: _parse_competition(c) for c in json.loads((MOCKS / "competitions.json").read_text("utf-8"))}
CLASSIC, EXPRESS = COMPS["c-classic-2027-03"], COMPS["c-express-2027-06"]
TEAM, BROKEN = COMPS["c-team-2027-08"], COMPS["c-broken-config"]


def form(**over) -> RegistrationData:
    base = dict(
        competition_id=CLASSIC.id, role="Viewer",
        profile=Profile(email="me@example.com", last_name="Иванов", first_name="Иван", country="Россия", city="Москва"),
        consent_personal_data=True, consent_photo_video=True,
    )
    base.update(over)
    return RegistrationData(**base)


class AvailableRolesTests(SimpleTestCase):
    def test_only_open_roles(self):
        self.assertEqual(available_roles(EXPRESS), ["Voter", "Viewer"])

    def test_adviser_in_express_is_config_error(self):
        with self.assertRaises(ConfigError):
            available_roles(BROKEN)


class CombineTests(SimpleTestCase):
    def test_player_plus_adviser_allowed(self):
        self.assertTrue(can_combine(["Player"], "Adviser"))

    def test_adviser_for_several_players_allowed(self):
        self.assertTrue(can_combine(["Adviser"], "Adviser"))

    def test_judge_plus_player_forbidden(self):
        self.assertFalse(can_combine(["Voter"], "Player"))

    def test_player_plus_viewer_forbidden(self):
        self.assertFalse(can_combine(["Player"], "Viewer"))


class ValidationTests(SimpleTestCase):
    def test_valid_viewer(self):
        self.assertEqual(validate_registration(form(), CLASSIC), [])

    def test_closed_role(self):
        errs = validate_registration(form(competition_id=EXPRESS.id, role="Player"), EXPRESS)
        self.assertIn("Регистрация на эту роль закрыта", errs)

    def test_judge_without_slots(self):
        self.assertIn("Судья должен отметить хотя бы один слот",
                      validate_registration(form(role="Voter"), CLASSIC))

    def test_adviser_of_himself(self):
        errs = validate_registration(form(role="Adviser", advised_player_email="ME@example.com"), CLASSIC)
        self.assertIn("Нельзя быть секундантом самого себя", errs)

    def test_team_player_without_partner(self):
        errs = validate_registration(form(competition_id=TEAM.id, role="Player"), TEAM)
        self.assertIn("Игрок командного формата должен указать напарника", errs)

    def test_required_fields_and_consents(self):
        f = form(consent_personal_data=False)
        f.profile.city = ""
        errs = validate_registration(f, CLASSIC)
        self.assertIn("Не заполнено обязательное поле: город", errs)
        self.assertIn("Нужно согласие на обработку персональных данных", errs)

    def test_judge_cannot_become_player(self):
        mine = [form(role="Voter", judge_slot_ids=["2027-03-13-s1"])]
        errs = validate_registration(form(role="Player"), CLASSIC, mine)
        self.assertTrue(any("сочетание ролей запрещено" in e for e in errs))


class AvailabilityTests(SimpleTestCase):
    def test_noon_slot_is_problem(self):
        raw = json.loads((MOCKS / "registrations.json").read_text("utf-8"))
        regs = [form(role="Voter", profile=Profile(email=r["profile"]["email"]),
                     judge_slot_ids=r["judgeSlotIds"]) for r in raw if r["role"] == "Voter"]
        noon = next(r for r in judge_availability(CLASSIC, regs) if r.slot_id == "2027-03-13-s4")
        self.assertTrue(noon.problem)
        self.assertEqual(noon.available, 3)
