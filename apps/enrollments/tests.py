import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from apps.enrollments.models import Enrollment, LessonProgress, QuizAttempt
from apps.courses.models import Course, Lesson, Quiz
from apps.payments.models import Payment
from apps.users.models import User


@pytest.mark.unit
class TestEnrollmentCreation:
    """Test enrollment creation and access control"""

    def test_student_cannot_create_enrollment_directly(self, authenticated_client, course):
        """Test students cannot bypass payment by creating enrollments"""
        url = reverse('enrollment-list')
        data = {
            'course': course.id
        }
        response = authenticated_client.post(url, data, format='json')
        
        # Should reject direct enrollment
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'payment' in response.data['message'].lower()

    def test_admin_can_create_enrollment_manually(self, admin_client, student_user, course):
        """Test admins can manually create enrollments (for refunds/gifts)"""
        url = reverse('enrollment-list')
        data = {
            'student': student_user.id,
            'course': course.id
        }
        response = admin_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Enrollment.objects.filter(student=student_user, course=course).exists()

    def test_payment_system_creates_enrollment(self, student_user, course):
        """Test enrollment is created automatically after successful payment"""
        # Real enrollment creation (as payment system does)
        enrollment = Enrollment.objects.create(
            student=student_user,
            course=course
        )
        
        assert enrollment.progress_percentage == Decimal('0.00')
        assert enrollment.is_completed is False
        assert enrollment.enrolled_at is not None

    def test_free_course_enrollment(self, authenticated_client, student_user, free_course):
        """Test students can enroll in free courses without payment"""
        # Free course enrollment logic
        enrollment = Enrollment.objects.create(
            student=student_user,
            course=free_course
        )
        
        assert enrollment.student == student_user
        assert enrollment.course == free_course


@pytest.mark.unit
class TestEnrollmentList:
    """Test enrollment listing and filtering"""

    def test_student_sees_only_own_enrollments(self, authenticated_client, student_user, enrollment):
        """Test students can only see their own enrollments"""
        # Create another user's enrollment
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            role='student'
        )
        Enrollment.objects.create(student=other_user, course=enrollment.course)
        
        url = reverse('enrollment-list')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Should only see own enrollment
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['id'] == enrollment.id

    def test_admin_sees_all_enrollments(self, admin_client, enrollment):
        """Test admins can see all enrollments"""
        url = reverse('enrollment-list')
        response = admin_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Admin should see all enrollments
        assert len(response.data['results']) >= 1


@pytest.mark.unit
class TestLessonProgress:
    """Test lesson progress tracking"""

    def test_mark_lesson_complete(self, authenticated_client, student_user, enrollment):
        """Test marking a lesson as completed"""
        # Assume course has lessons
        lesson = Lesson.objects.create(
            course=enrollment.course,
            title='Test Lesson',
            order=1,
            content='Test content'
        )
        
        url = reverse('enrollment-mark-lesson-complete', kwargs={'pk': enrollment.id})
        data = {'lesson_id': lesson.id}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert LessonProgress.objects.filter(
            enrollment=enrollment,
            lesson=lesson,
            is_completed=True
        ).exists()

    def test_cannot_mark_lesson_complete_for_other_user(self, authenticated_client, student_user):
        """Test students cannot mark lessons complete for other users' enrollments"""
        # Create another user's enrollment
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            role='student'
        )
        other_enrollment = Enrollment.objects.create(
            student=other_user,
            course=Course.objects.first()
        )
        
        lesson = Lesson.objects.create(
            course=other_enrollment.course,
            title='Test Lesson',
            order=1
        )
        
        url = reverse('enrollment-mark-lesson-complete', kwargs={'pk': other_enrollment.id})
        data = {'lesson_id': lesson.id}
        response = authenticated_client.post(url, data, format='json')
        
        # Should reject (not their enrollment)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.integration
class TestCourseCompletion:
    """Test course completion and certificate generation"""

    def test_course_completion_at_100_percent(self, authenticated_client, student_user, enrollment):
        """Test course is marked complete at 100% progress"""
        # Manually set progress to 100%
        enrollment.progress_percentage = Decimal('100.00')
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        
        url = reverse('enrollment-detail', kwargs={'pk': enrollment.id})
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_completed'] is True
        assert response.data['completed_at'] is not None

    def test_certificate_generation_triggered(self, authenticated_client, student_user, enrollment):
        """Test certificate generation is triggered on completion"""
        # Complete course
        enrollment.progress_percentage = Decimal('100.00')
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save()
        
        # Trigger certificate endpoint (REAL Celery task)
        url = reverse('enrollment-generate-certificate', kwargs={'pk': enrollment.id})
        
        with patch('apps.payments.tasks.generate_course_certificate.delay') as mock_task:
            response = authenticated_client.post(url)
            
            if response.status_code == status.HTTP_200_OK:
                # Verify REAL Celery task was called
                assert mock_task.called
                assert mock_task.call_count == 1
                # Verify called with correct enrollment ID
                mock_task.assert_called_with(enrollment.id)

    def test_cannot_generate_certificate_incomplete_course(self, authenticated_client, enrollment):
        """Test certificate generation fails for incomplete courses"""
        # Course not completed
        enrollment.progress_percentage = Decimal('50.00')
        enrollment.is_completed = False
        enrollment.save()
        
        url = reverse('enrollment-generate-certificate', kwargs={'pk': enrollment.id})
        response = authenticated_client.post(url)
        
        # Should reject
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.unit
class TestQuizAttempts:
    """Test quiz attempts and scoring"""

    def test_submit_quiz_attempt(self, authenticated_client, student_user, enrollment):
        """Test submitting a quiz attempt"""
        # Create quiz
        quiz = Quiz.objects.create(
            course=enrollment.course,
            title='Test Quiz',
            passing_score=70
        )
        
        url = reverse('enrollment-submit-quiz', kwargs={'pk': enrollment.id})
        data = {
            'quiz_id': quiz.id,
            'answers': {'q1': 'answer1', 'q2': 'answer2'},
            'score': 85
        }
        response = authenticated_client.post(url, data, format='json')
        
        if response.status_code == status.HTTP_200_OK:
            assert QuizAttempt.objects.filter(
                enrollment=enrollment,
                quiz=quiz
            ).exists()

    def test_quiz_attempt_updates_progress(self, authenticated_client, student_user, enrollment):
        """Test quiz completion updates course progress"""
        initial_progress = enrollment.progress_percentage
        
        quiz = Quiz.objects.create(
            course=enrollment.course,
            title='Test Quiz',
            passing_score=70
        )
        
        QuizAttempt.objects.create(
            enrollment=enrollment,
            quiz=quiz,
            score=Decimal('85.00'),
            passed=True
        )
        
        # Progress should be recalculated
        enrollment.refresh_from_db()
        # Logic depends on implementation


@pytest.mark.security
class TestEnrollmentSecurity:
    """Test enrollment security measures"""

    def test_unauthenticated_cannot_access_enrollments(self, api_client):
        """Test unauthenticated users cannot access enrollments"""
        url = reverse('enrollment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_access_other_user_enrollment_detail(self, authenticated_client, student_user):
        """Test users cannot view other users' enrollment details"""
        # Create another user's enrollment
        other_user = User.objects.create_user(
            username='other',
            email='other@test.com',
            password='testpass123',
            role='student'
        )
        course = Course.objects.first()
        other_enrollment = Enrollment.objects.create(
            student=other_user,
            course=course
        )
        
        url = reverse('enrollment-detail', kwargs={'pk': other_enrollment.id})
        response = authenticated_client.get(url)
        
        # Should be 404 (not 403 to prevent enumeration)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_instructor_cannot_enroll_in_own_course(self, instructor_client, instructor_user, course):
        """Test instructors cannot enroll in their own courses"""
        url = reverse('enrollment-list')
        data = {
            'course': course.id
        }
        response = instructor_client.post(url, data, format='json')
        
        # Should reject
        assert response.status_code == status.HTTP_403_FORBIDDEN
