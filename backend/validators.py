"""
Common validators for file uploads and other validations.
"""
from rest_framework.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import magic  # python-magic for MIME type detection


# Allowed file types configuration
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
ALLOWED_DOCUMENT_TYPES = ['application/pdf']
ALLOWED_ATTACHMENT_TYPES = ALLOWED_IMAGE_TYPES + ALLOWED_DOCUMENT_TYPES

# File size limits (in bytes)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file_size(file, max_size):
    """Validate file size doesn't exceed limit."""
    if file.size > max_size:
        raise ValidationError(
            f'File size ({file.size / 1024 / 1024:.2f}MB) exceeds '
            f'maximum allowed size ({max_size / 1024 / 1024:.0f}MB).'
        )


def validate_file_type(file, allowed_types):
    """
    Validate file MIME type using python-magic for security.
    This checks the actual file content, not just the extension.
    """
    # Read a small portion of the file to detect type
    file_head = file.read(2048)
    file.seek(0)  # Reset file pointer
    
    try:
        # Use python-magic to detect actual MIME type from content
        mime = magic.Magic(mime=True)
        detected_type = mime.from_buffer(file_head)
    except Exception:
        # Fallback to content_type if magic fails
        detected_type = file.content_type
    
    if detected_type not in allowed_types:
        raise ValidationError(
            f'File type "{detected_type}" is not allowed. '
            f'Allowed types: {", ".join(allowed_types)}'
        )


def validate_image_upload(file):
    """Validate image file for product images, profile pictures, etc."""
    if not file:
        return
    
    validate_file_size(file, MAX_IMAGE_SIZE)
    validate_file_type(file, ALLOWED_IMAGE_TYPES)


def validate_document_upload(file):
    """Validate document file (PDF, etc.)."""
    if not file:
        return
    
    validate_file_size(file, MAX_DOCUMENT_SIZE)
    validate_file_type(file, ALLOWED_DOCUMENT_TYPES)


def validate_attachment_upload(file):
    """Validate attachment file for messaging (images + documents)."""
    if not file:
        return
    
    validate_file_size(file, MAX_ATTACHMENT_SIZE)
    validate_file_type(file, ALLOWED_ATTACHMENT_TYPES)


class ImageUploadValidator:
    """
    Validator class for use in serializer fields.
    Usage: attachment = serializers.FileField(validators=[ImageUploadValidator()])
    """
    
    def __call__(self, file):
        validate_image_upload(file)


class AttachmentUploadValidator:
    """
    Validator class for attachment fields in messaging.
    Usage: attachment = serializers.FileField(validators=[AttachmentUploadValidator()])
    """
    
    def __call__(self, file):
        validate_attachment_upload(file)
