import gradio as gr
import os
import signal
from functools import wraps
from utils import *

def timeout(seconds=300, error_message="Processing timed out after 5 minutes."):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result
        return wrapper
    return decorator

def split_text_intelligently(text, max_length=80):
    """Split text intelligently, ensuring no segment exceeds max_length."""
    segments = []
    remaining_text = text.strip()

    while remaining_text:
        if len(remaining_text) <= max_length:
            segments.append(remaining_text)
            break
        best_pos = -1

        for punct in ['.', '!', '?']:
            pos = remaining_text.find(punct, max_length//2)
            if pos != -1 and pos <= max_length:
                best_pos = pos
                break

        if best_pos == -1:
            for punct in [',', ';', ':']:
                pos = remaining_text.find(punct, max_length//2)
                if pos != -1 and pos <= max_length:
                    best_pos = pos
                    break

        if best_pos != -1 and best_pos <= max_length:
            segment = remaining_text[:best_pos+1].strip()
            segments.append(segment)
            remaining_text = remaining_text[best_pos+1:].strip()
        else:
            last_space = remaining_text.rfind(' ', 0, max_length)
            if last_space > 0:
                segment = remaining_text[:last_space].strip()
                segments.append(segment)
                remaining_text = remaining_text[last_space:].strip()
            else:
                segment = remaining_text[:max_length].strip()
                segments.append(segment)
                remaining_text = remaining_text[max_length:].strip()

    final_segments = []
    for seg in segments:
        while len(seg) > max_length:
            if len(seg) <= max_length:
                final_segments.append(seg)
                break
            best_pos = -1
            for punct in ['.', '!', '?', ',', ';', ':']:
                pos = seg.find(punct, max_length//2)
                if pos != -1 and pos <= max_length:
                    best_pos = pos
                    break
            if best_pos != -1 and best_pos <= max_length:
                final_segments.append(seg[:best_pos+1].strip())
                seg = seg[best_pos+1:].strip()
            else:
                last_space = seg.rfind(' ', 0, max_length)
                if last_space > 0:
                    final_segments.append(seg[:last_space].strip())
                    seg = seg[last_space:].strip()
                else:
                    final_segments.append(seg[:max_length].strip())
                    seg = seg[max_length:].strip()
        final_segments.append(seg)

    return final_segments

@timeout(seconds=300)
def process_uploaded_video_multilingual(
    video_file,
    target_language,
    diarize,
    font_size=24,
    background_style="None",
    alignment="Bottom Center",
    text_color="#FFFFFF",
    font_name="Liberation Sans",
    progress=gr.Progress()
):
    try:
        print("=== Starting video processing ===")
        video_path = video_file.name

        cleanup_files()
        progress(0.1, desc="Extracting audio from video...")
        audio_path = extract_audio_from_video(video_path)

        progress(0.2, desc="Transcribing audio with segment granularity...")
        transcription = transcribe_audio(audio_path, granularity="segment", diarize=diarize)

        progress(0.3, desc="Generating subtitles...")
        subtitles = []
        for segment in transcription.get("segments", []):
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]
            speaker = segment.get("speaker_id", "speaker_null")
            subtitles.append((start, end, text, speaker))

        # Translate subtitles first
        progress(0.4, desc="Translating subtitles...")
        segments = [Segment(id=idx, content=text) for idx, (_, _, text, _) in enumerate(subtitles)]
        translated_segments = translate(segments, target_language)

        final_subtitles = []
        for (start, end, _, speaker), translated in zip(subtitles, translated_segments["segments"]):
            translated_text = translated["content"]
            duration = end - start

            if len(translated_text) > 80:
                text_segments = split_text_intelligently(translated_text, 80)

                char_duration = duration / len(translated_text) if len(translated_text) > 0 else 0
                current_pos = 0

                for seg_text in text_segments:
                    seg_start = start + (current_pos * char_duration)
                    seg_end = start + ((current_pos + len(seg_text)) * char_duration)
                    final_subtitles.append((seg_start, seg_end, seg_text, speaker))
                    current_pos += len(seg_text)
            else:
                final_subtitles.append((start, end, translated_text, speaker))

        for i, (start, end, text, speaker) in enumerate(final_subtitles):
            if len(text) > 80:
                print(f"Warning: Subtitle {i} is {len(text)} characters long: '{text[:50]}...'")
                text_segments = split_text_intelligently(text, 80)
                char_duration = (end - start) / len(text) if len(text) > 0 else 0
                current_pos = 0
                new_subtitles = []
                for seg_text in text_segments:
                    seg_start = start + (current_pos * char_duration)
                    seg_end = start + ((current_pos + len(seg_text)) * char_duration)
                    new_subtitles.append((seg_start, seg_end, seg_text, speaker))
                    current_pos += len(seg_text)
                final_subtitles[i:i+1] = new_subtitles

        print(f"Generated {len(final_subtitles)} subtitle segments after splitting")
        for i, (_, _, text, _) in enumerate(final_subtitles):
            print(f"Subtitle {i}: {len(text)} chars - '{text[:50]}...'")

        unique_speakers = []
        seen = set()
        for _, _, _, speaker in final_subtitles:
            if speaker not in seen:
                seen.add(speaker)
                unique_speakers.append(speaker)

        default_colors = [
            "#00FF00",  # Lime
            "#FF00FF",  # Magenta
            "#00FFFF",  # Cyan
            "#FF0000",  # Red
            "#FFFF00",  # Yellow
            "#0000FF",  # Blue
            "#FF8000",  # Orange
            "#8000FF",  # Purple
            "#00FF80",  # Spring Green
            "#FF0080",  # Pink
            "#80FF00",  # Chartreuse
            "#0080FF",  # Azure
        ]
        speaker_colors = {}
        for i, speaker in enumerate(unique_speakers):
            speaker_colors[speaker] = default_colors[i % len(default_colors)]
        speaker_colors["speaker_null"] = text_color

        if not diarize:
            first_speaker = next(iter(unique_speakers)) if unique_speakers else "speaker_null"
            speaker_colors[first_speaker] = text_color

        progress(0.5, desc="Generating overlay...")
        processed_video = overlay_subtitles(
            video_path,
            audio_path,
            final_subtitles,
            font_size,
            background_style,
            alignment,
            text_color,
            speaker_colors,
            text_color,
            font_name,
            progress=progress,
            add_logo=True
        )

        raw_subtitles_html = generate_raw_subtitles_html(final_subtitles, speaker_colors)

        progress(1.0, desc="Done.")
        return processed_video, None, gr.HTML(visible=True, value=raw_subtitles_html)

    except TimeoutError as e:
        cleanup_files()
        progress(0, desc=str(e))
        return None, str(e), gr.HTML(visible=False)
    except ValueError as e:
        cleanup_files()
        progress(0, desc=str(e))
        return None, str(e), gr.HTML(visible=False)
    except Exception as e:
        import traceback
        print(f"\nERROR: {str(e)}")
        traceback.print_exc()
        cleanup_files()
        return None, str(e), gr.HTML(visible=False)

def multilingual_tab():
    with gr.TabItem("Multilingual Subtitles", elem_classes="gradio-tabitem"):
        gr.Markdown("## Multilingual Subtitles", elem_classes="gradio-markdown")
        gr.Markdown(
            "Upload a video to generate a version with translated subtitles (segment-level granularity).",
            elem_classes="gradio-markdown"
        )

        with gr.Row():
            with gr.Column(scale=1, elem_classes="input-column"):
                video_input = gr.File(
                    label="Upload Video",
                    type="filepath",
                    file_types=[".mp4", ".mov", ".avi"],
                    elem_classes="gradio-file"
                )
                target_language_dropdown = gr.Dropdown(
                    label="Target Language",
                    choices=[
                        "English", "French", "Spanish", "German", "Italian",
                        "Portuguese", "Dutch", "Russian", "Chinese", "Japanese",
                        "Rōmaji (Romanized Japanese)"
                    ],
                    value="English",
                    elem_classes="gradio-dropdown"
                )
                submit_btn = gr.Button("Generate Translated Video", variant="primary", elem_classes="gradio-button")

                with gr.Accordion("Settings", open=False, elem_classes="gradio-accordion"):
                    diarize_checkbox = gr.Checkbox(
                        label="Enable Speaker Diarization",
                        value=True,
                        info="Check to identify and color-code different speakers.",
                        elem_classes="gradio-checkbox"
                    )
                    with gr.Group():
                        text_color_picker = gr.ColorPicker(
                            label="Text Color",
                            value="#FFFFFF",
                            info="Color to use when diarization is disabled.",
                            elem_classes="gradio-colorpicker"
                        )

                    font_size_slider = gr.Slider(
                        label="Font Size",
                        minimum=12,
                        maximum=48,
                        step=2,
                        value=18,
                        elem_classes="gradio-slider"
                    )
                    background_style_radio = gr.Radio(
                        label="Background Style",
                        choices=["None", "Outline"],
                        value="None",
                        elem_classes="gradio-radio"
                    )
                    alignment_dropdown = gr.Dropdown(
                        label="Subtitle Alignment",
                        choices=[
                            "Top Left", "Top Center", "Top Right",
                            "Middle Left", "Middle Center", "Middle Right",
                            "Bottom Left", "Bottom Center", "Bottom Right"
                        ],
                        value="Bottom Center",
                        elem_classes="gradio-dropdown"
                    )
                    font_dropdown = gr.Dropdown(
                        label="Font",
                        choices=[
                            "Liberation Sans",
                            "Liberation Serif",
                            "Liberation Mono",
                            "DejaVu Sans",
                            "DejaVu Serif",
                            "DejaVu Sans Mono"
                        ],
                        value="Liberation Sans",
                        elem_classes="gradio-dropdown"
                    )

            with gr.Column(scale=2, elem_classes="output-column"):
                video_output = gr.Video(
                    label="Video with Translated Subtitles",
                    include_audio=True,
                    elem_classes="gradio-video"
                )
                error_output = gr.Textbox(
                    label="Error",
                    visible=False,
                    elem_classes="gradio-textbox"
                )
                with gr.Accordion("Translated Subtitles", open=False, elem_classes="gradio-accordion"):
                    raw_subtitles_output = gr.HTML(
                        label="Translated Subtitles",
                        visible=True
                    )

        with gr.Row(elem_classes="gradio-examples"):
            gr.Examples(
                examples=[
                    [
                        "examples/short_example.mp4",
                        "French",
                        False,
                        24,
                        "None",
                        "Bottom Center",
                        "#FFFFFF",
                        "Liberation Sans",
                    ],
                    [
                        "examples/talk_example.mp4",
                        "English",
                        True,
                        24,
                        "None",
                        "Bottom Center",
                        "#FFFFFF",
                        "Liberation Sans",
                    ],
                ],
                inputs=[
                    video_input,
                    target_language_dropdown,
                    diarize_checkbox,
                    font_size_slider,
                    background_style_radio,
                    alignment_dropdown,
                    text_color_picker,
                    font_dropdown,
                ],
                outputs=[
                    video_output,
                    error_output,
                    raw_subtitles_output
                ],
                fn=process_uploaded_video_multilingual,
                cache_examples=True,
                label="Try an Example",
            )

        submit_btn.click(
            fn=process_uploaded_video_multilingual,
            inputs=[
                video_input,
                target_language_dropdown,
                diarize_checkbox,
                font_size_slider,
                background_style_radio,
                alignment_dropdown,
                text_color_picker,
                font_dropdown,
            ],
            outputs=[
                video_output,
                error_output,
                raw_subtitles_output
            ],
            api_name="generate_translated_video"
        )
