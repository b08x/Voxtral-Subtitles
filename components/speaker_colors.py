"""
Shared component for speaker color generation across all tabs.

This module provides unified speaker color logic to eliminate code duplication
and ensure consistent behavior across the vo_subtitles, multilingual,
image_slideshow, and transcription tabs.
"""

from typing import List, Dict, Union, Any
from models.subtitles import SpeakerColors, SubtitleTuple

def build_speaker_colors(
    subtitles: Union[List[SubtitleTuple], List[Dict[str, Any]]],
    primary_color: str,
    text_color: str,
    diarize: bool = True
) -> SpeakerColors:
    """
    Extract speaker color generation logic used by all tabs.

    Args:
        subtitles: List of subtitle tuples in various formats
        primary_color: User-selected primary color for first/main speaker
        text_color: Default text color for null speakers
        diarize: Whether speaker diarization is enabled

    Returns:
        Dict mapping speaker IDs to hex color codes
    """
    unique_speakers = extract_unique_speakers(subtitles)

    # Default color palette for additional speakers
    default_colors = [
        "#FFFFFF",  # White
        "#FFD700",  # Gold
        "#87CEEB",  # Sky Blue
        "#FF6B6B",  # Coral
        "#4ECDC4",  # Turquoise
        "#45B7D1",  # Light Blue
        "#00FF00",  # Lime
        "#FF00FF",  # Magenta
        "#00FFFF",  # Cyan
        "#FF0000",  # Red
        "#FFFF00",  # Yellow
        "#0000FF",  # Blue
        "#FF8000",  # Orange
        "#8000FF",  # Purple
        "#00FF80",  # Spring Green
        "#80FF00",  # Chartreuse
        "#0080FF",  # Azure
    ]

    speaker_colors = {}

    if unique_speakers:
        first_speaker = unique_speakers[0]
        speaker_colors[first_speaker] = primary_color

        # Assign default colors to remaining speakers
        for i, speaker in enumerate(unique_speakers[1:], 1):
            speaker_colors[speaker] = default_colors[i % len(default_colors)]

    # Always set fallback for null speaker
    speaker_colors["speaker_null"] = text_color if diarize else primary_color

    return speaker_colors


def extract_unique_speakers(
    subtitles: Union[List[SubtitleTuple], List[Dict[str, Any]]]
) -> List[str]:
    """
    Extract unique speaker IDs from subtitle data, handling different formats.

    Supports:
    - 5-tuple format: (start, end, text, word_segments, speaker)
    - 4-tuple format: (start, end, text, speaker)
    - Segments format: list of dicts with speaker_id

    Args:
        subtitles: Subtitle data in various formats

    Returns:
        List of unique speaker IDs in order of appearance
    """
    unique_speakers = []
    seen = set()

    if not subtitles:
        return unique_speakers

    # Handle different subtitle formats
    if isinstance(subtitles[0], dict):
        # Segments format (transcription.py)
        for segment in subtitles:
            speaker = segment.get("speaker_id", "speaker_null")
            if speaker not in seen:
                seen.add(speaker)
                unique_speakers.append(speaker)

    elif len(subtitles[0]) == 5:
        # 5-tuple format (vo_subtitles.py, image_slideshow.py)
        for _, _, _, word_segments, _ in subtitles:
            if word_segments:
                for word in word_segments:
                    speaker = word.get("speaker_id")
                    if speaker and speaker not in seen:
                        seen.add(speaker)
                        unique_speakers.append(speaker)

    elif len(subtitles[0]) == 4:
        # 4-tuple format (multilingual.py)
        for _, _, _, speaker in subtitles:
            if speaker and speaker not in seen:
                seen.add(speaker)
                unique_speakers.append(speaker)

    return unique_speakers


def get_speaker_color(
    speaker_colors: SpeakerColors,
    speaker_id: str,
    fallback_color: str = "#FFFFFF"
) -> str:
    """
    Safely get speaker color with fallback.

    Args:
        speaker_colors: Dict mapping speaker IDs to colors
        speaker_id: Speaker ID to look up
        fallback_color: Color to use if speaker not found

    Returns:
        Hex color code string
    """
    return speaker_colors.get(speaker_id, fallback_color)