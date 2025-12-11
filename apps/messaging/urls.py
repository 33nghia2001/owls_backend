from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, get_ws_ticket

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversations')

urlpatterns = [
    path('', include(router.urls)),
    path('ws-ticket/', get_ws_ticket, name='ws-ticket'),
]
