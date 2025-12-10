from django.urls import path
from .views import generate_ws_ticket

urlpatterns = [
    path('ws-ticket/', generate_ws_ticket, name='generate_ws_ticket'),
]
