from django.contrib import admin
from .models import Category, Course, Section, Lesson, Resource, Quiz, Question


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'is_active', 'order']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


class SectionInline(admin.TabularInline):
    model = Section
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'level', 'price', 'status', 'enrolled_count', 'created_at']
    list_filter = ['status', 'level', 'is_featured', 'category', 'created_at']
    search_fields = ['title', 'instructor__username', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SectionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'subtitle', 'description', 'instructor', 'category')
        }),
        ('Media', {
            'fields': ('thumbnail', 'preview_video')
        }),
        ('Course Details', {
            'fields': ('level', 'language', 'duration_hours')
        }),
        ('Pricing', {
            'fields': ('price', 'discount_price', 'is_free')
        }),
        ('Content', {
            'fields': ('requirements', 'what_you_will_learn', 'target_audience')
        }),
        ('Status', {
            'fields': ('status', 'is_featured', 'published_at')
        }),
    )


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'created_at']
    list_filter = ['course', 'created_at']
    search_fields = ['title', 'course__title']
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'section', 'lesson_type', 'order', 'is_preview', 'created_at']
    list_filter = ['lesson_type', 'is_preview', 'is_mandatory', 'created_at']
    search_fields = ['title', 'section__title']


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'file_size', 'created_at']
    search_fields = ['title', 'lesson__title']


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'passing_score', 'time_limit', 'created_at']
    search_fields = ['title', 'lesson__title']
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'quiz', 'question_type', 'points', 'order']
    list_filter = ['question_type', 'quiz']
    search_fields = ['question_text']
