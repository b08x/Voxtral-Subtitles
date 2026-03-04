"""
Core utilities for Voxtral-Subtitles production-ready architecture.

This module provides foundational components for safe, reliable subtitle generation
including temporary file management, error handling, and resource cleanup.
"""

from .temp_manager import TempFileManager, get_temp_filename
from .subprocess_utils import (
    run_with_timeout, run_ffmpeg_safe, SubprocessResult, TimeoutError,
    validate_subprocess_result
)
from .validation import (
    ValidationError, validate_file_size, validate_audio_file, validate_video_file,
    validate_image_file, validate_image_sequence, sanitize_filename,
    validate_api_key, validate_subtitle_count, validate_duration_range,
    validate_resolution
)

__all__ = [
    # Temp file management
    'TempFileManager', 'get_temp_filename',

    # Subprocess safety
    'run_with_timeout', 'run_ffmpeg_safe', 'SubprocessResult', 'TimeoutError',
    'validate_subprocess_result',

    # Input validation
    'ValidationError', 'validate_file_size', 'validate_audio_file', 'validate_video_file',
    'validate_image_file', 'validate_image_sequence', 'sanitize_filename',
    'validate_api_key', 'validate_subtitle_count', 'validate_duration_range',
    'validate_resolution'
]