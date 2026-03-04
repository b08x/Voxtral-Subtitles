import gradio as gr
import threading
import os
from utils import (
    cleanup_files,
    extract_audio_from_video,
    transcribe_audio_unified,
    generate_subtitles,
    overlay_subtitles,
    generate_raw_subtitles_html,
)


def run_with_timeout(func, args, kwargs, timeout=300):
    """Run a function with a timeout."""
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            error[0] = str(e)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        return None, "Processing timed out after 5 minutes."
    if error[0]:
        return None, error[0]
    return result[0], None


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
    progress=gr.Progress(),
):
    try:
        cleanup_files()
        video_path = video_file.name
        progress(0.1, desc="Extracting audio from video...")
        audio_path, extract_error = run_with_timeout(
            lambda: extract_audio_from_video(video_path),
            args=(),
            kwargs={},
            timeout=300,
        )
        if extract_error:
            raise Exception(extract_error)

        # Use unified transcription (AssemblyAI by default, Mistral as fallback)
        progress(
            0.2, desc="Transcribing audio (AssemblyAI with speaker diarization)..."
        )
        word_transcription, transcribe_error = run_with_timeout(
            lambda: transcribe_audio_unified(audio_path, diarize=diarize),
            args=(),
            kwargs={},
            timeout=300,
        )
        if transcribe_error:
            raise Exception(transcribe_error)

        # For subtitle generation, we need segment data
        # AssemblyAI already provides this in word_transcription["segments"]
        segment_transcription = {"segments": word_transcription.get("segments", [])}

        progress(0.4, desc="Generating subtitles...")
        subtitles, generate_error = run_with_timeout(
            lambda: generate_subtitles(word_transcription, segment_transcription),
            args=(),
            kwargs={},
            timeout=300,
        )
        if generate_error:
            raise Exception(generate_error)

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
                speaker_colors[speaker] = default_colors[
                    len(speaker_colors) % len(default_colors)
                ]
        speaker_colors["speaker_null"] = text_color

        progress(0.5, desc="Generating overlay...")
        processed_video, overlay_error = run_with_timeout(
            lambda: overlay_subtitles(
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
                add_logo=True,
            ),
            args=(),
            kwargs={},
            timeout=300,
        )
        if overlay_error:
            raise Exception(overlay_error)

        raw_subtitles_html = generate_raw_subtitles_html(subtitles, speaker_colors)

        # Clean up temporary files
        temp_files = ["temp_audio.mp3", "subtitles.ass"]
        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)

        progress(1.0, desc="Done.")
        return processed_video, None, gr.HTML(visible=True, value=raw_subtitles_html)

    except Exception as e:
        cleanup_files()
        progress(0, desc="Failed to process video.")
        return None, str(e), gr.HTML(visible=False)


def vo_subtitles_tab():
    with gr.TabItem("VO Subtitles", elem_classes="gradio-tabitem"):
        gr.Markdown("## VO Subtitles", elem_classes="gradio-markdown")
        gr.Markdown(
            "Upload a video to generate a version with subtitles with word-level timestamp granularity.",
            elem_classes="gradio-markdown",
        )

        with gr.Row():
            with gr.Column(scale=3):
                video_input = gr.Video(label="Upload Video", sources=["upload"])

            with gr.Column(scale=1):
                diarize = gr.Checkbox(
                    label="Speaker Diarization",
                    value=True,
                    info="Identify different speakers in the video",
                )

        with gr.Row():
            with gr.Column():
                font_size = gr.Slider(
                    minimum=12, maximum=72, value=24, step=1, label="Font Size"
                )
                background_style = gr.Dropdown(
                    choices=["None", "Box", "Opaque", "Shadow"],
                    value="None",
                    label="Background Style",
                )

            with gr.Column():
                alignment = gr.Dropdown(
                    choices=[
                        "Bottom Center",
                        "Top Center",
                        "Bottom Left",
                        "Bottom Right",
                    ],
                    value="Bottom Center",
                    label="Subtitle Alignment",
                )
                font_name = gr.Dropdown(
                    choices=["Liberation Sans", "Arial", "Helvetica", "Courier New"],
                    value="Liberation Sans",
                    label="Font",
                )

        with gr.Row():
            with gr.Column():
                text_color = gr.ColorPicker(label="Text Color", value="#FFFFFF")
                highlight_color = gr.ColorPicker(
                    label="Speaker Highlight Color", value="#FFA500"
                )

            with gr.Column():
                incoming_color = gr.ColorPicker(
                    label="Incoming Speaker Color", value="#808080"
                )

        with gr.Row():
            submit_btn = gr.Button("Generate Subtitles", variant="primary")

        with gr.Row():
            video_output = gr.Video(label="Output Video", visible=True)
            error_output = gr.Textbox(label="Error", visible=False)
            subtitles_html = gr.HTML(visible=False)

        submit_btn.click(
            fn=process_uploaded_video,
            inputs=[
                video_input,
                diarize,
                font_size,
                background_style,
                alignment,
                text_color,
                highlight_color,
                incoming_color,
                font_name,
            ],
            outputs=[video_output, error_output, subtitles_html],
        )
