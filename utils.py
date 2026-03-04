import os
import subprocess
import re
import json
import time
from pysubs2 import SSAFile, SSAEvent, Color
import Levenshtein
from pydantic import BaseModel
from mistralai import Mistral
from mistralai.models import File
import assemblyai as aai
from deepgram import DeepgramClient
from dotenv import load_dotenv

import httpx

# Import validation components and type definitions
from typing import List, Dict, Tuple, Optional, Union, Any
from validation.transcription_validator import validate_transcription_response, validate_subtitle_parameters
from models.subtitles import (
    SubtitleTuple, SpeakerColors, TranscriptionResponse,
    SubtitleSettings, ValidationResult, ProcessingResult
)

# Load environment variables from .env file
load_dotenv()

# Load API keys from environment variables
mistral_api_key = os.getenv("MISTRAL_API_KEY")
if not mistral_api_key:
    print("Warning: No Mistral API key found. Translation will not work.")

# Initialize Mistral for translation only
if mistral_api_key:
    # Initialize Mistral with a custom HTTP client to avoid SSL issues on some systems (like Python 3.14 + HTTP/2)
    http_client = httpx.Client(http2=False)
    client = Mistral(api_key=mistral_api_key, client=http_client)
else:
    client = None

translation_model = "mistral-small-latest"

# AssemblyAI configuration
assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
if assemblyai_api_key:
    aai.settings.api_key = assemblyai_api_key

# Deepgram configuration
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
if deepgram_api_key:
    deepgram_client = DeepgramClient(api_key=deepgram_api_key)
else:
    deepgram_client = None
    print("Warning: No Deepgram API key found. Deepgram transcription will not work.")


class Segment(BaseModel):
    id: int
    content: str


class TranslatedSegments(BaseModel):
    segments: list[Segment]


TEMP_DIR = os.getenv("TEMP_DIR", ".")


def cleanup_files():
    """Remove all temporary and output files."""
    try:
        files_to_clean = [
            os.path.join(TEMP_DIR, f)
            for f in [
                "temp_video.mp4",
                "temp_audio.mp3",
                "subtitles.srt",
                "subtitles.ass",
                "output_video.mp4",
                "voxtral_output.mp4",
                "scribe_output.mp4",
                "gpt4o_output.mp4",
            ]
        ]
        for file in files_to_clean:
            if os.path.exists(file):
                os.remove(file)
    except Exception as e:
        print(e)


def extract_audio_from_video(video_path):
    """Extract audio from video or return the audio path if the input is already an audio file."""
    audio_path = os.path.join(TEMP_DIR, "temp_audio.mp3")
    audio_extensions = {".mp3", ".wav", ".ogg", ".flac", ".aac"}

    if os.path.splitext(video_path)[1].lower() in audio_extensions:
        return video_path

    try:
        # Use absolute path for FFmpeg output
        abs_audio_path = os.path.abspath(audio_path)

        # 1. Detect if audio stream exists
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            video_path,
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        has_audio = "audio" in probe_result.stdout.lower()

        if has_audio:
            # Normal extraction
            ffmpeg_cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                abs_audio_path,
            ]
        else:
            # Video has no audio stream; generate a silent audio track
            duration = get_video_duration(video_path)
            print(f"No audio stream detected. Generating {duration}s of silence.")
            ffmpeg_cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=mono:sample_rate=44100",
                "-t",
                str(duration),
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                abs_audio_path,
            ]

        subprocess.run(
            ffmpeg_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error (Extraction): {e.stderr}")
        cleanup_files()
        raise Exception(f"Failed to extract audio: {e.stderr}")
    except Exception as e:
        print(f"General Error (Extraction): {str(e)}")
        cleanup_files()
        raise Exception(f"Failed to extract audio: {str(e)}")


def transcribe_audio_deepgram(audio_path, diarize=False, language_code=None):
    """Transcribe audio using Deepgram SDK with optional diarization."""
    if not deepgram_client:
        raise ValueError("No Deepgram API key found. Set DEEPGRAM_API_KEY environment variable.")
    
    max_retries = 5
    delay_time = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            with open(audio_path, "rb") as file:
                buffer_data = file.read()

            payload = {
                "buffer": buffer_data,
            }

            options = {
                "model": "nova-2",
                "smart_format": True,
                "diarize": diarize,
                "language": language_code,
                "utterances": True,
                "paragraphs": True,
            }

            # Using v1 rest client with dict-based options for maximum compatibility
            response = deepgram_client.listen.v1.rest.transcribe_file(payload, options)
            
            # Extract results safely using getattr where applicable
            results = getattr(response, "results", response.get("results") if isinstance(response, dict) else None)
            channels = getattr(results, "channels", None)
            channel = channels[0] if channels else None
            alternatives = getattr(channel, "alternatives", None)
            alternative = alternatives[0] if alternatives else None
            
            # Words with timestamps
            words_data = []
            words = getattr(alternative, "words", [])
            if words:
                for word in words:
                    words_data.append({
                        "text": getattr(word, "word", ""),
                        "start": getattr(word, "start", 0),
                        "end": getattr(word, "end", 0),
                        "confidence": getattr(word, "confidence", 1.0),
                        "speaker_id": f"speaker_{getattr(word, 'speaker', 0)}",
                    })
            
            # Segments/utterances with speaker info
            segments_data = []
            utterances = getattr(results, "utterances", [])
            if utterances:
                for i, utt in enumerate(utterances):
                    segments_data.append({
                        "id": i,
                        "text": getattr(utt, "transcript", ""),
                        "start": getattr(utt, "start", 0),
                        "end": getattr(utt, "end", 0),
                        "speaker": f"speaker_{getattr(utt, 'speaker', 0)}",
                        "confidence": getattr(utt, "confidence", 1.0),
                    })
            else:
                # Fallback if no utterances but we have text
                transcript = getattr(alternative, "transcript", "")
                segments_data.append({
                    "id": 0,
                    "text": transcript or "",
                    "start": 0,
                    "end": words_data[-1]["end"] if words_data else 0,
                    "speaker": "speaker_0",
                    "confidence": 1.0,
                })
            
            transcription_response = {
                "text": getattr(alternative, "transcript", ""),
                "words": words_data,
                "segments": segments_data,
            }
            
            return transcription_response
            
        except Exception as e:
            last_error = e
            time.sleep(delay_time)
    
    raise Exception(
        f"Failed to transcribe audio with Deepgram after {max_retries} attempts: {str(last_error)}"
    )


def transcribe_audio_assemblyai(audio_path, diarize=False, language_code=None):
    """Transcribe audio using AssemblyAI SDK with optional diarization."""
    if not assemblyai_api_key:
        raise ValueError("No AssemblyAI API key found. Set ASSEMBLYAI_API_KEY environment variable.")
    
    max_retries = 5
    delay_time = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            config = aai.TranscriptionConfig(
                speaker_labels=diarize,
                language_code=language_code,
                punctuate=True,
                format_text=True,
            )
            
            transcriber = aai.Transcriber(config=config)
            transcript = transcriber.transcribe(audio_path)
            
            # Words with timestamps (convert ms to seconds)
            words_data = []
            if transcript.words:
                for word in transcript.words:
                    words_data.append({
                        "text": word.text,
                        "start": word.start / 1000.0,
                        "end": word.end / 1000.0,
                        "confidence": getattr(word, "confidence", 1.0),
                        "speaker_id": getattr(word, "speaker", "speaker_null"),
                    })
            
            # Segments/utterances with speaker info (convert ms to seconds)
            segments_data = []
            if transcript.utterances:
                for utt in transcript.utterances:
                    segments_data.append({
                        "text": utt.text,
                        "start": utt.start / 1000.0,
                        "end": utt.end / 1000.0,
                        "speaker": getattr(utt, "speaker", "speaker_null"),
                        "confidence": getattr(utt, "confidence", 1.0),
                    })
            else:
                segments_data.append({
                    "text": transcript.text or "",
                    "start": 0,
                    "end": words_data[-1]["end"] if words_data else 0,
                    "speaker": "speaker_null",
                    "confidence": 1.0,
                })
            
            transcription_response = {
                "text": transcript.text or "",
                "words": words_data,
                "segments": segments_data,
            }
            
            return transcription_response
            
        except Exception as e:
            last_error = e
            time.sleep(delay_time)
    
    raise Exception(
        f"Failed to transcribe audio with AssemblyAI after {max_retries} attempts: {str(last_error)}"
    )


def transcribe_audio_unified(
    audio_path: str,
    diarize: bool = False,
    language_code: Optional[str] = None
) -> TranscriptionResponse:
    """Unified transcription function with validation and proper error handling."""
    errors = []

    # Try AssemblyAI first
    if assemblyai_api_key:
        try:
            result = transcribe_audio_assemblyai(audio_path, diarize=diarize, language_code=language_code)
            validated_result = validate_transcription_response(result, "AssemblyAI")

            if diarize and result.get("segments"):
                has_speakers = any(seg.get("speaker") != "speaker_null" for seg in result["segments"])
                if has_speakers:
                    print("Using AssemblyAI for transcription (speaker diarization enabled)")
                    return validated_result
            print("Using AssemblyAI for transcription")
            return validated_result
        except Exception as e:
            error_msg = f"AssemblyAI failed: {str(e)}"
            errors.append(error_msg)
            print(error_msg)
            print("Falling back to Deepgram...")
    else:
        errors.append("AssemblyAI API key not configured")

    # Fallback to Deepgram
    if deepgram_api_key:
        try:
            result = transcribe_audio_deepgram(audio_path, diarize=diarize, language_code=language_code)
            validated_result = validate_transcription_response(result, "Deepgram")
            print("Using Deepgram for transcription")
            return validated_result
        except Exception as e:
            error_msg = f"Deepgram failed: {str(e)}"
            errors.append(error_msg)
            print(error_msg)
    else:
        errors.append("Deepgram API key not configured")

    # Both services failed
    all_errors = "; ".join(errors)
    raise ValueError(f"All transcription services failed: {all_errors}")


def split_segments_by_segment_boundaries(word_segments, segment_segments):
    if not word_segments or not segment_segments:
        return []
    word_segments = sorted(word_segments, key=lambda x: x["start"])
    segment_segments = sorted(segment_segments, key=lambda x: x["start"])
    segment_groups, current_segment_index, current_group = [], 0, []
    for word in word_segments:
        while (
            current_segment_index < len(segment_segments)
            and word["start"] >= segment_segments[current_segment_index]["end"]
        ):
            if current_group:
                segment_groups.extend(
                    split_group_by_punctuation_and_time(current_group)
                )
                current_group = []
            current_segment_index += 1
            if current_segment_index >= len(segment_segments):
                break
        if current_segment_index < len(segment_segments):
            current_group.append(word)
    if current_group:
        segment_groups.extend(split_group_by_punctuation_and_time(current_group))
    return concatenate_short_segments(segment_groups)


def split_group_by_punctuation_and_time(group):
    if not group:
        return []

    sub_groups = []
    current_sub_group = [group[0]]
    current_length = len(group[0]["text"])

    for i in range(1, len(group)):
        prev_word, current_word = group[i - 1], group[i]
        if current_length + len(current_word["text"]) + 1 > 80:
            sub_groups.append(current_sub_group)
            current_sub_group = [current_word]
            current_length = len(current_word["text"])
        else:
            if prev_word["text"][-1] in {".", ",", "!", "?"} or (
                current_word["start"] - prev_word["end"] > 0.3
            ):
                sub_groups.append(current_sub_group)
                current_sub_group = [current_word]
                current_length = len(current_word["text"])
            else:
                current_sub_group.append(current_word)
                current_length += len(current_word["text"]) + 1

    if current_sub_group:
        sub_groups.append(current_sub_group)

    final_groups = []
    for group in sub_groups:
        while True:
            group_length = sum(len(w["text"]) + 1 for w in group) - 1
            if group_length <= 80:
                final_groups.append(group)
                break
            else:
                max_gap_index = 0
                max_gap = 0
                for j in range(1, len(group)):
                    gap = group[j]["start"] - group[j - 1]["end"]
                    if gap > max_gap:
                        max_gap = gap
                        max_gap_index = j
                if max_gap_index > 0:
                    final_groups.append(group[:max_gap_index])
                    group = group[max_gap_index:]
                else:
                    split_index = len(group) // 2
                    final_groups.append(group[:split_index])
                    group = group[split_index:]

    return final_groups


def concatenate_short_segments(groups):
    concatenated_groups, current_group = [], []
    for group in groups:
        if not current_group:
            current_group = group
        else:
            last_word_text = current_group[-1]["text"]
            if last_word_text[-1] in {".", "!", "?"}:
                concatenated_groups.append(current_group)
                current_group = group
            else:
                combined_text = " ".join([w["text"] for w in current_group + group])
                time_diff = group[0]["start"] - current_group[-1]["end"]
                if len(combined_text) <= 80 and time_diff <= 0.5:
                    current_group.extend(group)
                else:
                    concatenated_groups.append(current_group)
                    current_group = group
    if current_group:
        concatenated_groups.append(current_group)
    return concatenated_groups


def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip("#")
    bgr = hex_color[4:6] + hex_color[2:4] + hex_color[0:2]
    return f"&H{bgr}&"


def hex_to_pysubs2_color(hex_color):
    """Convert hex color (#RRGGBB) to pysubs2.Color (R, G, B)."""
    if not hex_color:
        return Color(255, 255, 255, 0)
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return Color(r, g, b, 0)
    return Color(255, 255, 255, 0)


def generate_subtitles(transcription_response, segment_transcription):
    # Try to get words first, then fall back to segments
    word_segments = transcription_response.get("words")
    if not word_segments:
        word_segments = transcription_response.get("segments", [])
    
    segment_segments = segment_transcription.get("segments", [])
    
    subtitles = []
    if not word_segments or not segment_segments:
        return subtitles
    segment_groups = split_segments_by_segment_boundaries(
        word_segments, segment_segments
    )
    first_speaker = (
        segment_segments[0].get("speaker_id") if segment_segments else "speaker_null"
    )
    for group in segment_groups:
        if not group:
            continue
        start, end, text = (
            group[0]["start"],
            group[-1]["end"],
            " ".join([seg["text"] for seg in group]),
        )
        speaker = group[0].get("speaker_id", first_speaker)
        subtitles.append((start, end, text, group, speaker))
    return subtitles


def create_ass_file(
    subtitles,
    srt_path="subtitles.ass",
    font_size=24,
    text_color="#FFFFFF",
    speaker_colors=None,
    incoming_color="#808080",
    font_name="Liberation Sans",
    alignment="Bottom Center",
    # Advanced styling from slideshow tab
    primary_colour=None,
    secondary_colour=None,
    outline_colour=None,
    back_colour=None,
    bold=False,
    italic=False,
    border_style=1,
    margin_l=10,
    margin_r=10,
    margin_v=10,
    encoding=1,
    **kwargs
):
    sub = SSAFile()
    style = sub.styles["Default"]
    style.fontname = font_name
    style.fontsize = font_size
    
    # Use advanced colors if provided, otherwise fallback to text_color
    if primary_colour:
        style.primarycolor = hex_to_pysubs2_color(primary_colour)
    else:
        style.primarycolor = hex_to_pysubs2_color(text_color)
        
    if secondary_colour:
        style.secondarycolor = hex_to_pysubs2_color(secondary_colour)
    
    if outline_colour:
        style.outlinecolor = hex_to_pysubs2_color(outline_colour)
    else:
        style.outlinecolor = Color(0, 0, 0, 0) # Default black outline
        
    if back_colour:
        style.backcolor = hex_to_pysubs2_color(back_colour)
    
    style.bold = bold
    style.italic = italic
    style.borderstyle = border_style
    style.marginl = margin_l
    style.marginr = margin_r
    style.marginv = margin_v
    style.encoding = encoding

    alignment_map = {
        "Bottom Left": 1,
        "Bottom Center": 2,
        "Bottom Right": 3,
        "Middle Left": 4,
        "Middle Center": 5,
        "Middle Right": 6,
        "Top Left": 7,
        "Top Center": 8,
        "Top Right": 9,
    }
    
    if isinstance(alignment, str):
        style.alignment = alignment_map.get(alignment, 2)
    else:
        style.alignment = alignment

    bgr_default = hex_to_bgr(text_color if not primary_colour else primary_colour)
    bgr_incoming = hex_to_bgr(incoming_color)

    has_word_granularity = len(subtitles) > 0 and len(subtitles[0]) == 5

    if has_word_granularity:
        first_speaker = subtitles[0][4] if subtitles else "speaker_null"
    else:
        first_speaker = subtitles[0][3] if subtitles else "speaker_null"

    total_subtitles = len(subtitles)
    for i, subtitle in enumerate(subtitles, start=1):
        if has_word_granularity:
            start, end, text, word_segments, speaker = subtitle
        else:
            start, end, text, speaker = subtitle
            word_segments = None

        if word_segments and len(word_segments) > 0:
            # Word-level highlighting
            for j, word_seg in enumerate(word_segments):
                line = SSAEvent()
                line.start = int(word_seg["start"] * 1000)
                line.end = (
                    int(word_segments[j + 1]["start"] * 1000)
                    if j < len(word_segments) - 1
                    else int(word_seg["end"] * 1000)
                )
                line.style = "Default"
                ass_text = ""
                for k, w in enumerate(word_segments):
                    speaker_id = w.get("speaker_id", first_speaker)
                    bgr_highlight = hex_to_bgr(
                        speaker_colors.get(
                            speaker_id, speaker_colors.get(first_speaker, text_color)
                        )
                    )
                    if k == j:
                        ass_text += f"{{\\c{bgr_highlight}}}{w['text']} "
                    else:
                        ass_text += f"{{\\c{bgr_default if k < j else bgr_incoming}}}{w['text']} "
                line.text = ass_text.strip()
                sub.events.append(line)
        else:
            # Segment-level highlighting (entire subtitle at once)
            line = SSAEvent()
            line.start = int(start * 1000)
            line.end = int(end * 1000)
            line.style = "Default"
            # Use speaker color for the entire segment
            speaker_id = speaker if has_word_granularity else speaker
            bgr_highlight = hex_to_bgr(speaker_colors.get(speaker_id, text_color))
            line.text = f"{{\\c{bgr_highlight}}}{text}"
            sub.events.append(line)

    sub.save(srt_path)


def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return float(result.stdout.strip())


def overlay_subtitles(
    video_path,
    audio_path,
    subtitles,
    font_size=24,
    background_style="None",
    alignment="Bottom Center",
    text_color="#FFFFFF",
    speaker_colors=None,
    incoming_color="#808080",
    font_name="Liberation Sans",
    output_path="output_video.mp4",
    progress=None,
    add_logo=False,
    logo_path="videologo.png",
    logo_scale=0.5,
    padding=10,
    **kwargs
):
    """
    Overlays subtitles on the video, with an option to add a logo in the bottom right corner.

    Args:
        add_logo (bool): If True, adds the logo to the video.
        logo_path (str): Path to the logo image.
        logo_scale (float): Scale factor for the logo (default: 0.1).
        padding (int): Padding around the logo (default: 10).
    """
    try:
        ass_path = os.path.join(TEMP_DIR, "subtitles.ass")
        create_ass_file(
            subtitles,
            ass_path,
            font_size,
            text_color,
            speaker_colors,
            incoming_color,
            font_name,
            alignment,
            **kwargs
        )

        output_path = os.path.join(TEMP_DIR, "output_video.mp4")
        if os.path.exists(output_path):
            os.remove(output_path)

        total_duration = get_video_duration(video_path)
        abs_ass_path = os.path.abspath(ass_path)
        abs_output_path = os.path.abspath(output_path)

        # Determine video encoder based on hardware availability
        video_encoder = "libx264"
        compute_device = os.getenv("COMPUTE_DEVICE", "CPU")
        if compute_device == "CUDA":
            video_encoder = "h264_nvenc"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-vf",
            f"ass={abs_ass_path}",
            "-c:v",
            video_encoder,
            "-preset",
            "ultrafast",
            "-c:a",
            "copy",
            "-strict",
            "experimental",
            abs_output_path,
        ]

        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        stderr_output = []
        for line in process.stderr:
            stderr_output.append(line)
            time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
            if time_match:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress(
                    0.5 + (0.5 * (current_time / total_duration)),
                    desc=f"Overlay creation...",
                )
        process.wait()
        if process.returncode != 0:
            raise Exception(
                f"FFmpeg failed to overlay subtitles. Error: {''.join(stderr_output)}"
            )

        return output_path
    except Exception as e:
        print(e)
        raise Exception(f"Failed to overlay subtitles: {str(e)}")


def generate_raw_subtitles_html(
    subtitles: List[SubtitleTuple],
    speaker_colors: SpeakerColors,
    show_timestamps: bool = True
) -> str:
    """Generate HTML with defensive parameter checking"""
    validate_subtitle_parameters(subtitles, speaker_colors)

    html = "<div style='white-space: pre-wrap; font-size: 16px; line-height: 1.2; color: #E0E0E0; background: #121212; padding: 10px; border-radius: 8px;'>"

    has_word_granularity = len(subtitles) > 0 and len(subtitles[0]) == 5

    if show_timestamps:
        for sub in subtitles:
            if has_word_granularity:
                start, end, text, word_segments, speaker = sub
            else:
                start, end, text, speaker = sub
                word_segments = None

            start_time = f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{start % 60:06.3f}".replace(
                ".", ","
            )
            end_time = f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{end % 60:06.3f}".replace(
                ".", ","
            )
            html += f"<div style='margin-bottom: 8px;'><span style='color: #808080;'>{start_time} --> {end_time}</span> "

            if word_segments:
                current_speaker = None
                for word in word_segments:
                    word_speaker = word.get("speaker_id", speaker)
                    color = speaker_colors.get(word_speaker, "#FFFFFF")

                    if word_speaker != current_speaker and current_speaker is not None:
                        html += "</span>"
                    if word_speaker != current_speaker:
                        html += f"<span style='color: {color};'>"
                    current_speaker = word_speaker
                    html += f"{word['text']} "

                if word_segments:
                    html += "</span>"
            else:
                color = speaker_colors.get(speaker, "#FFFFFF")
                html += f"<span style='color: {color};'>{text}</span>"

            html += "</div>"
    else:
        prev_speaker = None
        for sub in subtitles:
            if has_word_granularity:
                _, _, _, word_segments, speaker = sub
            else:
                _, _, _, speaker = sub
                word_segments = None

            if not word_segments:
                continue

            current_speaker = (
                word_segments[0].get("speaker_id", speaker)
                if word_segments
                else speaker
            )
            color = speaker_colors.get(current_speaker, "#FFFFFF")

            if current_speaker != prev_speaker and prev_speaker is not None:
                html += "</span></div>"

            if current_speaker != prev_speaker:
                if prev_speaker is not None:
                    html += "</div>"
                html += f"<div style='margin-bottom: 4px;'><span style='color: {color};'><strong>{current_speaker}:</strong> "

            if word_segments:
                for word in word_segments:
                    html += f"{word['text']} "
            else:
                if has_word_granularity:
                    _, _, text, _, _ = sub
                else:
                    _, _, text, _ = sub
                html += f"{text} "

            prev_speaker = current_speaker

        if prev_speaker is not None:
            html += "</span></div>"

    html += "</div>"
    return html


def translate(segments, target_language):
    """
    Translates a list of segments into the target language using the Mistral API.
    Retries up to 5 times if the request fails.

    Args:
        segments: List of Segment objects to translate.
        target_language: The language code to translate into (e.g., "fr", "es", "de").

    Returns:
        dict: A dictionary containing the translated segments in the format {"segments": [{"id": int, "content": str}, ...]}
    """
    max_retries = 5
    retry_delay = 2  # seconds
    str_segments = "\n".join([f"{seg['id']}: {seg['content']}" for seg in segments])
    input_length = len(segments)

    for attempt in range(max_retries):
        try:
            chat_response = client.chat.parse(
                model=translation_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a segment translation system. "
                            "You must translate a list of segments into their translation in a target language. "
                            "The translation must keeo the exact same length of segments, and not modify the contents, provide only the accurate translation. "
                            'You must answer with the following format: {"segments": [{"id": int, "content": str}, ...]}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"# Segments to translate to {target_language}\n{str_segments}",
                    },
                ],
                response_format=TranslatedSegments,
                max_tokens=9192,
                temperature=0,
            )

            # The Mistral SDK's parse method returns a parsed object directly
            translated_segments = chat_response.choices[0].message.parsed

            # If for some reason it's None, fall back to content
            if translated_segments is None:
                translated_segments = json.loads(
                    chat_response.choices[0].message.content
                )

            # If it's a Pydantic model, convert to dict
            if hasattr(translated_segments, "model_dump"):
                translated_segments = translated_segments.model_dump()

            assert len(translated_segments["segments"]) == input_length, (
                f"Mismatch in segment count: input={input_length}, output={len(translated_segments['segments'])}"
            )

            return translated_segments

        except Exception as e:
            print(e)
            if attempt == max_retries - 1:
                raise Exception(
                    f"Failed to translate after {max_retries} attempts. Error: {str(e)}"
                )
            time.sleep(retry_delay)


# ============================================================================
# IMAGE SLIDESHOW FUNCTIONS
# ============================================================================

def validate_image_files(image_files):
    """Validate image formats, sizes, and convert to standard format"""
    try:
        from PIL import Image

        validated_images = []
        supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

        for image_file in image_files:
            if not image_file or not hasattr(image_file, 'name'):
                continue

            file_path = image_file.name

            # Check file extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in supported_formats:
                raise ValueError(f"Unsupported image format: {ext}. Supported: {', '.join(supported_formats)}")

            # Verify it's actually an image using python-magic (with fallback)
            try:
                import magic
                file_type = magic.from_file(file_path, mime=True)
                if not file_type.startswith('image/'):
                    raise ValueError(f"File {os.path.basename(file_path)} is not a valid image")
            except Exception as magic_error:
                # Fallback to PIL-only verification if magic isn't available
                print(f"Warning: python-magic not available ({magic_error}), using PIL-only validation")
                pass

            # Validate with PIL
            try:
                with Image.open(file_path) as img:
                    img.verify()
                    # Reopen for size check (verify closes the image)
                    with Image.open(file_path) as img:
                        width, height = img.size
                        if width < 100 or height < 100:
                            raise ValueError(f"Image {os.path.basename(file_path)} too small: {width}x{height}")
                        if width > 8000 or height > 8000:
                            raise ValueError(f"Image {os.path.basename(file_path)} too large: {width}x{height}")

                        validated_images.append({
                            'path': file_path,
                            'name': os.path.basename(file_path),
                            'size': (width, height),
                            'format': img.format
                        })
            except Exception as e:
                raise ValueError(f"Invalid image {os.path.basename(file_path)}: {str(e)}")

        if not validated_images:
            raise ValueError("No valid images found")

        return validated_images

    except ImportError as e:
        raise ValueError(f"Required image processing libraries not available: {e}")


def normalize_image_resolution(images, target_resolution="1920x1080", aspect_handling="letterbox"):
    """Standardize image resolution while maintaining aspect ratio"""
    from PIL import Image, ImageOps

    target_width, target_height = map(int, target_resolution.split('x'))
    normalized_images = []

    temp_dir = "temp_normalized_images"
    os.makedirs(temp_dir, exist_ok=True)

    for i, image_info in enumerate(images):
        try:
            with Image.open(image_info['path']) as img:
                # Convert to RGB if necessary (handles RGBA, etc.)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                if aspect_handling == "letterbox":
                    # Maintain aspect ratio, add black bars
                    img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
                    # Create black background
                    result = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                    # Center the image
                    x = (target_width - img.size[0]) // 2
                    y = (target_height - img.size[1]) // 2
                    result.paste(img, (x, y))

                elif aspect_handling == "crop":
                    # Crop to fit exact aspect ratio
                    result = ImageOps.fit(img, (target_width, target_height), Image.Resampling.LANCZOS)

                else:  # stretch
                    # Stretch to exact dimensions
                    result = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

                # Save normalized image
                output_path = os.path.join(temp_dir, f"normalized_{i:04d}.jpg")
                result.save(output_path, "JPEG", quality=95)

                normalized_images.append({
                    'path': output_path,
                    'original_name': image_info['name'],
                    'size': (target_width, target_height)
                })

        except Exception as e:
            raise ValueError(f"Failed to normalize image {image_info['name']}: {str(e)}")

    return normalized_images


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', audio_path
        ], capture_output=True, text=True, check=True)

        metadata = json.loads(result.stdout)
        duration = float(metadata['format']['duration'])
        return duration
    except Exception as e:
        raise ValueError(f"Failed to get audio duration: {str(e)}")


def calculate_auto_durations(images, audio_duration):
    """Auto-distribute audio duration across images intelligently"""
    num_images = len(images)
    if num_images == 0:
        return []

    # Base duration per image
    base_duration = audio_duration / num_images

    # Ensure minimum and maximum durations
    min_duration = 0.5  # 0.5 seconds minimum
    max_duration = min(audio_duration * 0.8, 30.0)  # 80% of total or 30 seconds max

    # Smart distribution: slightly longer for first and last images
    durations = []
    for i in range(num_images):
        if i == 0 or i == num_images - 1:
            # First and last images get slightly longer duration
            duration = min(base_duration * 1.2, max_duration)
        else:
            duration = base_duration

        duration = max(min_duration, min(duration, max_duration))
        durations.append(duration)

    # Normalize to exact audio duration
    total_duration = sum(durations)
    scale_factor = audio_duration / total_duration
    durations = [d * scale_factor for d in durations]

    # Ensure last image ends exactly with audio
    durations[-1] = audio_duration - sum(durations[:-1])

    return durations


def validate_manual_durations(durations, audio_duration, tolerance=0.1):
    """Validate manual durations against audio length"""
    if not durations:
        raise ValueError("No durations provided")

    total_duration = sum(durations)
    difference = abs(total_duration - audio_duration)

    if difference > tolerance:
        raise ValueError(
            f"Duration mismatch: images total {total_duration:.2f}s, "
            f"audio is {audio_duration:.2f}s (difference: {difference:.2f}s)"
        )

    # Check for reasonable individual durations
    for i, duration in enumerate(durations):
        if duration < 0.1:
            raise ValueError(f"Image {i+1} duration too short: {duration:.2f}s")
        if duration > 60.0:
            raise ValueError(f"Image {i+1} duration too long: {duration:.2f}s")

    return durations


def parse_csv_durations(csv_file, images):
    """Parse CSV file with image/duration mappings"""
    import csv

    if not csv_file:
        raise ValueError("No CSV file provided")

    durations = []
    expected_count = len(images)

    try:
        with open(csv_file.name, 'r', newline='') as file:
            reader = csv.DictReader(file)

            # Expected headers: image_name, duration OR image_index, duration
            required_headers = ['duration']
            if not any(header in reader.fieldnames for header in ['image_name', 'image_index']):
                raise ValueError("CSV must contain 'image_name' or 'image_index' column")
            if 'duration' not in reader.fieldnames:
                raise ValueError("CSV must contain 'duration' column")

            duration_map = {}
            for row in reader:
                try:
                    duration = float(row['duration'])
                    if 'image_index' in row:
                        idx = int(row['image_index'])
                        duration_map[idx] = duration
                    elif 'image_name' in row:
                        # Find matching image by name
                        image_name = row['image_name']
                        for i, img in enumerate(images):
                            if img['name'] == image_name:
                                duration_map[i] = duration
                                break
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Invalid CSV row: {row}. Error: {e}")

            # Build ordered duration list
            for i in range(expected_count):
                if i not in duration_map:
                    raise ValueError(f"No duration specified for image {i+1}")
                durations.append(duration_map[i])

        return durations

    except FileNotFoundError:
        raise ValueError("CSV file not found")
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {str(e)}")


def create_image_sequence_video(images, durations, audio_path, resolution="1920x1080"):
    """Generate MP4 using FFmpeg with image sequence and audio"""
    temp_dir = "temp_video_creation"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Create individual video segments for each image
        segment_files = []

        for i, (image_info, duration) in enumerate(zip(images, durations)):
            segment_file = os.path.join(temp_dir, f"segment_{i:04d}.mp4")

            # Create video segment from image with specific duration - use basic settings
            width, height = resolution.split('x')
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', image_info['path'],
                '-c:v', 'mpeg4',  # Use mpeg4 instead of libx264 for compatibility
                '-t', str(duration),
                '-pix_fmt', 'yuv420p',
                '-r', '24',  # 24 fps
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                '-q:v', '5',  # Good quality for mpeg4
                segment_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise ValueError(f"Failed to create segment {i}: {result.stderr}")

            segment_files.append(segment_file)

        # Create concat file for FFmpeg
        concat_file = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_file, 'w') as f:
            for segment_file in segment_files:
                f.write(f"file '{os.path.abspath(segment_file)}'\n")

        # Concatenate all segments
        video_only_file = os.path.join(temp_dir, "video_only.mp4")
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            video_only_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Failed to concatenate segments: {result.stderr}")

        # Add audio to video - use compatible audio codec
        final_video_file = os.path.join(temp_dir, "final_video_with_audio.mp4")
        cmd = [
            'ffmpeg', '-y',
            '-i', video_only_file,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'mp3',  # Use mp3 instead of aac for compatibility
            '-shortest',
            final_video_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Failed to add audio: {result.stderr}")

        return final_video_file

    except Exception as e:
        raise ValueError(f"Video creation failed: {str(e)}")


def create_timing_visualization(images, durations):
    """Generate timeline visualization for preview"""
    try:
        import plotly.graph_objects as go
        import plotly.express as px

        # Calculate cumulative times
        cumulative_times = [0]
        for duration in durations:
            cumulative_times.append(cumulative_times[-1] + duration)

        # Create timeline data
        timeline_data = []
        colors = px.colors.qualitative.Set3

        for i, (image_info, duration) in enumerate(zip(images, durations)):
            timeline_data.append({
                'Image': f"Image {i+1}",
                'Start': cumulative_times[i],
                'End': cumulative_times[i+1],
                'Duration': duration,
                'Name': image_info.get('original_name', image_info.get('name', f'Image {i+1}'))
            })

        # Create Gantt-style chart
        fig = go.Figure()

        for i, data in enumerate(timeline_data):
            fig.add_trace(go.Scatter(
                x=[data['Start'], data['End'], data['End'], data['Start'], data['Start']],
                y=[i, i, i+0.8, i+0.8, i],
                fill='toself',
                fillcolor=colors[i % len(colors)],
                line=dict(color=colors[i % len(colors)]),
                name=data['Name'],
                text=f"{data['Name']}<br>Duration: {data['Duration']:.2f}s",
                hovertemplate='%{text}<extra></extra>',
                showlegend=False
            ))

            # Add text labels
            fig.add_trace(go.Scatter(
                x=[(data['Start'] + data['End']) / 2],
                y=[i + 0.4],
                text=[f"{data['Duration']:.1f}s"],
                mode='text',
                textfont=dict(color='black', size=10),
                showlegend=False,
                hoverinfo='skip'
            ))

        # Update layout
        fig.update_layout(
            title="Image Display Timeline",
            xaxis_title="Time (seconds)",
            yaxis_title="Images",
            height=max(300, len(images) * 60),
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(len(images))),
                ticktext=[f"Image {i+1}" for i in range(len(images))],
                range=[-0.5, len(images) - 0.5]
            ),
            xaxis=dict(range=[0, cumulative_times[-1] * 1.05]),
            plot_bgcolor='white',
            showlegend=False
        )

        return fig

    except ImportError:
        return None  # Plotly not available
    except Exception as e:
        print(f"Failed to create visualization: {e}")
        return None


def generate_subtitles_for_slideshow(transcription_response, durations, images):
    """Generate subtitles with timing adjustment for slideshow"""
    try:
        # Validate transcription response
        if transcription_response is None:
            raise ValueError("Transcription response is None - transcription failed")

        # Get word-level transcription for precise timing
        words = []

        # 1. Try to get top-level words (AssemblyAI/Deepgram format)
        if isinstance(transcription_response, dict):
            words = transcription_response.get('words', [])
        elif hasattr(transcription_response, 'words'):
            words = transcription_response.words

        # 2. Fallback to segments if words list is empty (Mistral format or nested)
        if not words:
            if isinstance(transcription_response, dict):
                segments = transcription_response.get('segments', [])
            elif hasattr(transcription_response, 'segments'):
                segments = transcription_response.segments
            else:
                segments = []

            # Extract words from segments
            for segment in segments:
                if isinstance(segment, dict):
                    seg_words = segment.get('words', [])
                elif hasattr(segment, 'words'):
                    seg_words = segment.words
                else:
                    seg_words = []
                
                if seg_words:
                    words.extend(seg_words)
                elif isinstance(segment, dict) and 'start' in segment and 'end' in segment:
                    # If the segment itself looks like a word (Mistral word granularity)
                    words.append(segment)
                elif hasattr(segment, 'start') and hasattr(segment, 'end'):
                    words.append(segment)

        if not words:
            raise ValueError("No word-level transcription available")

        # Map words to image timing
        total_audio_duration = sum(durations)
        cumulative_times = [0]
        for duration in durations:
            cumulative_times.append(cumulative_times[-1] + duration)

        # Adjust word timings to match slideshow timing
        subtitle_entries = []
        current_image_idx = 0
        current_line_text = []
        current_line_words = []
        current_line_start = None

        for word in words:
            word_start = float(word.get('start') if isinstance(word, dict) else getattr(word, 'start', 0))
            word_end = float(word.get('end') if isinstance(word, dict) else getattr(word, 'end', 0))
            word_text = word.get('text') if isinstance(word, dict) else getattr(word, 'text', '')
            
            # If word_text is empty, try 'word' key for backward compatibility
            if not word_text:
                word_text = word.get('word') if isinstance(word, dict) else getattr(word, 'word', '')

            # Find which image this word should appear on
            while (current_image_idx < len(cumulative_times) - 1 and
                   word_start >= cumulative_times[current_image_idx + 1]):
                current_image_idx += 1

            # Adjust timing to image boundaries
            image_start = cumulative_times[current_image_idx]
            image_end = cumulative_times[current_image_idx + 1]

            # Scale word timing within image duration
            if current_image_idx < len(durations):
                original_image_duration = image_end - image_start
                word_progress = (word_start - image_start) / original_image_duration if original_image_duration > 0 else 0
                adjusted_start = image_start + (word_progress * durations[current_image_idx])
                adjusted_end = min(adjusted_start + (word_end - word_start), image_end)
            else:
                adjusted_start = word_start
                adjusted_end = word_end

            # Build subtitle lines
            if current_line_start is None:
                current_line_start = adjusted_start

            current_line_text.append(word_text)
            
            speaker_id = word.get('speaker_id', 'Speaker 1') if isinstance(word, dict) else getattr(word, 'speaker_id', 'Speaker 1')
            
            current_line_words.append({
                'text': word_text,
                'start': adjusted_start,
                'end': adjusted_end,
                'speaker_id': speaker_id
            })

            # Create subtitle line when reaching punctuation or line length limit
            line_text = ' '.join(current_line_text)
            if (len(line_text) > 80 or
                word_text.rstrip().endswith(('.', '!', '?', ',')) or
                adjusted_end - current_line_start > 4.0):  # Max 4 seconds per line

                subtitle_entries.append((
                    current_line_start,
                    adjusted_end,
                    line_text.strip(),
                    current_line_words,
                    speaker_id
                ))

                current_line_text = []
                current_line_words = []
                current_line_start = None

        # Add remaining words if any
        if current_line_text:
            line_text = ' '.join(current_line_text)
            last_speaker = current_line_words[-1]['speaker_id'] if current_line_words else 'Speaker 1'
            subtitle_entries.append((
                current_line_start or 0,
                total_audio_duration,
                line_text.strip(),
                current_line_words,
                last_speaker
            ))

        return subtitle_entries

    except Exception as e:
        raise ValueError(f"Failed to generate subtitles for slideshow: {str(e)}")
