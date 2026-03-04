"""
Centralized validation for transcription service responses.

This module provides comprehensive validation for transcription responses
from different services (AssemblyAI, Deepgram) to ensure consistent
data structures and catch issues early in the pipeline.
"""

from typing import List, Dict, Tuple, Union, Any
from models.subtitles import TranscriptionResponse, SpeakerColors, SubtitleTuple

def validate_transcription_response(
    response: Any,
    source_service: str
) -> TranscriptionResponse:
    """
    Ensure response has required structure regardless of service.

    Args:
        response: Raw response from transcription service
        source_service: Name of the service for error messages

    Returns:
        Validated response dict

    Raises:
        ValueError: If response structure is invalid
        TypeError: If response has wrong type
    """
    if response is None:
        raise ValueError(f"Transcription response is None from {source_service}")

    if not isinstance(response, dict):
        raise TypeError(f"Expected dict, got {type(response)} from {source_service}")

    required_keys = {'text', 'words', 'segments'}
    missing_keys = required_keys - set(response.keys())
    if missing_keys:
        raise ValueError(f"Missing keys {missing_keys} from {source_service}")

    # Validate text content
    text = response.get('text', '')
    if not isinstance(text, str):
        raise ValueError(f"Expected string for 'text', got {type(text)} from {source_service}")

    # Validate words structure
    words = response.get('words', [])
    if not isinstance(words, list):
        raise ValueError(f"Expected list for 'words', got {type(words)} from {source_service}")

    for i, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValueError(f"Word {i} is not a dict in response from {source_service}")
        if 'text' not in word:
            raise ValueError(f"Word {i} missing 'text' field from {source_service}")
        if not isinstance(word['text'], str):
            raise ValueError(f"Word {i} 'text' is not a string from {source_service}")

    # Validate segments structure
    segments = response.get('segments', [])
    if not isinstance(segments, list):
        raise ValueError(f"Expected list for 'segments', got {type(segments)} from {source_service}")

    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError(f"Segment {i} is not a dict in response from {source_service}")
        if 'text' not in segment:
            raise ValueError(f"Segment {i} missing 'text' field from {source_service}")
        if not isinstance(segment['text'], str):
            raise ValueError(f"Segment {i} 'text' is not a string from {source_service}")

    return response


def validate_subtitle_parameters(
    subtitles: List[SubtitleTuple],
    speaker_colors: SpeakerColors
) -> None:
    """
    Validate parameters for subtitle generation functions.

    Args:
        subtitles: List of subtitle tuples
        speaker_colors: Dict mapping speaker IDs to colors

    Raises:
        TypeError: If parameters have wrong types
        ValueError: If parameters are None or invalid
    """
    if not isinstance(subtitles, list):
        raise TypeError(f"Expected list of subtitles, got {type(subtitles)}")

    if speaker_colors is None:
        raise ValueError("speaker_colors parameter is required")

    if not isinstance(speaker_colors, dict):
        raise TypeError(f"Expected dict for speaker_colors, got {type(speaker_colors)}")

    # Validate subtitle structure if not empty
    if subtitles:
        first_subtitle = subtitles[0]
        if not isinstance(first_subtitle, (tuple, list)):
            raise TypeError(f"Expected tuple/list for subtitle, got {type(first_subtitle)}")

        # Check for supported subtitle formats
        if len(first_subtitle) not in [4, 5]:
            raise ValueError(f"Unsupported subtitle format: {len(first_subtitle)} elements. Expected 4 or 5.")


def validate_api_keys() -> Tuple[bool, bool]:
    """
    Validate that at least one transcription API key is configured.

    Returns:
        Tuple of (assemblyai_available, deepgram_available)

    Raises:
        ValueError: If no API keys are configured
    """
    import os

    assemblyai_key = os.getenv("ASSEMBLYAI_API_KEY")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")

    assemblyai_available = bool(assemblyai_key and assemblyai_key.strip())
    deepgram_available = bool(deepgram_key and deepgram_key.strip())

    if not (assemblyai_available or deepgram_available):
        raise ValueError(
            "No transcription API keys configured. "
            "Please set either ASSEMBLYAI_API_KEY or DEEPGRAM_API_KEY in your .env file."
        )

    return assemblyai_available, deepgram_available


def validate_audio_file(audio_path: str) -> None:
    """
    Validate audio file exists and has supported format.

    Args:
        audio_path: Path to audio file

    Raises:
        ValueError: If file doesn't exist or has unsupported format
    """
    import os

    if not audio_path:
        raise ValueError("Audio file path is required")

    if not os.path.exists(audio_path):
        raise ValueError(f"Audio file does not exist: {audio_path}")

    if not os.path.isfile(audio_path):
        raise ValueError(f"Audio path is not a file: {audio_path}")

    # Check file extension
    supported_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.mp4', '.mov', '.avi'}
    file_ext = os.path.splitext(audio_path)[1].lower()

    if file_ext not in supported_extensions:
        raise ValueError(f"Unsupported audio format: {file_ext}. Supported: {supported_extensions}")