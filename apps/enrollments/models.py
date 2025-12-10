from django.db import models
from django.conf import settings
from apps.courses.models import Course, Lesson, Quiz


class Enrollment(models.Model):
    """Student Course Enrollments"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    # SECURITY FIX: Use SET_NULL to preserve enrollment history for audit trails
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    
    # Payment reference (optional - có thể null nếu free course)
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollment'
    )
    
    # Progress
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    completed_lessons_count = models.PositiveIntegerField(default=0)
    total_time_spent = models.PositiveIntegerField(default=0)  # in seconds
    
    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)
    
    # Certificate
    certificate_issued = models.BooleanField(default=False)
    certificate_number = models.CharField(max_length=100, blank=True, unique=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'enrollments'
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
        ]
    
    def __str__(self):
        return f"{self.student.username} - {self.course.title}"
    
    def mark_as_completed(self):
        """Mark enrollment as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.progress_percentage = 100.00
        self.completed_at = timezone.now()
        self.save()


class LessonProgress(models.Model):
    """Track student progress for each lesson"""
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='student_progress')
    
    is_completed = models.BooleanField(default=False)
    time_spent = models.PositiveIntegerField(default=0)  # in seconds
    last_position = models.PositiveIntegerField(default=0)  # for video playback position
    
    completed_at = models.DateTimeField(null=True, blank=True)
    first_viewed_at = models.DateTimeField(auto_now_add=True)
    last_viewed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lesson_progress'
        unique_together = ['enrollment', 'lesson']
        verbose_name_plural = 'Lesson Progress'
    
    def __str__(self):
        return f"{self.enrollment.student.username} - {self.lesson.title}"
    
    def mark_as_completed(self):
        """Mark lesson as completed and auto-complete enrollment if 100% done"""
        from django.utils import timezone
        from django.db import transaction
        
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.save()
            
            # Update enrollment progress
            enrollment = self.enrollment
            enrollment.completed_lessons_count += 1
            
            # Calculate progress percentage
            total_lessons = enrollment.course.sections.aggregate(
                total=models.Count('lessons')
            )['total'] or 1
            enrollment.progress_percentage = (enrollment.completed_lessons_count / total_lessons) * 100
            
            # BUSINESS LOGIC FIX: Auto-complete enrollment when 100% done
            if enrollment.progress_percentage >= 100 and enrollment.status == 'active':
                enrollment.mark_as_completed()
                
                # Trigger certificate generation (async)
                transaction.on_commit(
                    lambda: self._trigger_certificate_generation(enrollment.id)
                )
            else:
                enrollment.save()
    
    def _trigger_certificate_generation(self, enrollment_id):
        """Helper to trigger certificate generation task"""
        try:
            from apps.payments.tasks import generate_course_certificate
            generate_course_certificate.delay(enrollment_id)
        except ImportError:
            pass  # Task app not available


class QuizAttempt(models.Model):
    """Student Quiz Attempts"""
    
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    max_score = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    
    answers = models.JSONField(default=dict)  # Store student answers
    time_taken = models.PositiveIntegerField(default=0)  # in seconds
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.enrollment.student.username} - {self.quiz.title} - {self.score}/{self.max_score}"


class Certificate(models.Model):
    """Course Completion Certificates"""
    
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    certificate_number = models.CharField(max_length=100, unique=True)
    
    student_name = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    instructor_name = models.CharField(max_length=255)
    
    issue_date = models.DateTimeField(auto_now_add=True)
    verification_url = models.URLField(blank=True)
    
    # Certificate file
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'certificates'
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"Certificate {self.certificate_number} - {self.student_name}"
