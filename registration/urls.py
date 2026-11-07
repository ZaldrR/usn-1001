from django.urls import path

from . import views

urlpatterns = [
    path("", views.competition_list, name="competition_list"),
    path("competition/<str:competition_id>/register/", views.register, name="register"),
    path("organizer/", views.organizer, name="organizer"),
]
