from django import forms

from .domain.types import ROLE_LABEL, Competition, Profile, RegistrationData

TIME = "%H:%M"


class RegistrationForm(forms.Form):
    role = forms.ChoiceField(label="Роль")
    email = forms.EmailField(label="E-mail *", required=False)
    last_name = forms.CharField(label="Фамилия *", required=False)
    first_name = forms.CharField(label="Имя *", required=False)
    country = forms.CharField(label="Страна *", required=False)
    city = forms.CharField(label="Город *", required=False)
    club = forms.CharField(label="Школа / клуб", required=False)
    position = forms.CharField(label="Должность", required=False)
    company = forms.CharField(label="Компания", required=False)
    about = forms.CharField(label="О себе", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    telegram = forms.CharField(label="Telegram", required=False)
    vk = forms.CharField(label="VK", required=False)
    judge_slot_ids = forms.MultipleChoiceField(
        label="Слоты, в которые вы готовы судить", required=False, widget=forms.CheckboxSelectMultiple)
    advised_player_email = forms.EmailField(label="E-mail игрока, которому секундируете *", required=False)
    team_partner_email = forms.EmailField(label="E-mail напарника по команде *", required=False)
    consent_personal_data = forms.BooleanField(label="Согласен на обработку персональных данных", required=False)
    consent_photo_video = forms.BooleanField(
        label="Согласен на использование фото и видео (формулировку даст заказчик)", required=False)

    def __init__(self, *args, competition: Competition, roles: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.competition = competition
        self.fields["role"].choices = [("", "— выберите —")] + [(r, ROLE_LABEL[r]) for r in roles]
        self.fields["judge_slot_ids"].choices = [
            (s.id, f"{s.start:%d.%m} · {s.start:{TIME}}–{s.end:{TIME}} UTC") for s in competition.judge_slots
        ]

    def profile_fields(self):
        """Поля анкеты, общие для всех ролей (ТЗ п. 6.1.2.1)."""
        return [self[f] for f in Profile.__dataclass_fields__]

    def to_data(self) -> RegistrationData:
        d = self.cleaned_data
        role = d.get("role", "")
        return RegistrationData(
            competition_id=self.competition.id, role=role,
            profile=Profile(**{f: (d.get(f) or "").strip() for f in Profile.__dataclass_fields__}),
            consent_personal_data=bool(d.get("consent_personal_data")),
            consent_photo_video=bool(d.get("consent_photo_video")),
            judge_slot_ids=list(d.get("judge_slot_ids") or []) if role == "Voter" else [],
            advised_player_email=(d.get("advised_player_email") or "") if role == "Adviser" else "",
            team_partner_email=(d.get("team_partner_email") or "")
            if role == "Player" and self.competition.format == "team" else "",
        )
