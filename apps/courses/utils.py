"""
Utility functions for secure video URLs
"""
import cloudinary
import cloudinary.utils
from django.conf import settings
from datetime import timedelta
from django.utils import timezone


def generate_signed_video_url(public_id, duration_hours=None, streaming_format='hls'):
    """
    Generate a signed URL for HLS/DASH video streaming with expiration time.
    Uses adaptive bitrate streaming for better performance and security.
    
    SECURITY: Default duration reduced to 10 minutes for HLS to prevent replay attacks.
    HLS clients automatically refresh the manifest every 5-10 seconds, so short
    expiration doesn't affect playback but prevents URL sharing.
    
    Args:
        public_id: Cloudinary public_id of the video
        duration_hours: URL expiration time in hours (default: 10 min for HLS, 1 hour for MP4)
        streaming_format: 'hls' (m3u8) or 'dash' (mpd) - default: hls
    
    Returns:
        Signed streaming URL (m3u8 or mpd) with expiration
    """
    if not public_id:
        return None
    
    # SECURITY: Short expiration for HLS to prevent URL sharing/replay attacks
    # HLS players fetch manifest periodically, so short duration is safe
    if duration_hours is None:
        duration_hours = 1.0 if streaming_format == 'mp4' else (10 / 60)  # 10 minutes for HLS
    
    # Calculate expiration timestamp (Unix timestamp)
    expires_at = int((timezone.now() + timedelta(hours=duration_hours)).timestamp())
    
    # Generate HLS/DASH streaming URL with adaptive bitrate
    transformation = {
        'streaming_profile': 'hd',  # HD quality with adaptive bitrate
        'format': streaming_format,  # m3u8 for HLS, mpd for DASH
    }
    
    signed_url = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type='video',
        type='authenticated',
        sign_url=True,
        expires_at=expires_at,
        secure=True,
        **transformation
    )[0]
    
    return signed_url


def generate_video_thumbnail(public_id):
    """
    Generate video thumbnail from first frame.
    Used for video preview images.
    """
    if not public_id:
        return None
    
    return cloudinary.utils.cloudinary_url(
        public_id,
        resource_type='video',
        format='jpg',
        transformation=[
            {'width': 1280, 'height': 720, 'crop': 'fill'},
            {'start_offset': '0'}  # First frame
        ],
        secure=True
    )[0]


def generate_signed_resource_url(public_id, duration_hours=24):
    """
    Generate a signed URL for downloadable resources (PDF, documents).
    
    Args:
        public_id: Cloudinary public_id of the resource
        duration_hours: URL expiration time in hours (default: 24 hours)
    
    Returns:
        Signed URL string with expiration
    """
    if not public_id:
        return None
    
    expires_at = int((timezone.now() + timedelta(hours=duration_hours)).timestamp())
    
    signed_url = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type='raw',
        type='authenticated',
        sign_url=True,
        expires_at=expires_at,
        secure=True
    )[0]
    
    return signed_url
