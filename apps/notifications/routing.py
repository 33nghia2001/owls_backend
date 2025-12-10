"""
WebSocket URL routing for Django Channels.
"""
from django.urls import re_path
from apps.notifications import consumers

websocket_urlpatterns = [
    # Personal notifications channel
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    
    # Course-specific activity channel
    re_path(r'ws/course/(?P<course_slug>[\w-]+)/$', consumers.CourseActivityConsumer.as_asgi()),
]
