"""
Tests for the transcription pipeline functionality.

This module tests the core transcription functionality including
validation, API integration, and error handling scenarios.
"""

import pytest
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from validation.transcription_validator import (
    validate_transcription_response,
    validate_subtitle_parameters,
    validate_api_keys,
    validate_audio_file
)


class TestTranscriptionValidation(unittest.TestCase):
    """Test transcription response validation."""

    def test_valid_transcription_response(self):
        """Test validation with valid response."""
        valid_response = {
            'text': 'Hello world',
            'words': [
                {'text': 'Hello', 'start': 0.0, 'end': 1.0},
                {'text': 'world', 'start': 1.0, 'end': 2.0}
            ],
            'segments': [
                {'text': 'Hello world', 'start': 0.0, 'end': 2.0}
            ]
        }

        result = validate_transcription_response(valid_response, "TestService")
        self.assertEqual(result, valid_response)

    def test_none_response_validation(self):
        """Test validation correctly rejects None response."""
        with self.assertRaises(ValueError) as context:
            validate_transcription_response(None, "TestService")

        self.assertIn("response is None", str(context.exception))
        self.assertIn("TestService", str(context.exception))

    def test_invalid_type_response(self):
        """Test validation rejects non-dict responses."""
        with self.assertRaises(TypeError):
            validate_transcription_response("invalid", "TestService")

    def test_missing_keys_validation(self):
        """Test validation catches missing required keys."""
        invalid_response = {'text': 'Hello'}  # Missing 'words' and 'segments'

        with self.assertRaises(ValueError) as context:
            validate_transcription_response(invalid_response, "TestService")

        self.assertIn("Missing keys", str(context.exception))

    def test_invalid_words_structure(self):
        """Test validation catches invalid word structures."""
        invalid_response = {
            'text': 'Hello',
            'words': [{'invalid': 'structure'}],  # Missing 'text' field
            'segments': []
        }

        with self.assertRaises(ValueError):
            validate_transcription_response(invalid_response, "TestService")

    def test_invalid_segments_structure(self):
        """Test validation catches invalid segment structures."""
        invalid_response = {
            'text': 'Hello',
            'words': [],
            'segments': [{'invalid': 'structure'}]  # Missing 'text' field
        }

        with self.assertRaises(ValueError):
            validate_transcription_response(invalid_response, "TestService")


class TestSubtitleParametersValidation(unittest.TestCase):
    """Test subtitle parameters validation."""

    def test_valid_subtitle_parameters(self):
        """Test validation passes with valid parameters."""
        subtitles = [(0.0, 1.0, "Hello", [], "speaker1")]
        speaker_colors = {"speaker1": "#FFFFFF"}

        # Should not raise any exception
        validate_subtitle_parameters(subtitles, speaker_colors)

    def test_invalid_subtitles_type(self):
        """Test validation rejects non-list subtitles."""
        with self.assertRaises(TypeError):
            validate_subtitle_parameters("invalid", {})

    def test_none_speaker_colors(self):
        """Test validation rejects None speaker_colors."""
        with self.assertRaises(ValueError):
            validate_subtitle_parameters([], None)

    def test_invalid_speaker_colors_type(self):
        """Test validation rejects non-dict speaker_colors."""
        with self.assertRaises(TypeError):
            validate_subtitle_parameters([], "invalid")

    def test_invalid_subtitle_format(self):
        """Test validation catches unsupported subtitle formats."""
        invalid_subtitles = [(1, 2)]  # Only 2 elements, should be 4 or 5

        with self.assertRaises(ValueError):
            validate_subtitle_parameters(invalid_subtitles, {})


class TestApiKeyValidation(unittest.TestCase):
    """Test API key validation."""

    @patch.dict(os.environ, {'ASSEMBLYAI_API_KEY': 'test_key'}, clear=False)
    def test_assemblyai_key_available(self):
        """Test validation recognizes AssemblyAI key."""
        assemblyai_available, deepgram_available = validate_api_keys()
        self.assertTrue(assemblyai_available)

    @patch.dict(os.environ, {'DEEPGRAM_API_KEY': 'test_key'}, clear=False)
    def test_deepgram_key_available(self):
        """Test validation recognizes Deepgram key."""
        assemblyai_available, deepgram_available = validate_api_keys()
        self.assertTrue(deepgram_available)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_api_keys_configured(self):
        """Test validation fails when no API keys are configured."""
        with self.assertRaises(ValueError) as context:
            validate_api_keys()

        self.assertIn("No transcription API keys configured", str(context.exception))


class TestAudioFileValidation(unittest.TestCase):
    """Test audio file validation."""

    def test_empty_path_validation(self):
        """Test validation rejects empty file path."""
        with self.assertRaises(ValueError):
            validate_audio_file("")

    def test_none_path_validation(self):
        """Test validation rejects None file path."""
        with self.assertRaises(ValueError):
            validate_audio_file(None)

    @patch('os.path.exists')
    def test_nonexistent_file_validation(self, mock_exists):
        """Test validation rejects non-existent files."""
        mock_exists.return_value = False

        with self.assertRaises(ValueError):
            validate_audio_file("nonexistent.mp3")

    @patch('os.path.exists')
    @patch('os.path.isfile')
    def test_unsupported_format_validation(self, mock_isfile, mock_exists):
        """Test validation rejects unsupported file formats."""
        mock_exists.return_value = True
        mock_isfile.return_value = True

        with self.assertRaises(ValueError):
            validate_audio_file("file.txt")


if __name__ == '__main__':
    unittest.main()