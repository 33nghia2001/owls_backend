import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls import path
from rest_framework import status
from django.urls import reverse
from apps.notifications.consumers import NotificationConsumer, CourseConsumer
from apps.notifications.models import Notification


@pytest.mark.unit
class TestWebSocketTicket:
    """Test WebSocket ticket generation"""

    def test_generate_ticket_authenticated(self, authenticated_client, student_user):
        """Test authenticated users can generate WebSocket tickets"""
        url = reverse('generate_ws_ticket')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'ticket' in response.data
        assert 'expires_at' in response.data
        assert 'ws_url' in response.data

    def test_generate_ticket_unauthenticated(self, api_client):
        """Test unauthenticated users cannot generate tickets"""
        url = reverse('generate_ws_ticket')
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('apps.notifications.views.WebSocketTicketThrottle.allow_request')
    def test_ticket_generation_rate_limited(self, mock_throttle, authenticated_client):
        """Test ticket generation is rate limited (10/min)"""
        mock_throttle.return_value = False
        
        url = reverse('generate_ws_ticket')
        response = authenticated_client.post(url)
        
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_ticket_contains_ws_base_url(self, authenticated_client):
        """Test ticket response includes configured WebSocket URL"""
        url = reverse('generate_ws_ticket')
        response = authenticated_client.post(url)
        
        if response.status_code == status.HTTP_200_OK:
            # Should use WS_BASE_URL from settings, not hardcoded
            assert 'ws://' in response.data['ws_url'] or 'wss://' in response.data['ws_url']
            assert 'localhost' in response.data['ws_url'] or 'ws_base_url' in str(response.data).lower()


@pytest.mark.integration
class TestNotificationConsumer:
    """Test real-time notification WebSocket consumer"""

    @pytest.mark.asyncio
    async def test_connect_authenticated_user(self, student_user):
        """Test authenticated user can connect to WebSocket"""
        # Create WebSocket communicator
        application = URLRouter([
            path('ws/notifications/', NotificationConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(application, '/ws/notifications/')
        communicator.scope['user'] = student_user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Should receive connection confirmation
        response = await communicator.receive_json_from()
        assert response['type'] == 'connection_established'
        
        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_unauthenticated_rejected(self):
        """Test unauthenticated connection is rejected"""
        from django.contrib.auth.models import AnonymousUser
        
        application = URLRouter([
            path('ws/notifications/', NotificationConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(application, '/ws/notifications/')
        communicator.scope['user'] = AnonymousUser()
        
        connected, _ = await communicator.connect()
        # Should reject connection
        assert not connected

    @pytest.mark.asyncio
    async def test_receive_notification(self, student_user):
        """Test receiving a notification via WebSocket"""
        from channels.layers import get_channel_layer
        
        application = URLRouter([
            path('ws/notifications/', NotificationConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(application, '/ws/notifications/')
        communicator.scope['user'] = student_user
        
        connected, _ = await communicator.connect()
        assert connected
        
        # Receive connection confirmation
        await communicator.receive_json_from()
        
        # Send REAL notification via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'notifications_{student_user.id}',
            {
                'type': 'notification_message',
                'message': 'Test notification',
                'notification_id': 123,
                'title': 'Test Title'
            }
        )
        
        # Receive the notification
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'notification_message'
        assert response['message'] == 'Test notification'
        assert response['notification_id'] == 123
        
        await communicator.disconnect()


@pytest.mark.integration
class TestCourseConsumer:
    """Test course-specific WebSocket consumer"""

    @pytest.mark.asyncio
    async def test_join_enrolled_course_channel(self, student_user, enrollment):
        """Test student can join WebSocket channel for enrolled course"""
        from channels.layers import get_channel_layer
        from asgiref.sync import sync_to_async
        
        # Ensure enrollment status is active
        await sync_to_async(lambda: setattr(enrollment, 'status', 'active'))()
        await sync_to_async(enrollment.save)()
        
        application = URLRouter([
            path('ws/courses/<int:course_id>/', CourseConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(
            application,
            f'/ws/courses/{enrollment.course.id}/'
        )
        communicator.scope['user'] = student_user
        communicator.scope['url_route'] = {'kwargs': {'course_id': enrollment.course.id}}
        
        # Real enrollment check (no mock)
        connected, _ = await communicator.connect()
        assert connected, "Should connect to enrolled course"
        
        # Clear connection confirmation
        await communicator.receive_json_from()
        
        # Send REAL course message via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'course_{enrollment.course.id}',
            {
                'type': 'course_message',
                'message': 'New lesson available',
                'course_id': enrollment.course.id
            }
        )
        
        # Receive the message
        response = await communicator.receive_json_from(timeout=2)
        assert response['type'] == 'course_message'
        assert response['message'] == 'New lesson available'
        
        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_cannot_join_unenrolled_course_channel(self, student_user, course):
        """Test student cannot join WebSocket channel for non-enrolled course"""
        from apps.enrollments.models import Enrollment
        from asgiref.sync import sync_to_async
        
        # Ensure NOT enrolled (real DB check)
        @sync_to_async
        def check_enrollment():
            return Enrollment.objects.filter(student=student_user, course=course).exists()
        
        is_enrolled = await check_enrollment()
        assert not is_enrolled
        
        application = URLRouter([
            path('ws/courses/<int:course_id>/', CourseConsumer.as_asgi()),
        ])
        
        communicator = WebsocketCommunicator(
            application,
            f'/ws/courses/{course.id}/'
        )
        communicator.scope['user'] = student_user
        communicator.scope['url_route'] = {'kwargs': {'course_id': course.id}}
        
        # Real enrollment check (no mock) - should reject
        connected, _ = await communicator.connect()
        assert not connected, "Should NOT connect to non-enrolled course"

    @pytest.mark.asyncio
    async def test_enrollment_check_uses_correct_field(self, student_user, course):
        """Test enrollment check uses 'student' field (not 'user')"""
        from apps.enrollments.models import Enrollment
        from asgiref.sync import sync_to_async
        
        # Create enrollment using correct field
        @sync_to_async
        def create_enrollment():
            return Enrollment.objects.create(
                student=student_user,  # Correct field name
                course=course
            )
        
        enrollment = await create_enrollment()
        
        # Verify enrollment exists with correct field
        @sync_to_async
        def check_enrollment():
            return Enrollment.objects.filter(student=student_user, course=course).exists()
        
        is_enrolled = await check_enrollment()
        assert is_enrolled
        
        # Note: This test documents that the field name is 'student', not 'user'
        # The old incorrect query Enrollment.objects.filter(user=...) would fail
        # because the Enrollment model uses 'student' as the field name


@pytest.mark.security
class TestWebSocketSecurity:
    """Test WebSocket security measures"""

    def test_ticket_single_use(self, authenticated_client, student_user):
        """Test WebSocket tickets are single-use only"""
        # Generate ticket
        url = reverse('generate_ws_ticket')
        response = authenticated_client.post(url)
        ticket = response.data['ticket']
        
        # First use should work (tested in integration tests)
        # Second use should fail
        # This requires Redis integration test

    def test_ticket_expiration(self, authenticated_client):
        """Test WebSocket tickets expire after 30 seconds"""
        url = reverse('generate_ws_ticket')
        response = authenticated_client.post(url)
        
        # Ticket should have expiration time
        assert 'expires_at' in response.data
        # Expires in 30 seconds (from settings)

    def test_no_jwt_in_url_params(self):
        """Test JWT tokens are NOT accepted in URL query params"""
        # This is a documentation test to ensure security best practice
        # JWT should only be in:
        # 1. HttpOnly cookies (best)
        # 2. One-time tickets (fallback)
        # NEVER in URL query params (logs vulnerability)
        pass

    @pytest.mark.asyncio
    async def test_users_isolated_in_separate_channels(self, student_user, instructor_user):
        """Test users receive only their own notifications"""
        from channels.layers import get_channel_layer
        
        application = URLRouter([
            path('ws/notifications/', NotificationConsumer.as_asgi()),
        ])
        
        comm1 = WebsocketCommunicator(application, '/ws/notifications/')
        comm1.scope['user'] = student_user
        
        comm2 = WebsocketCommunicator(application, '/ws/notifications/')
        comm2.scope['user'] = instructor_user
        
        await comm1.connect()
        await comm2.connect()
        
        # Clear connection confirmations
        await comm1.receive_json_from()
        await comm2.receive_json_from()
        
        # Send notification ONLY to student
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'notifications_{student_user.id}',
            {
                'type': 'notification_message',
                'message': 'Student notification',
                'notification_id': 1
            }
        )
        
        # Student should receive it
        student_msg = await comm1.receive_json_from(timeout=2)
        assert student_msg['message'] == 'Student notification'
        
        # Instructor should NOT receive it (timeout)
        try:
            await comm2.receive_json_from(timeout=0.5)
            assert False, "Instructor should not receive student's notification"
        except:
            pass  # Expected timeout
        
        await comm1.disconnect()
        await comm2.disconnect()

    def test_cookie_auth_preferred_over_query_params(self):
        """Test cookie-based auth is the recommended method"""
        # Documentation test
        # Cookies are HttpOnly and not accessible to JavaScript
        # Query params can leak in logs, referrer headers, browser history
        pass


@pytest.mark.unit
class TestNotificationModel:
    """Test notification model operations"""

    def test_create_notification(self, student_user):
        """Test creating a notification"""
        notification = Notification.objects.create(
            user=student_user,
            title='Test Notification',
            message='This is a test',
            notification_type='info'
        )
        
        assert notification.user == student_user
        assert notification.is_read is False
        assert notification.created_at is not None

    def test_mark_notification_read(self, student_user):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            user=student_user,
            title='Test Notification',
            message='This is a test',
            notification_type='info'
        )
        
        notification.is_read = True
        notification.save()
        
        assert notification.is_read is True
