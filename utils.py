import os
import subprocess
import re
import json
import time
import requests
from pysubs2 import SSAFile, SSAEvent
import Levenshtein
from pydantic import BaseModel
from mistralai import Mistral

# Load API key from environment variable
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("No Mistral API key found.")

client = Mistral(api_key=api_key)
model = "voxtral-mini-2602"
translation_model = "mistral-small-latest"

class Segment(BaseModel):
    id: int
    content: str

class TranslatedSegments(BaseModel):
    segments: list[Segment]

def cleanup_files():
    """Remove all temporary and output files."""
    try:
        files_to_clean = ["temp_video.mp4", "temp_audio.mp3", "subtitles.srt", "subtitles.ass", "output_video.mp4", "voxtral_output.mp4", "scribe_output.mp4", "gpt4o_output.mp4"]
        for file in files_to_clean:
            if os.path.exists(file):
                os.remove(file)
    except Exception as e:
        print(e)

def extract_audio_from_video(video_path):
    """Extract audio from video or return the audio path if the input is already an audio file."""
    audio_path = "temp_audio.mp3"
    audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.aac'}

    if os.path.splitext(video_path)[1].lower() in audio_extensions:
        return video_path

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return audio_path
    except Exception as e:
        print(e)
        cleanup_files()
        raise Exception(f"Failed to extract audio: {str(e)}")

def transcribe_audio(audio_path, granularity="word", diarize=False):
    """Transcribe audio using Mistral API with the selected granularity and optional diarization."""
    max_retries = 5
    delay_time = 2
    for i in range(max_retries):
        try:
            with open(audio_path, "rb") as audio_file:
                url = "https://api.mistral.ai/v1/audio/transcriptions"
                headers = {"x-api-key": api_key}
                files = {"file": ("audio.mp3", audio_file)}
                data = {"model": model}
                if granularity:
                    data["timestamp_granularities[]"] = granularity
                if diarize:
                    data["diarize"] = "true"
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                transcription_response = response.json()
                print(f"\n####\n\n- Granularity: {granularity}\n- Diarize: {diarize}\n- Response:\n", transcription_response, "\n\n####\n")
            return transcription_response
        except Exception as e:
            time.sleep(delay_time)
            print(e)
    raise Exception(f"Failed to transcribe audio: {str(e)}")

def split_segments_by_segment_boundaries(word_segments, segment_segments):
    if not word_segments or not segment_segments:
        return []
    word_segments = sorted(word_segments, key=lambda x: x["start"])
    segment_segments = sorted(segment_segments, key=lambda x: x["start"])
    segment_groups, current_segment_index, current_group = [], 0, []
    for word in word_segments:
        while (current_segment_index < len(segment_segments) and word["start"] >= segment_segments[current_segment_index]["end"]):
            if current_group:
                segment_groups.extend(split_group_by_punctuation_and_time(current_group))
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
        prev_word, current_word = group[i-1], group[i]
        if current_length + len(current_word["text"]) + 1 > 80:
            sub_groups.append(current_sub_group)
            current_sub_group = [current_word]
            current_length = len(current_word["text"])
        else:
            if prev_word["text"][-1] in {'.', ',', '!', '?'} or (current_word["start"] - prev_word["end"] > 0.3):
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
                    gap = group[j]["start"] - group[j-1]["end"]
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
            if last_word_text[-1] in {'.', '!', '?'}:
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

def match_words_to_speakers(segment_transcription, word_transcription):
    speaker_segments = segment_transcription.get("segments", [])
    word_segments = word_transcription.get("segments", [])
    first_speaker = speaker_segments[0].get("speaker_id") if speaker_segments else "speaker_null"

    for word in word_segments:
        word_start, word_end = word["start"], word["end"]

        if word_start == word_end:
            containing_segments = [
                seg for seg in speaker_segments
                if seg["start"] <= word_start <= seg["end"]
            ]
            if containing_segments:
                word["speaker_id"] = containing_segments[0].get("speaker_id")
                continue

        closest_segment = min(
            speaker_segments,
            key=lambda seg: min(
                abs(word_start - seg["start"]),
                abs(word_end - seg["end"])
            )
        )
        word["speaker_id"] = closest_segment.get("speaker_id")

    for i, word in enumerate(word_segments):
        if "speaker_id" not in word:
            prev_word = word_segments[i - 1] if i > 0 else None
            next_word = word_segments[i + 1] if i < len(word_segments) - 1 else None

            if prev_word and next_word and prev_word.get("speaker_id") == next_word.get("speaker_id"):
                word["speaker_id"] = prev_word["speaker_id"]
            elif prev_word or next_word:
                if prev_word and next_word:
                    closest_word = prev_word if (word_start - prev_word["end"]) < (next_word["start"] - word_end) else next_word
                    word["speaker_id"] = closest_word["speaker_id"]
                elif prev_word:
                    word["speaker_id"] = prev_word["speaker_id"]
                elif next_word:
                    word["speaker_id"] = next_word["speaker_id"]
            else:
                closest_segment = min(
                    speaker_segments,
                    key=lambda seg: min(
                        abs(word_start - seg["start"]),
                        abs(word_end - seg["end"])
                    )
                )
                word["speaker_id"] = closest_segment.get("speaker_id")

    for word in word_segments:
        if "speaker_id" not in word:
            word["speaker_id"] = first_speaker

    return word_segments

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip('#')
    bgr = hex_color[4:6] + hex_color[2:4] + hex_color[0:2]
    return f"&H{bgr}&"

def generate_subtitles(transcription_response, segment_transcription):
    subtitles, word_segments, segment_segments = [], transcription_response.get("segments", []), segment_transcription.get("segments", [])
    if not word_segments or not segment_segments:
        return subtitles
    segment_groups = split_segments_by_segment_boundaries(word_segments, segment_segments)
    first_speaker = segment_segments[0].get("speaker_id") if segment_segments else "speaker_null"
    for group in segment_groups:
        if not group:
            continue
        start, end, text = group[0]["start"], group[-1]["end"], " ".join([seg["text"] for seg in group])
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
    alignment="Bottom Center"
):
    sub = SSAFile()
    style = sub.styles["Default"]
    style.fontname = font_name
    style.fontsize = font_size
    style.primarycolor = int(text_color.lstrip('#'), 16)
    style.outlinecolor = 0x000000
    style.bold = False
    style.italic = False

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
    style.alignment = alignment_map.get(alignment, 2)

    bgr_default = hex_to_bgr(text_color)
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
                line.end = int(word_segments[j + 1]["start"] * 1000) if j < len(word_segments) - 1 else int(word_seg["end"] * 1000)
                line.style = "Default"
                ass_text = ""
                for k, w in enumerate(word_segments):
                    speaker_id = w.get("speaker_id", first_speaker)
                    bgr_highlight = hex_to_bgr(speaker_colors.get(speaker_id, speaker_colors.get(first_speaker, text_color)))
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
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    padding=10
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
        ass_path = "subtitles.ass"
        create_ass_file(subtitles, ass_path, font_size, text_color, speaker_colors, incoming_color, font_name, alignment)

        if os.path.exists(output_path):
            os.remove(output_path)
            
        total_duration = get_video_duration(video_path)
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", "-strict", "experimental",
            output_path
        ]
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        stderr_output = []
        for line in process.stderr:
            stderr_output.append(line)
            time_match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
            if time_match:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress(0.5 + (0.5 * (current_time / total_duration)), desc=f"Overlay creation...")
        process.wait()
        if process.returncode != 0:
            raise Exception(f"FFmpeg failed to overlay subtitles. Error: {''.join(stderr_output)}")

        return output_path
    except Exception as e:
        print(e)
        raise Exception(f"Failed to overlay subtitles: {str(e)}")


def generate_raw_subtitles_html(subtitles, speaker_colors, show_timestamps=True):
    html = "<div style='white-space: pre-wrap; font-size: 16px; line-height: 1.2; color: #E0E0E0; background: #121212; padding: 10px; border-radius: 8px;'>"

    has_word_granularity = len(subtitles) > 0 and len(subtitles[0]) == 5

    if show_timestamps:
        for sub in subtitles:
            if has_word_granularity:
                start, end, text, word_segments, speaker = sub
            else:
                start, end, text, speaker = sub
                word_segments = None

            start_time = f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{start % 60:06.3f}".replace('.', ',')
            end_time = f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{end % 60:06.3f}".replace('.', ',')
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

            current_speaker = word_segments[0].get("speaker_id", speaker) if word_segments else speaker
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
    print(segments)
    str_segments = "\n".join([f"{seg["id"]}: {seg["content"]}" for id, seg in segments])
    print(str_segments)
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
                            "You must answer with the following format: {\"segments\": [{\"id\": int, \"content\": str}, ...]}"
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
            
            translated_segments = json.loads(chat_response.choices[0].message.content)
            print(translated_segments)

            assert len(translated_segments["segments"]) == input_length, (
                f"Mismatch in segment count: input={input_length}, output={len(translated_segments['segments'])}"
            )

            return translated_segments

        except Exception as e:
            print(e)
            if attempt == max_retries - 1:
                raise Exception(f"Failed to translate after {max_retries} attempts. Error: {str(e)}")
            time.sleep(retry_delay)
