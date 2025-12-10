from rest_framework import serializers
from .models import Review, ReviewHelpful, InstructorReply, ReportReview
from apps.courses.serializers import CourseListSerializer
from apps.users.serializers import PublicUserSerializer
# Lưu ý: Cần import Enrollment model bên trong method để tránh Circular Import, 
# hoặc nếu không bị vòng lặp thì import ở đây. Trong code dưới tôi để trong method cho an toàn.
import bleach


def sanitize_html(text):
    """
    Remove all HTML tags except safe ones.
    Prevents XSS attacks by stripping dangerous tags and attributes.
    """
    allowed_tags = []  # No HTML tags allowed (Plain text only)
    allowed_attrs = {}
    if text:
        return bleach.clean(text, tags=allowed_tags, attributes=allowed_attrs, strip=True)
    return text


class InstructorReplySerializer(serializers.ModelSerializer):
    instructor = PublicUserSerializer(read_only=True)  # Ẩn email/phone của instructor
    
    class Meta:
        model = InstructorReply
        fields = ['id', 'review', 'instructor', 'reply_text', 'created_at', 'updated_at']
        read_only_fields = ['instructor', 'created_at', 'updated_at']


class ReviewSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)  # Ẩn email/phone của reviewer
    user_avatar = serializers.SerializerMethodField()
    instructor_reply = InstructorReplySerializer(read_only=True)
    # Giới hạn 5000 ký tự để tránh spam/DoS database
    comment = serializers.CharField(max_length=5000)
    
    class Meta:
        model = Review
        fields = ['id', 'course', 'user', 'user_avatar', 'rating', 'title', 
                  'comment', 'helpful_count', 'not_helpful_count', 'is_approved', 
                  'instructor_reply', 'created_at', 'updated_at']
        read_only_fields = ['user', 'helpful_count', 'not_helpful_count', 'is_approved', 
                           'created_at', 'updated_at']
    
    def get_user_avatar(self, obj):
        if obj.user.avatar:
            return obj.user.avatar.url
        return None
    
    def validate_comment(self, value):
        """Sanitize comment to prevent XSS attacks"""
        return sanitize_html(value)
    
    def validate_title(self, value):
        """Sanitize title to prevent XSS attacks"""
        return sanitize_html(value)
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def validate(self, data):
        """
        Kiểm tra logic nghiệp vụ:
        1. User phải enrolled (active/completed).
        2. User chỉ được review 1 lần cho mỗi khóa học.
        """
        request = self.context.get('request')
        course = data.get('course')
        
        # Chỉ thực hiện validate nếu có request (để lấy user) và course
        if request and course:
            from apps.enrollments.models import Enrollment
            
            # 1. Kiểm tra enrollment
            # Tối ưu: Dùng .exists() nhanh hơn .first() nếu chỉ cần kiểm tra tồn tại
            has_enrollment = Enrollment.objects.filter(
                student=request.user,
                course=course,
                status__in=['active', 'completed']
            ).exists()
            
            if not has_enrollment:
                raise serializers.ValidationError(
                    "You must be enrolled in this course to leave a review."
                )
            
            # 2. Kiểm tra duplicate review (Chỉ check khi tạo mới - self.instance is None)
            if self.instance is None:
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
            # Tối ưu: Dùng .exists()
            if ReportReview.objects.filter(reported_by=request.user, review=review).exists():
                raise serializers.ValidationError(
                    "You have already reported this review."
                )
        
        return data