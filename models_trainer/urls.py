from models_trainer import views
from django.urls import path

urlpatterns = [
    path("", views.trainer, name="trainer"),
]
