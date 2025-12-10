from django.contrib import admin
from .models import Enrollment, LessonProgress, QuizAttempt, Certificate


class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0
    readonly_fields = ['lesson', 'is_completed', 'time_spent', 'completed_at']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'status', 'progress_percentage', 'enrolled_at', 'completed_at']
    list_filter = ['status', 'enrolled_at', 'completed_at']
    search_fields = ['student__username', 'student__email', 'course__title']
    readonly_fields = ['enrolled_at', 'completed_at', 'certificate_number']
    inlines = [LessonProgressInline]
    
    fieldsets = (
        ('Enrollment Info', {
            'fields': ('student', 'course', 'status')
        }),
        ('Progress', {
            'fields': ('progress_percentage', 'completed_lessons_count', 'total_time_spent')
        }),
        ('Dates', {
            'fields': ('enrolled_at', 'completed_at', 'expires_at', 'last_accessed_at')
        }),
        ('Certificate', {
            'fields': ('certificate_issued', 'certificate_number')
        }),
    )


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'lesson', 'is_completed', 'time_spent', 'completed_at']
    list_filter = ['is_completed', 'completed_at']
    search_fields = ['enrollment__student__username', 'lesson__title']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'quiz', 'score', 'max_score', 'passed', 'started_at', 'completed_at']
    list_filter = ['passed', 'started_at']
    search_fields = ['enrollment__student__username', 'quiz__title']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'student_name', 'course_title', 'issue_date']
    search_fields = ['certificate_number', 'student_name', 'course_title']
    readonly_fields = ['certificate_number', 'issue_date']
