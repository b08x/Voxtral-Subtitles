"""
Input Validation and Safety Utilities

Provides comprehensive input validation to prevent system overload, security issues,
and resource exhaustion. All user inputs should be validated through these utilities.
"""

import os
import re
import logging
from typing import List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# File size limits (in bytes)
MAX_AUDIO_SIZE = 500 * 1024 * 1024  # 500MB
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_IMAGE_SIZE = 50 * 1024 * 1024   # 50MB per image
MAX_SUBTITLE_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Content limits
MAX_SUBTITLE_LINES = 10000
MAX_FILENAME_LENGTH = 255
MAX_PATH_DEPTH = 10

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass

def validate_file_size(file_path: Union[str, Path], max_size: int, file_type: str = "file") -> None:
    """
    Validate that file doesn't exceed size limits.

    Args:
        file_path: Path to file to validate
        max_size: Maximum allowed size in bytes
        file_type: Description of file type for error messages

    Raises:
        ValidationError: If file is too large or doesn't exist
    """
    path = Path(file_path)

    if not path.exists():
        raise ValidationError(f"{file_type} does not exist: {path}")

    if not path.is_file():
        raise ValidationError(f"Path is not a file: {path}")

    file_size = path.stat().st_size

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValidationError(
            f"{file_type} too large: {actual_mb:.1f}MB exceeds limit of {max_mb:.1f}MB"
        )

    logger.debug(f"File size validation passed: {path} ({file_size / (1024 * 1024):.1f}MB)")

def validate_audio_file(file_path: Union[str, Path]) -> None:
    """
    Validate audio file for processing.

    Args:
        file_path: Path to audio file

    Raises:
        ValidationError: If file is invalid
    """
    path = Path(file_path)

    # Check size
    validate_file_size(path, MAX_AUDIO_SIZE, "Audio file")

    # Check extension
    valid_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
    if path.suffix.lower() not in valid_extensions:
        raise ValidationError(
            f"Unsupported audio format: {path.suffix}. "
            f"Supported formats: {', '.join(sorted(valid_extensions))}"
        )

def validate_video_file(file_path: Union[str, Path]) -> None:
    """
    Validate video file for processing.

    Args:
        file_path: Path to video file

    Raises:
        ValidationError: If file is invalid
    """
    path = Path(file_path)

    # Check size
    validate_file_size(path, MAX_VIDEO_SIZE, "Video file")

    # Check extension
    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}
    if path.suffix.lower() not in valid_extensions:
        raise ValidationError(
            f"Unsupported video format: {path.suffix}. "
            f"Supported formats: {', '.join(sorted(valid_extensions))}"
        )

def validate_image_file(file_path: Union[str, Path]) -> None:
    """
    Validate image file for processing.

    Args:
        file_path: Path to image file

    Raises:
        ValidationError: If file is invalid
    """
    path = Path(file_path)

    # Check size
    validate_file_size(path, MAX_IMAGE_SIZE, "Image file")

    # Check extension
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    if path.suffix.lower() not in valid_extensions:
        raise ValidationError(
            f"Unsupported image format: {path.suffix}. "
            f"Supported formats: {', '.join(sorted(valid_extensions))}"
        )

def validate_image_sequence(image_paths: List[Union[str, Path]]) -> None:
    """
    Validate sequence of images for slideshow creation.

    Args:
        image_paths: List of paths to image files

    Raises:
        ValidationError: If any images are invalid
    """
    if not image_paths:
        raise ValidationError("No images provided")

    if len(image_paths) > 1000:  # Reasonable limit
        raise ValidationError(f"Too many images: {len(image_paths)} (max: 1000)")

    total_size = 0
    for i, image_path in enumerate(image_paths):
        try:
            validate_image_file(image_path)
            total_size += Path(image_path).stat().st_size
        except ValidationError as e:
            raise ValidationError(f"Image {i+1}: {e}")

    # Check total size of all images
    max_total_size = 1024 * 1024 * 1024  # 1GB total
    if total_size > max_total_size:
        total_mb = total_size / (1024 * 1024)
        max_mb = max_total_size / (1024 * 1024)
        raise ValidationError(
            f"Total image size too large: {total_mb:.1f}MB exceeds limit of {max_mb:.1f}MB"
        )

def sanitize_filename(filename: str) -> str:
    """
    Remove dangerous characters from filename.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        return "unnamed"

    # Remove dangerous characters, keep only alphanumeric, dots, dashes, underscores
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)

    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Trim length
    if len(sanitized) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(sanitized)
        max_name_len = MAX_FILENAME_LENGTH - len(ext)
        sanitized = name[:max_name_len] + ext

    # Ensure not empty
    if not sanitized or sanitized == '.':
        sanitized = "unnamed"

    return sanitized

def validate_api_key(api_key: Optional[str], service_name: str) -> None:
    """
    Validate API key format and presence.

    Args:
        api_key: API key to validate
        service_name: Name of service for error messages

    Raises:
        ValidationError: If API key is invalid
    """
    if not api_key:
        raise ValidationError(f"No {service_name} API key provided")

    if not isinstance(api_key, str):
        raise ValidationError(f"Invalid {service_name} API key format")

    # Basic format validation (not service-specific)
    if len(api_key.strip()) < 10:
        raise ValidationError(f"{service_name} API key appears too short")

    if ' ' in api_key or '\n' in api_key or '\t' in api_key:
        raise ValidationError(f"{service_name} API key contains invalid whitespace")

def validate_subtitle_count(subtitle_count: int) -> None:
    """
    Validate subtitle count to prevent memory exhaustion.

    Args:
        subtitle_count: Number of subtitle entries

    Raises:
        ValidationError: If count exceeds limits
    """
    if subtitle_count <= 0:
        raise ValidationError("No subtitles to process")

    if subtitle_count > MAX_SUBTITLE_LINES:
        raise ValidationError(
            f"Too many subtitle lines: {subtitle_count} (max: {MAX_SUBTITLE_LINES})"
        )

def validate_duration_range(duration_seconds: float) -> None:
    """
    Validate media duration is within reasonable bounds.

    Args:
        duration_seconds: Duration in seconds

    Raises:
        ValidationError: If duration is invalid
    """
    if duration_seconds <= 0:
        raise ValidationError("Duration must be positive")

    # Maximum 24 hours
    max_duration = 24 * 60 * 60
    if duration_seconds > max_duration:
        raise ValidationError(
            f"Duration too long: {duration_seconds:.1f}s (max: {max_duration}s / 24 hours)"
        )

def validate_resolution(width: int, height: int) -> None:
    """
    Validate image/video resolution.

    Args:
        width: Width in pixels
        height: Height in pixels

    Raises:
        ValidationError: If resolution is invalid
    """
    if width <= 0 or height <= 0:
        raise ValidationError(f"Invalid resolution: {width}x{height}")

    # Maximum 8K resolution
    max_pixels = 7680 * 4320
    total_pixels = width * height

    if total_pixels > max_pixels:
        raise ValidationError(
            f"Resolution too high: {width}x{height} ({total_pixels:,} pixels, max: {max_pixels:,})"
        )