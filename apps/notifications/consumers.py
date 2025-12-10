"""
WebSocket consumers for real-time notifications.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for receiving real-time notifications.
    
    Usage (frontend):
        const ws = new WebSocket('ws://localhost:8000/ws/notifications/?token=' + accessToken);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Notification:', data);
        };
    """
    
    async def connect(self):
        """Authenticate user and join their personal notification channel."""
        # Get user from scope (JWT middleware should populate this)
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            # Check for token in query params as fallback
            query_string = self.scope.get('query_string', b'').decode()
            if 'token=' in query_string:
                # Extract token and authenticate
                token = query_string.split('token=')[1].split('&')[0]
                self.user = await self.authenticate_token(token)
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Create personal notification channel for this user
        self.room_group_name = f'notifications_{self.user.id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to notifications for user {self.user.id}'
        }))
    
    async def disconnect(self, close_code):
        """Leave notification channel on disconnect."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming messages (if needed)."""
        data = json.loads(text_data)
        message_type = data.get('type')
        
        # Mark notification as read
        if message_type == 'mark_read':
            notification_id = data.get('notification_id')
            await self.mark_notification_read(notification_id)
    
    async def notification_message(self, event):
        """
        Receive notification from channel layer and send to WebSocket.
        
        This is called when channel_layer.group_send() is used with type='notification_message'
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    
    @database_sync_to_async
    def authenticate_token(self, token):
        """Authenticate user from JWT token in query params."""
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            return User.objects.get(id=user_id)
        except Exception:
            return None
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read."""
        from apps.notifications.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False


class CourseActivityConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for course-specific activity (new lessons, announcements, etc.)
    
    Usage:
        const ws = new WebSocket('ws://localhost:8000/ws/course/python-basics/?token=' + token);
    """
    
    async def connect(self):
        """Join course activity channel."""
        self.user = self.scope['user']
        self.course_slug = self.scope['url_route']['kwargs']['course_slug']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Verify user is enrolled in this course
        is_enrolled = await self.check_enrollment()
        if not is_enrolled:
            await self.close()
            return
        
        self.room_group_name = f'course_activity_{self.course_slug}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Leave course activity channel."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def course_update(self, event):
        """Broadcast course updates to all connected students."""
        await self.send(text_data=json.dumps({
            'type': 'course_update',
            'update': event['update']
        }))
    
    @database_sync_to_async
    def check_enrollment(self):
        """Verify user is enrolled in the course."""
        from apps.enrollments.models import Enrollment
        from apps.courses.models import Course
        try:
            course = Course.objects.get(slug=self.course_slug)
            return Enrollment.objects.filter(
                user=self.user,
                course=course,
                status='active'
            ).exists()
        except Course.DoesNotExist:
            return False
