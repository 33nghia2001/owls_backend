# backend/apps/core/permissions.py
from rest_framework import permissions

class IsInstructorOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role in ['instructor', 'admin']

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user or request.user.is_staff


class IsEnrolledOrInstructor(permissions.BasePermission):
    """
    Permission để kiểm tra user có quyền xem nội dung bài học không.
    - Instructor/Admin luôn được xem
    - Bài học preview được xem free
    - Học viên đã đăng ký (enrollment active) được xem
    """
    def has_object_permission(self, request, view, obj):
        # obj ở đây là một Lesson instance
        
        # 1. Instructor hoặc Admin luôn được xem
        if request.user.is_authenticated and request.user.role in ['instructor', 'admin']:
            return True
            
        # 2. Nếu bài học cho phép xem thử (Preview)
        if obj.is_preview:
            return True
            
        # 3. Kiểm tra xem User đã mua khóa học chưa
        # Import bên trong hàm để tránh Circular Import
        if request.user.is_authenticated:
            from apps.enrollments.models import Enrollment
            return Enrollment.objects.filter(
                student=request.user, 
                course=obj.section.course, 
                status='active'
            ).exists()
        
        return False