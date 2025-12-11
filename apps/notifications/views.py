from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message',
            'link', 'data', 'is_read', 'read_at', 'created_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_orders', 'email_promotions', 'email_reviews', 'email_newsletter',
            'push_orders', 'push_promotions', 'push_reviews'
        ]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications."""
        notifications = self.get_queryset().filter(is_read=False)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notification count."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response(NotificationSerializer(notification).data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': 'All notifications marked as read.'})
    
    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        """Delete all notifications."""
        self.get_queryset().delete()
        return Response({'message': 'All notifications cleared.'})


class NotificationPreferenceViewSet(viewsets.ViewSet):
    """ViewSet for notification preferences."""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get notification preferences."""
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs)
        return Response(serializer.data)
    
    def create(self, request):
        """Update notification preferences."""
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
