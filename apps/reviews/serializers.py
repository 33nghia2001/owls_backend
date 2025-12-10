from rest_framework import serializers
from .models import Review, ReviewHelpful, InstructorReply, ReportReview
from apps.courses.serializers import CourseListSerializer


class InstructorReplySerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    
    class Meta:
        model = InstructorReply
        fields = ['id', 'review', 'instructor', 'instructor_name', 'reply_text', 'created_at', 'updated_at']
        read_only_fields = ['instructor', 'created_at', 'updated_at']


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    instructor_reply = InstructorReplySerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'course', 'user', 'user_name', 'user_avatar', 'rating', 'title', 
                  'comment', 'helpful_count', 'not_helpful_count', 'is_approved', 
                  'instructor_reply', 'created_at', 'updated_at']
        read_only_fields = ['user', 'helpful_count', 'not_helpful_count', 'is_approved', 
                           'created_at', 'updated_at']
    
    def get_user_avatar(self, obj):
        if obj.user.avatar:
            return obj.user.avatar.url
        return None
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def validate(self, data):
        """
        Kiểm tra user đã đăng ký và hoàn thành khóa học chưa.
        Chỉ cho phép review nếu đã học (enrollment completed hoặc active với progress > 0).
        """
        request = self.context.get('request')
        course = data.get('course')
        
        if request and course:
            # Kiểm tra enrollment
            from apps.enrollments.models import Enrollment
            
            enrollment = Enrollment.objects.filter(
                student=request.user,
                course=course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                raise serializers.ValidationError(
                    "You must be enrolled in this course to leave a review."
                )
            
            # Kiểm tra đã review chưa (chỉ cho review 1 lần)
            if self.instance is None:  # Chỉ check khi tạo mới, không check khi update
                if Review.objects.filter(user=request.user, course=course).exists():
                    raise serializers.ValidationError(
                        "You have already reviewed this course."
                    )
        
        return data


class ReviewHelpfulSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewHelpful
        fields = ['id', 'review', 'user', 'is_helpful', 'created_at']
        read_only_fields = ['user', 'created_at']


class ReportReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportReview
        fields = ['id', 'review', 'reported_by', 'reason', 'description', 
                  'status', 'reported_at']
        read_only_fields = ['reported_by', 'status', 'reported_at']
    
    def validate(self, data):
        """Kiểm tra user chưa report review này trước đó"""
        request = self.context.get('request')
        review = data.get('review')
        
        if request and review:
            if ReportReview.objects.filter(reported_by=request.user, review=review).exists():
                raise serializers.ValidationError(
                    "You have already reported this review."
                )
        
        return data
