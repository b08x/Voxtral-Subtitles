import gradio as gr
from utils import *
from components.speaker_colors import build_speaker_colors

def process_transcription(video_file, diarize=True, progress=gr.Progress()):
    try:
        cleanup_files()
        video_path = video_file.name
        progress(0.1, desc=f"Extracting audio from video...")
        audio_path = extract_audio_from_video(video_path)

        if diarize:
            progress(0.5, desc="Transcribing with speaker diarization...")
            transcription_response = transcribe_audio_unified(audio_path, diarize=True)
            segments = transcription_response.get("segments", [])

            if not segments:
                return gr.HTML(value="<div style='color: #FF5733; background: #121212; padding: 10px; border-radius: 8px;'>No transcription segments found.</div>", visible=True)

            # Build speaker colors using shared component
            speaker_colors = build_speaker_colors(segments, "#FFFFFF", "#FFFFFF", diarize=True)

            html_output = "<div style='white-space: pre-wrap; font-size: 16px; line-height: 1.5; background: #121212; padding: 10px; border-radius: 8px;'>"
            for seg in segments:
                speaker = seg.get("speaker_id", "speaker_null")
                text = seg.get("text", "")
                color = speaker_colors.get(speaker, "#FFFFFF")
                html_output += f"<span style='color: {color};'><b>{speaker}:</b> {text}</span><br/>"
            html_output += "</div>"
        else:
            progress(0.5, desc="Transcribing audio...")
            transcription_response = transcribe_audio_unified(audio_path, diarize=False)
            text = transcription_response.get("text", "")

            if not text:
                return gr.HTML(value="<div style='color: #FF5733; background: #121212; padding: 10px; border-radius: 8px;'>No transcription text found.</div>", visible=True)

            html_output = f"<div style='white-space: pre-wrap; font-size: 16px; line-height: 1.5; color: #FFFFFF; background: #121212; padding: 10px; border-radius: 8px;'>{text}</div>"
        progress(1.0, desc="Done.")
        return gr.HTML(value=html_output, visible=True)
    except Exception as e:
        cleanup_files()
        progress(0, desc=f"Error: {str(e)}")
        return gr.HTML(value=f"<div style='color: #FF5733; background: #121212; padding: 10px; border-radius: 8px;'>{str(e)}</div>", visible=True)

def transcription_tab():
    with gr.TabItem("Transcription", elem_classes="gradio-tabitem"):
        gr.Markdown("## Transcription", elem_classes="gradio-markdown")
        gr.Markdown("Upload an audio or video file to generate a transcription.", elem_classes="gradio-markdown")

        with gr.Row():
            with gr.Column(scale=1, elem_classes="input-column"):
                audio_input = gr.File(
                    label="Upload Audio/Video",
                    type="filepath",
                    file_types=[".mp3", ".wav", ".mp4", ".mov", ".avi"],
                    elem_classes="gradio-file"
                )
                diarize_checkbox = gr.Checkbox(
                    label="Enable Speaker Diarization",
                    value=True,
                    info="Check to identify and color-code different speakers. Uncheck for raw text output.",
                    elem_classes="gradio-checkbox"
                )
                submit_btn = gr.Button("Transcribe", variant="primary", elem_classes="gradio-button")

        with gr.Column(scale=2, elem_classes="output-column"):
            transcription_output = gr.HTML(label="Transcription", visible=True)

        submit_btn.click(
            fn=process_transcription,
            inputs=[audio_input, diarize_checkbox],
            outputs=transcription_output,
            api_name="transcribe_audio"
        )
