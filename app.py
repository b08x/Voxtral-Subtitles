import gradio as gr
from tabs.vo_subtitles import vo_subtitles_tab
from tabs.multilingual import multilingual_tab
from tabs.transcription import transcription_tab
from tabs.image_slideshow import image_slideshow_tab

def how_it_works_tab():
    with gr.TabItem("How It Works", elem_classes="gradio-tabitem"):
        gr.Markdown("## How It Works", elem_classes="gradio-markdown")
        with gr.Group(elem_classes="gradio-group"):
            gr.Markdown(
                """
                <div style='padding: 20px;'>
                This app allows you to generate subtitles for videos with word-level segmentation, diarization, or even translated subtitles from multiple languages.
                Below is a detailed, step-by-step breakdown of how each feature works:

                ### **1. VO Subtitles**
                **Purpose:** Generate subtitles with word-level precision and optional speaker diarization.

                **How it works:**
                1. **Upload a Video:** Select a video file (MP4, MOV, or AVI).
                2. **Audio Extraction:** The app extracts the audio using `ffmpeg`.
                3. **API Calls:**
                   - The app makes **two API calls** to Mistral:
                     - First, with `diarize=True` to identify speakers and segment-level timestamps.
                     - Second, with `granularity="word"` to get word-level timestamps.
                   This is required as diarization and word granularity are not currently available simultaneously.
                4. **Mapping Speakers to Words:**
                   - Each word timestamp is matched to a speaker using the segment-level diarization transcription.
                   - Words are grouped into subtitle lines (max 80 chars), split at punctuation or time gaps, this can be freely customized.
                5. **Subtitle Styling:** Customize font, size, alignment, and colors for speakers.
                6. **Overlay:** The app generates an `.ass` file and overlays subtitles onto the video using `ffmpeg`.
                7. **Output:** The processed video with subtitles and a raw HTML output of subtitles with timestamps.

                ### **2. Multilingual Subtitles**
                **Purpose:** Translate subtitles into another language, with optional speaker diarization.

                **How it works:**
                1. **Upload a Video:** Select a video file (MP4, MOV, or AVI).
                2. **Audio Extraction:** The app extracts the audio using `ffmpeg`.
                3. **API Call:**
                   - The app calls Mistral’s API with `diarize=True` (if enabled).
                   - The transcription is translated into the selected language using Mistral Small.
                4. **Subtitle Splitting:**
                   - Translated text is split into lines (max 80 chars) using punctuation or time gaps.
                   - Timing is preserved by distributing the original segment’s duration.
                5. **Subtitle Styling:** Customize font, size, alignment, and colors for speakers.
                6. **Overlay:** The app generates an `.ass` file and overlays translated subtitles onto the video.
                7. **Output:** The processed video with translated subtitles and a raw HTML output.

                ### **3. Transcription**
                **Purpose:** Generate a text transcription, with optional speaker diarization.

                **How it works:**
                1. **Upload Audio/Video:** Select an audio or video file (MP3, WAV, MP4, MOV, or AVI).
                2. **API Call:**
                   - With diarization: Returns segments with speaker IDs.
                   - Without diarization: Returns raw text.
                3. **Output Formatting:**
                   - With diarization: Each segment is color-coded by speaker.
                   - Without diarization: Raw text is displayed as-is.
                4. **Output:** A formatted HTML transcription.

                ### **4. Image Slideshow**
                **Purpose:** Create MP4 videos from audio files and image sequences with synchronized subtitles.

                **How it works:**
                1. **Upload Files:** Select an audio file (MP3, WAV, M4A, FLAC, OGG) and multiple images (JPG, PNG, BMP, TIFF, WEBP).
                2. **Duration Configuration:**
                   - **Auto-distribute:** Automatically distributes audio duration across images (first/last get slightly longer)
                   - **Manual per image:** Set custom duration for each image using interactive controls
                   - **CSV import:** Upload a CSV file with image names and durations
                3. **Image Processing:**
                   - Images are validated for format and size
                   - Normalized to target resolution (1920x1080, 1280x720, or 854x480)
                   - Aspect ratio handling: letterbox (add black bars), crop (fit exactly), or stretch (distort)
                4. **Video Creation:**
                   - Individual video segments created for each image with precise duration
                   - Segments concatenated using FFmpeg
                   - Audio synchronized with the image sequence
                5. **Subtitle Generation:**
                   - Audio transcribed using Mistral AI with word-level precision
                   - Word timings mapped to image display periods
                   - Subtitles adjusted to match slideshow timing
                6. **Timeline Visualization:** Interactive chart showing image duration distribution
                7. **Output:** MP4 video with images, audio, and synchronized .ass subtitles


                </div>
                """,
                elem_classes="gradio-markdown"
            )

with open("styles.css", "r") as f:
    css = f.read()

with gr.Blocks(title="Voxtral Transcribe - Subtitles Space") as demo:
    gr.Markdown("# Voxtral Transcribe - Subtitles Space\n\nA gradio space leveraging Voxtral Transcribe 2.0 for multiple use cases focused on subtitle creation and transcription.", elem_classes="gradio-markdown")

    with gr.Tabs(elem_classes="gradio-tab"):
        vo_subtitles_tab()
        multilingual_tab()
        transcription_tab()
        image_slideshow_tab()
        how_it_works_tab()

demo.launch(debug=True, css=css)
