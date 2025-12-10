"""
Custom validators for file uploads with magic bytes verification.

SECURITY: Uses python-magic to detect actual file type from binary content,
preventing file extension spoofing attacks (e.g., virus.exe renamed to document.pdf).
"""
from django.core.exceptions import ValidationError
import os
import magic


def validate_image_file(file):
    """
    Validate uploaded image files with magic bytes verification.
    
    SECURITY: Checks actual file content, not just extension or client-sent MIME type.
    - Only allow .jpg, .jpeg, .png, .gif, .webp
    - Max size: 5MB
    """
    # File size validation (5MB)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    if file.size > max_size:
        raise ValidationError(f'Image file size cannot exceed 5MB. Current size: {file.size / (1024*1024):.2f}MB')
    
    # File extension validation (basic check)
    ext = os.path.splitext(file.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    if ext not in valid_extensions:
        raise ValidationError(f'Only image files are allowed ({", ".join(valid_extensions)}). Got: {ext}')
    
    # SECURITY: Magic bytes validation (actual file content check)
    file.seek(0)  # Reset file pointer
    mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)  # Reset again for upload
    
    valid_mime_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if mime_type not in valid_mime_types:
        raise ValidationError(
            f'File content does not match image format. '
            f'Detected type: {mime_type}. Possible file spoofing attack.'
        )


def validate_resource_file(file):
    """
    Validate uploaded resource files (course materials) with magic bytes verification.
    
    SECURITY: Prevents malware uploads by checking actual file binary signatures.
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
    
    # SECURITY: Magic bytes validation (detect actual file type)
    file.seek(0)
    mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    
    # Map extensions to valid MIME types
    valid_mime_mapping = {
        '.pdf': ['application/pdf'],
        '.doc': ['application/msword'],
        '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        '.ppt': ['application/vnd.ms-powerpoint'],
        '.pptx': ['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
        '.zip': ['application/zip', 'application/x-zip-compressed'],
        '.rar': ['application/x-rar-compressed', 'application/vnd.rar']
    }
    
    expected_mimes = valid_mime_mapping.get(ext, [])
    if mime_type not in expected_mimes:
        raise ValidationError(
            f'File content does not match extension {ext}. '
            f'Detected type: {mime_type}. Possible malware or file spoofing.'
        )


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
