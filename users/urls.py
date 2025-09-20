from django.urls import path
from . import views

urlpatterns = [
    path('debug/email-config/', views.debug_email_config, name='debug-email-config'),
]
