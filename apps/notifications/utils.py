"""
Helper function to send real-time notifications via Django Channels.
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def send_notification_to_user(user_id, notification_data):
    """
    Send a real-time notification to a specific user via WebSocket.
    
    Args:
        user_id: ID of the user to send notification to
        notification_data: Dictionary containing notification details
            {
                'id': notification_id,
                'title': 'Notification title',
                'message': 'Notification message',
                'type': 'info|success|warning|error',
                'created_at': '2024-01-01T00:00:00Z',
                'is_read': False,
            }
    
    Example:
        from apps.notifications.utils import send_notification_to_user
        
        send_notification_to_user(user_id=student.id, notification_data={
            'id': notification.id,
            'title': 'New Lesson Available',
            'message': f'A new lesson has been added to {course.title}',
            'type': 'info',
            'created_at': notification.created_at.isoformat(),
            'is_read': False,
        })
    """
    channel_layer = get_channel_layer()
    
    # Send to user's personal notification channel
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user_id}',
        {
            'type': 'notification_message',
            'notification': notification_data
        }
    )


def send_course_update(course_slug, update_data):
    """
    Broadcast an update to all students connected to a course's activity channel.
    
    Args:
        course_slug: Slug of the course
        update_data: Dictionary containing update details
            {
                'type': 'new_lesson|announcement|quiz_available',
                'title': 'Update title',
                'message': 'Update message',
                'data': {...},  # Additional data
            }
    
    Example:
        from apps.notifications.utils import send_course_update
        
        send_course_update(course_slug='python-basics', update_data={
            'type': 'new_lesson',
            'title': 'New Lesson: Advanced Functions',
            'message': 'A new lesson has been published',
            'data': {
                'lesson_id': lesson.id,
                'lesson_title': lesson.title,
            }
        })
    """
    channel_layer = get_channel_layer()
    
    # Broadcast to all users in course activity channel
    async_to_sync(channel_layer.group_send)(
        f'course_activity_{course_slug}',
        {
            'type': 'course_update',
            'update': update_data
        }
    )
