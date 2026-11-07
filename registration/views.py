from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from . import usn_client
from .domain.availability import judge_availability
from .domain.rules import ConfigError, available_roles, is_same_application, validate_registration
from .domain.types import FORMAT_LABEL, ROLE_LABEL
from .forms import RegistrationForm
from .models import Registration


def _ctx(**kw):
    return {"use_mocks": settings.USN_USE_MOCKS, **kw}


def competition_list(request):
    """Шаг участника 1: список соревнований с открытой регистрацией."""
    comps = usn_client.get_open_competitions()
    items = [{
        "c": c, "format": FORMAT_LABEL.get(c.format, c.format),
        "open_roles": ", ".join(ROLE_LABEL[r.role] for r in c.roles if r.is_open) or "нет",
    } for c in comps]
    return render(request, "registration/competition_list.html", _ctx(items=items, tab="participant"))


def register(request, competition_id):
    """Шаги участника 2–4: роль, анкета, проверка, сохранение без дублей (ТЗ п. 6.1.2)."""
    c = usn_client.get_competition(competition_id)
    if c is None:
        raise Http404("Соревнование не найдено")
    try:
        roles = available_roles(c)
    except ConfigError as e:
        return render(request, "registration/register.html", _ctx(c=c, config_error=str(e), tab="participant"))

    errors, saved = [], None
    form = RegistrationForm(request.POST or None, competition=c, roles=roles)
    if request.method == "POST" and form.is_valid():
        data = form.to_data()
        email = data.profile.email.lower()
        mine = list(Registration.objects.filter(competition_id=c.id, email__iexact=email))
        errors = validate_registration(data, c, [r.to_data() for r in mine])
        if not errors:
            existing = next((r for r in mine if is_same_application(r.to_data(), data)), None)
            if existing:  # повторная регистрация = обновление той же заявки (критерий 8)
                for k, v in Registration.fields_from_data(data).items():
                    setattr(existing, k, v)
                existing.save()
                saved = existing
            else:
                saved = Registration.objects.create(**Registration.fields_from_data(data))
            usn_client.submit_registration(data)
    elif request.method == "POST":
        errors = [f"{form.fields[f].label}: {', '.join(e)}" for f, e in form.errors.items()]
    return render(request, "registration/register.html",
                  _ctx(c=c, form=form, errors=errors, saved=saved, tab="participant"))


def organizer(request):
    """Панель организатора: карта доступности судей (ТЗ п. 5.4, критерий 6)."""
    comps = usn_client.get_open_competitions()
    selected = request.GET.get("competition") or (comps[0].id if comps else "")
    c = next((x for x in comps if x.id == selected), None)
    rows, counts = [], []
    if c:
        regs = [r.to_data() for r in Registration.objects.filter(competition_id=c.id)]
        rows = judge_availability(c, regs)
        counts = [(ROLE_LABEL[role], sum(1 for r in regs if r.role == role and r.status != "withdrawn"))
                  for role in ROLE_LABEL]
    return render(request, "registration/organizer.html",
                  _ctx(comps=comps, c=c, rows=rows, counts=counts, tab="organizer"))
