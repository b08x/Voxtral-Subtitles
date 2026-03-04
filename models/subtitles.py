"""
Typed data structures for subtitle handling.

This module provides type definitions and data contracts for subtitle
data to ensure type safety and consistency across the application.
"""

from typing import List, Dict, Tuple, Optional, Union, TypedDict, NamedTuple
from dataclasses import dataclass


# Type aliases for different subtitle formats
SubtitleTuple4 = Tuple[float, float, str, str]  # (start, end, text, speaker)
SubtitleTuple5 = Tuple[float, float, str, Optional[List[Dict]], str]  # (start, end, text, word_segments, speaker)
SubtitleTuple = Union[SubtitleTuple4, SubtitleTuple5]

# Speaker color mapping
SpeakerColors = Dict[str, str]

# Word segment structure
class WordSegment(TypedDict):
    """Type definition for word-level timing data."""
    text: str
    start: float
    end: Optional[float]
    speaker_id: Optional[str]


# Transcription segment structure
class TranscriptionSegment(TypedDict):
    """Type definition for transcription segment data."""
    text: str
    start: float
    end: float
    speaker_id: Optional[str]


# Complete transcription response
class TranscriptionResponse(TypedDict):
    """Type definition for transcription service response."""
    text: str
    words: List[WordSegment]
    segments: List[TranscriptionSegment]


# Subtitle generation parameters
@dataclass
class SubtitleSettings:
    """Settings for subtitle generation and styling."""
    font_name: str = "Arial"
    font_size: int = 20
    primary_colour: str = "#FFFFFF"
    secondary_colour: str = "#FF0000"
    outline_colour: str = "#000000"
    back_colour: str = "#80000000"
    bold: bool = False
    italic: bool = False
    border_style: int = 2
    alignment: int = 2
    margin_l: int = 10
    margin_r: int = 10
    margin_v: int = 10
    encoding: str = "utf-8"


# Validation result
@dataclass
class ValidationResult:
    """Result of validation operations."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, error: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)


# Processing pipeline result
@dataclass
class ProcessingResult:
    """Result of processing operations with optional error handling."""
    success: bool
    data: Optional[any] = None
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []