"""
Custom validators for file uploads
"""
from django.core.exceptions import ValidationError
import os


def validate_image_file(file):
    """
    Validate uploaded image files.
    - Only allow .jpg, .jpeg, .png, .gif, .webp
    - Max size: 5MB
    """
    # File size validation (5MB)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    if file.size > max_size:
        raise ValidationError(f'Image file size cannot exceed 5MB. Current size: {file.size / (1024*1024):.2f}MB')
    
    # File extension validation
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    if ext not in valid_extensions:
        raise ValidationError(f'Only image files are allowed ({", ".join(valid_extensions)}). Got: {ext}')
    
    # MIME type validation (additional security)
    valid_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if hasattr(file, 'content_type') and file.content_type not in valid_mime_types:
        raise ValidationError(f'Invalid image file type. Got: {file.content_type}')


def validate_resource_file(file):
    """
    Validate uploaded resource files (course materials).
    - Only allow .pdf, .doc, .docx, .ppt, .pptx, .zip
    - Max size: 50MB
    """
    # File size validation (50MB)
    max_size = 50 * 1024 * 1024  # 50MB in bytes
    if file.size > max_size:
        raise ValidationError(f'Resource file size cannot exceed 50MB. Current size: {file.size / (1024*1024):.2f}MB')
    
    # File extension validation
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip', '.rar']
    if ext not in valid_extensions:
        raise ValidationError(f'Only document/archive files are allowed ({", ".join(valid_extensions)}). Got: {ext}')
    
    # Dangerous extensions blacklist for security
    dangerous_extensions = ['.exe', '.bat', '.cmd', '.sh', '.php', '.asp', '.aspx', '.jsp', '.js', '.html', '.htm']
    if ext in dangerous_extensions:
        raise ValidationError(f'File type {ext} is not allowed for security reasons.')


def validate_video_thumbnail(file):
    """
    Validate video thumbnail images.
    - Only allow .jpg, .jpeg, .png
    - Max size: 2MB
    """
    # File size validation (2MB)
    max_size = 2 * 1024 * 1024  # 2MB in bytes
    if file.size > max_size:
        raise ValidationError(f'Thumbnail size cannot exceed 2MB. Current size: {file.size / (1024*1024):.2f}MB')
    
    # File extension validation
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(f'Only .jpg, .jpeg, .png are allowed for thumbnails. Got: {ext}')
