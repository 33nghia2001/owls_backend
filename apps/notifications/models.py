from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Notification(models.Model):
    """User Notifications"""
    
    NOTIFICATION_TYPES = (
        ('enrollment', 'New Enrollment'),
        ('course_update', 'Course Updated'),
        ('new_lesson', 'New Lesson Available'),
        ('assignment', 'New Assignment'),
        ('grade', 'Assignment Graded'),
        ('review', 'New Review'),
        ('reply', 'Instructor Reply'),
        ('payment', 'Payment Confirmation'),
        ('certificate', 'Certificate Issued'),
        ('announcement', 'Announcement'),
        ('message', 'New Message'),
        ('reminder', 'Reminder'),
        ('system', 'System Notification'),
    )
    
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    # Notification content
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Action URL
    action_url = models.URLField(blank=True, null=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Email notification
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """User notification preferences"""
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email notifications
    email_enrollment = models.BooleanField(default=True)
    email_course_updates = models.BooleanField(default=True)
    email_new_lessons = models.BooleanField(default=True)
    email_assignments = models.BooleanField(default=True)
    email_reviews = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_announcements = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)
    
    # Push notifications
    push_enrollment = models.BooleanField(default=True)
    push_course_updates = models.BooleanField(default=True)
    push_new_lessons = models.BooleanField(default=True)
    push_assignments = models.BooleanField(default=True)
    push_reviews = models.BooleanField(default=True)
    push_messages = models.BooleanField(default=True)
    
    # Digest settings
    daily_digest = models.BooleanField(default=False)
    weekly_digest = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f"Notification Preferences - {self.user.username}"


class Announcement(models.Model):
    """System-wide or course-specific announcements"""
    
    ANNOUNCEMENT_TYPES = (
        ('system', 'System Wide'),
        ('course', 'Course Specific'),
        ('category', 'Category Specific'),
    )
    
    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES, default='system')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='normal')
    
    # Target audience
    target_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='targeted_announcements')
    target_courses = models.ManyToManyField('courses.Course', blank=True, related_name='announcements')
    
    # Publishing
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_announcements')
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    view_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-published_at']
    
    def __str__(self):
        return self.title


class AnnouncementView(models.Model):
    """Track who viewed announcements"""
    
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='announcement_views')
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'announcement_views'
        unique_together = ['announcement', 'user']
    
    def __str__(self):
        return f"{self.user.username} viewed {self.announcement.title}"
