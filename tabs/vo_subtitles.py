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
    
@timeout(seconds=300)
def process_uploaded_video(
    video_file,
    diarize,
    font_size=24,
    background_style="None",
    alignment="Bottom Center",
    text_color="#FFFFFF",
    highlight_color="#FFA500",
    incoming_color="#808080",
    font_name="Liberation Sans",
    progress=gr.Progress()
):
    try:
        video_path = video_file.name

        cleanup_files()
        progress(0.1, desc="Extracting audio from video...")
        audio_path = extract_audio_from_video(video_path)

        progress(0.2, desc="Transcribing audio with segment granularity for diarization...")
        segment_transcription = transcribe_audio(audio_path, granularity="segment", diarize=True)

        progress(0.3, desc="Transcribing audio with word granularity...")
        word_transcription = transcribe_audio(audio_path, granularity="word")

        if diarize:
            word_transcription["segments"] = match_words_to_speakers(segment_transcription, word_transcription)

        progress(0.4, desc="Generating subtitles...")
        subtitles = generate_subtitles(word_transcription, segment_transcription)

        unique_speakers = []
        for _, _, _, word_segments, _ in subtitles:
            if word_segments:
                for w in word_segments:
                    if not w.get("speaker_id") in unique_speakers:
                        unique_speakers.append(w.get("speaker_id"))

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

        first_speaker = unique_speakers[0] if unique_speakers else "speaker_null"
        speaker_colors[first_speaker] = highlight_color

        for speaker in unique_speakers:
            if speaker != first_speaker:
                speaker_colors[speaker] = default_colors[len(speaker_colors) % len(default_colors)]
        speaker_colors["speaker_null"] = text_color

        progress(0.5, desc="Generating overlay...")
        processed_video = overlay_subtitles(
            video_path,
            audio_path,
            subtitles,
            font_size,
            background_style,
            alignment,
            text_color,
            speaker_colors,
            incoming_color,
            font_name,
            progress=progress,
            add_logo=True
        )

        raw_subtitles_html = generate_raw_subtitles_html(subtitles, speaker_colors)

        # Clean up temporary files
        temp_files = ["temp_audio.mp3", "subtitles.ass"]
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)

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
        cleanup_files()
        progress(0, desc="Failed to process video.")
        return None, str(e), gr.HTML(visible=False)

def vo_subtitles_tab():
    with gr.TabItem("VO Subtitles", elem_classes="gradio-tabitem"):
        gr.Markdown("## VO Subtitles", elem_classes="gradio-markdown")
        gr.Markdown(
            "Upload a video to generate a version with subtitles with word-level timestamp granularity.",
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
                submit_btn = gr.Button("Generate Video", variant="primary", elem_classes="gradio-button")

                with gr.Accordion("Settings", open=False, elem_classes="gradio-accordion"):
                    diarize_checkbox = gr.Checkbox(
                        label="Enable Speaker Diarization",
                        value=True,
                        info="Check to identify and color-code different speakers using segment granularity timestamps with diarization.",
                        elem_classes="gradio-checkbox"
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
                    with gr.Group():
                        text_color_picker = gr.ColorPicker(
                            label="Default Text Color",
                            value="#FFFFFF",
                            elem_classes="gradio-colorpicker"
                        )
                        highlight_color_picker = gr.ColorPicker(
                            label="First Speaker Highlight Color",
                            value="#FFA500",
                            elem_classes="gradio-colorpicker"
                        )
                        incoming_color_picker = gr.ColorPicker(
                            label="Incoming Text Color",
                            value="#808080",
                            elem_classes="gradio-colorpicker"
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
                    label="Video with Subtitles",
                    include_audio=True,
                    elem_classes="gradio-video"
                )
                error_output = gr.Textbox(
                    label="Error",
                    visible=False,
                    elem_classes="gradio-textbox"
                )
                with gr.Accordion("Raw Subtitles", open=False, elem_classes="gradio-accordion"):
                    raw_subtitles_output = gr.HTML(
                        label="Raw Subtitles",
                        visible=True
                    )

        with gr.Row(elem_classes="gradio-examples"):
            gr.Examples(
                examples=[
                    [
                        "examples/short_example.mp4",
                        False,
                        24,
                        "None",
                        "Bottom Center",
                        "#FFFFFF",
                        "#FFA500",
                        "#808080",
                        "Liberation Sans",
                    ],
                    [
                        "examples/talk_example.mp4",
                        True,
                        24,
                        "None",
                        "Bottom Center",
                        "#FFFFFF",
                        "#FFA500",
                        "#808080",
                        "Liberation Sans",
                    ],
                ],
                inputs=[
                    video_input,
                    diarize_checkbox,
                    font_size_slider,
                    background_style_radio,
                    alignment_dropdown,
                    text_color_picker,
                    highlight_color_picker,
                    incoming_color_picker,
                    font_dropdown,
                ],
                outputs=[
                    video_output,
                    error_output,
                    raw_subtitles_output
                ],
                fn=process_uploaded_video,
                cache_examples=True,
                label="Try an Example",
            )

        submit_btn.click(
            fn=process_uploaded_video,
            inputs=[
                video_input,
                diarize_checkbox,
                font_size_slider,
                background_style_radio,
                alignment_dropdown,
                text_color_picker,
                highlight_color_picker,
                incoming_color_picker,
                font_dropdown,
            ],
            outputs=[
                video_output,
                error_output,
                raw_subtitles_output
            ],
            api_name="generate_video"
        )
