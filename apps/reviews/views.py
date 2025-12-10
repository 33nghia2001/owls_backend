from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.db.models import Q, Avg, Count
from django.db import models
from .models import Review, ReviewHelpful, InstructorReply, ReportReview
from .serializers import (
    ReviewSerializer,
    ReviewHelpfulSerializer,
    InstructorReplySerializer,
    ReportReviewSerializer
)
from apps.courses.models import Course


class ReviewCreateThrottle(UserRateThrottle):
    """Custom throttle cho việc tạo review - 10 lần/ngày"""
    scope = 'review_create'


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet cho Reviews.
    - List/Retrieve: Public (approved reviews)
    - Create: Chỉ enrolled students (throttled: 10/day)
    - Update/Delete: Chỉ owner
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_throttles(self):
        """Áp dụng throttle riêng cho create action"""
        if self.action == 'create':
            return [ReviewCreateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        """
        - Admin/Instructor: Xem tất cả reviews
        - User thường: Chỉ xem approved reviews
        - Filter by course_id nếu có
        """
        queryset = Review.objects.select_related('user', 'course').prefetch_related('instructor_reply')
        
        # Admin và instructor xem hết
        if self.request.user.is_authenticated and self.request.user.role in ['admin', 'instructor']:
            pass  # Xem tất cả
        else:
            # User thường chỉ xem approved
            queryset = queryset.filter(is_approved=True)
        
        # Filter by course nếu có tham số
        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Tự động gán user khi tạo review"""
        serializer.save(user=self.request.user)
        # Không cần gọi update_course_rating vì đã có Signal lo

    def perform_update(self, serializer):
        """Chỉ owner mới update được"""
        if serializer.instance.user != self.request.user:
            raise permissions.PermissionDenied("You can only edit your own review")
        serializer.save()

    def perform_destroy(self, instance):
        """Chỉ owner hoặc admin mới xóa được"""
        if instance.user != self.request.user and self.request.user.role != 'admin':
            raise permissions.PermissionDenied("You can only delete your own review")
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def helpful(self, request, pk=None):
        """Toggle helpful vote: Bấm lần đầu là Vote, bấm lần nữa (cùng loại) là Hủy vote"""
        review = self.get_object()
        is_helpful = request.data.get('is_helpful', True)
        
        existing_vote = ReviewHelpful.objects.filter(review=review, user=request.user).first()
        
        if existing_vote:
            if existing_vote.is_helpful == is_helpful:
                # Nếu vote giống hệt cái cũ -> Xóa (Unvote)
                existing_vote.delete()
                action = 'removed'
            else:
                # Nếu vote khác -> Đổi chiều vote
                existing_vote.is_helpful = is_helpful
                existing_vote.save()
                action = 'updated'
        else:
            # Chưa có vote -> Tạo mới
            ReviewHelpful.objects.create(review=review, user=request.user, is_helpful=is_helpful)
            action = 'created'
        
        # Cập nhật count vào Model Review
        review.helpful_count = ReviewHelpful.objects.filter(review=review, is_helpful=True).count()
        review.not_helpful_count = ReviewHelpful.objects.filter(review=review, is_helpful=False).count()
        review.save(update_fields=['helpful_count', 'not_helpful_count'])
        
        return Response({
            'status': 'success',
            'action': action,
            'helpful_count': review.helpful_count,
            'not_helpful_count': review.not_helpful_count
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def report(self, request, pk=None):
        """Report review không phù hợp"""
        review = self.get_object()
        
        serializer = ReportReviewSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(reported_by=request.user, review=review)
        
        return Response({
            'status': 'success',
            'message': 'Review reported successfully'
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def reply(self, request, pk=None):
        """Instructor reply to review"""
        review = self.get_object()
        
        # Chỉ instructor của khóa học mới reply được
        if review.course.instructor != request.user:
            raise permissions.PermissionDenied("Only course instructor can reply to reviews")
        
        reply_text = request.data.get('reply_text')
        if not reply_text:
            return Response({'error': 'reply_text is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Tạo hoặc cập nhật reply
        reply, created = InstructorReply.objects.update_or_create(
            review=review,
            defaults={
                'instructor': request.user,
                'reply_text': reply_text
            }
        )
        
        serializer = InstructorReplySerializer(reply)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class InstructorReplyViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet để xem instructor replies"""
    queryset = InstructorReply.objects.select_related('review', 'instructor')
    serializer_class = InstructorReplySerializer
    permission_classes = [permissions.AllowAny]
