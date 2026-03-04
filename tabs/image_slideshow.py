import gradio as gr
import threading
import json
import os
from utils import *

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
        # If the thread is still running after the timeout, consider it a timeout
        return None, "Operation timed out. Please try with smaller files or shorter audio."
    if error[0]:
        return None, error[0]
    return result[0], None


def process_audio_and_images(
    audio_file, image_files, duration_mode, manual_durations_json, csv_file,
    resolution, quality, aspect_handling, diarize,
    font_name, font_size, primary_colour, secondary_colour, outline_colour, back_colour,
    bold, italic, border_style, alignment, margin_l, margin_r, margin_v, encoding,
    progress=gr.Progress()
):
    """Main processing pipeline for audio + images → MP4 + subtitles"""
    try:
        cleanup_files()

        # Step 1: Validate inputs
        progress(0.1, desc="Validating audio and image files...")

        if not audio_file:
            raise ValueError("Please upload an audio file")

        if not image_files or len(image_files) == 0:
            raise ValueError("Please upload at least one image")

        # Get audio duration
        audio_duration = get_audio_duration(audio_file.name)
        progress(0.15, desc=f"Audio duration: {audio_duration:.1f} seconds")

        # Validate images
        validated_images = validate_image_files(image_files)
        progress(0.2, desc=f"Validated {len(validated_images)} images")

        # Step 2: Calculate durations
        progress(0.25, desc="Calculating image display durations...")

        if duration_mode == "Auto-distribute":
            durations = calculate_auto_durations(validated_images, audio_duration)
        elif duration_mode == "Manual per image":
            if not manual_durations_json:
                raise ValueError("Manual durations not provided")
            try:
                manual_durations = json.loads(manual_durations_json)
                if len(manual_durations) != len(validated_images):
                    raise ValueError(f"Duration count mismatch: {len(manual_durations)} durations for {len(validated_images)} images")
                durations = validate_manual_durations(manual_durations, audio_duration)
            except json.JSONDecodeError:
                raise ValueError("Invalid manual durations format")
        else:  # CSV import
            durations = parse_csv_durations(csv_file, validated_images)

        progress(0.3, desc="Image durations calculated successfully")

        # Step 3: Process images
        progress(0.35, desc="Normalizing image resolution...")
        normalized_images = normalize_image_resolution(validated_images, resolution, aspect_handling)

        # Step 4: Create video from images
        progress(0.4, desc="Creating video from image sequence...")
        video_path = create_image_sequence_video(normalized_images, durations, audio_file.name, resolution)

        # Step 5: Transcribe audio for subtitles
        progress(0.6, desc="Transcribing audio...")
        try:
            transcription_response = transcribe_audio_unified(audio_file.name, diarize=diarize)
        except ValueError as e:
            if "API key" in str(e):
                raise ValueError(f"Transcription API key missing or invalid: {str(e)}")
            else:
                raise ValueError(f"Transcription failed: {str(e)}")

        # Step 6: Generate subtitles with timing adjustment
        progress(0.7, desc="Generating subtitles...")
        subtitles = generate_subtitles_for_slideshow(transcription_response, durations, normalized_images)

        # Step 7: Create subtitle files with custom styling
        progress(0.8, desc="Creating subtitle files...")
        subtitle_settings = {
            'font_name': font_name,
            'font_size': font_size,
            'primary_colour': primary_colour,
            'secondary_colour': secondary_colour,
            'outline_colour': outline_colour,
            'back_colour': back_colour,
            'bold': bold,
            'italic': italic,
            'border_style': border_style,
            'alignment': alignment,
            'margin_l': margin_l,
            'margin_r': margin_r,
            'margin_v': margin_v,
            'encoding': encoding
        }

        ass_file_path = create_ass_file(subtitles, **subtitle_settings)

        # Step 8: Overlay subtitles on video
        progress(0.9, desc="Overlaying subtitles...")
        final_video = overlay_subtitles(video_path, audio_file.name, subtitles, **subtitle_settings)

        # Step 9: Create visualizations
        progress(0.95, desc="Creating timeline visualization...")
        timeline_plot = create_timing_visualization(normalized_images, durations)

        # Step 10: Build speaker colors for subtitle preview
        unique_speakers = []
        for _, _, _, word_segments, _ in subtitles:
            if word_segments:
                for w in word_segments:
                    speaker_id = w.get("speaker_id")
                    if speaker_id and speaker_id not in unique_speakers:
                        unique_speakers.append(speaker_id)

        # Create speaker color mapping using user-selected primary color
        default_colors = ["#FFFFFF", "#FFD700", "#87CEEB", "#FF6B6B", "#4ECDC4", "#45B7D1"]
        speaker_colors = {}

        first_speaker = unique_speakers[0] if unique_speakers else "speaker_null"
        speaker_colors[first_speaker] = primary_colour  # Use user-selected color

        for i, speaker in enumerate(unique_speakers[1:], 1):
            speaker_colors[speaker] = default_colors[i % len(default_colors)]
        speaker_colors["speaker_null"] = primary_colour

        # Step 11: Generate subtitle preview HTML
        subtitle_html = generate_raw_subtitles_html(subtitles, speaker_colors)

        progress(1.0, desc="Processing complete!")

        return final_video, ass_file_path, timeline_plot, subtitle_html, None

    except Exception as e:
        cleanup_files()
        error_msg = f"Processing failed: {str(e)}"
        print(f"Error in process_audio_and_images: {error_msg}")
        return None, None, None, None, error_msg


def update_duration_controls(duration_mode, image_files):
    """Update the duration control interface based on selected mode"""
    if not image_files:
        return gr.Group(visible=False), gr.Group(visible=False), gr.HTML("")

    num_images = len(image_files)

    if duration_mode == "Manual per image":
        # Create manual duration controls
        duration_html = "<div style='padding: 10px;'>"
        duration_html += "<h4>Set duration for each image (seconds):</h4>"
        duration_html += "<div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;'>"

        for i in range(num_images):
            image_name = os.path.basename(image_files[i].name) if hasattr(image_files[i], 'name') else f"Image {i+1}"
            duration_html += f"""
            <div style='border: 1px solid #ddd; padding: 8px; border-radius: 4px;'>
                <label style='font-size: 12px; color: #666;'>{image_name}</label><br>
                <input type='number' id='duration_{i}' value='3.0' step='0.1' min='0.1' max='60'
                       style='width: 100%; margin-top: 4px;' onchange='updateDurationsJSON()'>
            </div>
            """

        duration_html += "</div>"
        duration_html += """
        <script>
        function updateDurationsJSON() {
            const durations = [];
            for (let i = 0; i < """ + str(num_images) + """; i++) {
                const input = document.getElementById('duration_' + i);
                if (input) {
                    durations.push(parseFloat(input.value) || 3.0);
                }
            }
            const hiddenInput = document.querySelector('input[data-testid="manual_durations_json"]');
            if (hiddenInput) {
                hiddenInput.value = JSON.stringify(durations);
                hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        // Initialize JSON on load
        setTimeout(updateDurationsJSON, 100);
        </script>
        </div>
        """

        return (
            gr.Group(visible=True),
            gr.Group(visible=False),
            gr.HTML(duration_html)
        )

    elif duration_mode == "CSV import":
        return (
            gr.Group(visible=False),
            gr.Group(visible=True),
            gr.HTML("")
        )

    else:  # Auto-distribute
        return (
            gr.Group(visible=False),
            gr.Group(visible=False),
            gr.HTML("")
        )


def generate_csv_template(image_files):
    """Generate a CSV template file for duration configuration"""
    if not image_files:
        return None

    import csv
    import tempfile

    # Create temporary CSV file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)

    with open(temp_file.name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['image_index', 'image_name', 'duration'])

        for i, image_file in enumerate(image_files):
            image_name = os.path.basename(image_file.name) if hasattr(image_file, 'name') else f"image_{i+1}"
            writer.writerow([i, image_name, 3.0])  # Default 3 seconds

    return temp_file.name


def image_slideshow_tab():
    """Create the Image Slideshow tab interface"""

    with gr.TabItem("Image Slideshow", elem_classes="gradio-tabitem"):
        gr.Markdown("## Audio + Images → Video with Subtitles", elem_classes="gradio-markdown")
        gr.Markdown("Create MP4 videos from audio files and image sequences with synchronized subtitles.", elem_classes="gradio-markdown")

        with gr.Row():
            # Input Panel
            with gr.Column(scale=1):
                # File Uploads
                with gr.Group(elem_classes="gradio-group"):
                    gr.Markdown("### Input Files")
                    audio_input = gr.File(
                        label="Audio File",
                        file_types=[".mp3", ".wav", ".m4a", ".flac", ".ogg"],
                        elem_classes="gradio-file"
                    )
                    image_gallery = gr.File(
                        label="Images (Upload Multiple)",
                        file_count="multiple",
                        file_types=["image"],
                        elem_classes="gradio-file"
                    )

                # Duration Configuration
                with gr.Group(elem_classes="gradio-group"):
                    gr.Markdown("### Duration Settings")
                    duration_mode = gr.Radio(
                        choices=["Auto-distribute", "Manual per image", "CSV import"],
                        value="Auto-distribute",
                        label="Duration Mode",
                        info="How to set display duration for each image"
                    )

                    # Hidden input for manual durations JSON
                    manual_durations_json = gr.Textbox(
                        value="[]",
                        visible=False,
                        elem_id="manual_durations_json"
                    )

                    # Dynamic duration controls
                    with gr.Group(visible=False, elem_classes="gradio-group") as manual_group:
                        manual_duration_display = gr.HTML("")

                    with gr.Group(visible=False, elem_classes="gradio-group") as csv_group:
                        csv_upload = gr.File(label="Duration CSV File", file_types=[".csv"])
                        csv_template_btn = gr.Button("Download CSV Template", size="sm")

                # Video Settings
                with gr.Accordion("Video Settings", open=False):
                    resolution = gr.Dropdown(
                        choices=["1920x1080", "1280x720", "854x480"],
                        value="1920x1080",
                        label="Resolution"
                    )
                    aspect_handling = gr.Radio(
                        choices=["letterbox", "crop", "stretch"],
                        value="letterbox",
                        label="Aspect Ratio Handling",
                        info="letterbox: maintain ratio with black bars, crop: fit exactly, stretch: distort to fit"
                    )
                    quality = gr.Dropdown(
                        choices=["high", "medium", "fast"],
                        value="high",
                        label="Encoding Quality"
                    )

                # Subtitle Settings (copied from existing patterns)
                with gr.Accordion("Subtitle Settings", open=False):
                    diarize_checkbox = gr.Checkbox(label="Enable Speaker Diarization", value=True)

                    font_name = gr.Textbox(label="Font Name", value="Arial")
                    font_size = gr.Slider(label="Font Size", minimum=8, maximum=72, value=20, step=1)

                    with gr.Row():
                        primary_colour = gr.ColorPicker(label="Primary Colour", value="#FFFFFF")
                        secondary_colour = gr.ColorPicker(label="Secondary Colour", value="#FF0000")
                        outline_colour = gr.ColorPicker(label="Outline Colour", value="#000000")
                        back_colour = gr.ColorPicker(label="Background Colour", value="#80000000")

                    with gr.Row():
                        bold = gr.Checkbox(label="Bold", value=False)
                        italic = gr.Checkbox(label="Italic", value=False)

                    border_style = gr.Slider(label="Border Style", minimum=0, maximum=3, value=2, step=1)
                    alignment = gr.Slider(label="Alignment", minimum=1, maximum=9, value=2, step=1)

                    with gr.Row():
                        margin_l = gr.Slider(label="Left Margin", minimum=0, maximum=50, value=10, step=1)
                        margin_r = gr.Slider(label="Right Margin", minimum=0, maximum=50, value=10, step=1)
                        margin_v = gr.Slider(label="Vertical Margin", minimum=0, maximum=50, value=10, step=1)

                    encoding = gr.Dropdown(["utf-8", "utf-16"], label="Encoding", value="utf-8")

                # Process Button
                generate_btn = gr.Button("Generate Video with Subtitles", variant="primary", size="lg")

            # Output Panel
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("Timeline Preview"):
                        timeline_chart = gr.Plot(label="Timeline Visualization")
                        preview_info = gr.HTML("""
                        <div style='padding: 10px; background: #f0f0f0; border-radius: 8px; margin-top: 10px;'>
                            <h4>Timeline Preview</h4>
                            <p>This visualization shows how long each image will be displayed during the video.
                            Each colored segment represents one image, with duration shown in seconds.</p>
                        </div>
                        """)

                    with gr.TabItem("Video Output"):
                        video_output = gr.Video(label="Generated Video", elem_classes="gradio-video")
                        subtitle_download = gr.File(label="Download Subtitles (.ass)")

                    with gr.TabItem("Subtitle Preview"):
                        subtitle_preview = gr.HTML(label="Subtitle Preview")

                    with gr.TabItem("Processing Log"):
                        error_output = gr.HTML(visible=True, elem_classes="gradio-html")

        # Event handlers
        def update_controls_wrapper(duration_mode, image_files):
            manual_group_update, csv_group_update, duration_display = update_duration_controls(duration_mode, image_files)
            return [
                gr.Group(visible=(duration_mode == "Manual per image")),
                gr.Group(visible=(duration_mode == "CSV import")),
                duration_display
            ]

        # Update duration controls when mode or images change
        duration_mode.change(
            fn=update_controls_wrapper,
            inputs=[duration_mode, image_gallery],
            outputs=[manual_group, csv_group, manual_duration_display]
        )

        image_gallery.change(
            fn=update_controls_wrapper,
            inputs=[duration_mode, image_gallery],
            outputs=[manual_group, csv_group, manual_duration_display]
        )

        # CSV template download
        csv_template_btn.click(
            fn=generate_csv_template,
            inputs=[image_gallery],
            outputs=[csv_upload]
        )

        # Main processing
        def process_wrapper(*args):
            result, error = run_with_timeout(
                process_audio_and_images,
                args,
                {},
                timeout=600  # 10 minute timeout
            )

            if error:
                return None, None, None, None, f"<div style='color: red; padding: 10px; border: 1px solid red; border-radius: 4px; background: #ffeeee;'><strong>Error:</strong> {error}</div>"

            if result is None:
                return None, None, None, None, "<div style='color: red; padding: 10px;'>Processing failed with unknown error</div>"

            video, subtitles, timeline, subtitle_html, error_msg = result

            if error_msg:
                return None, None, None, None, f"<div style='color: red; padding: 10px; border: 1px solid red; border-radius: 4px; background: #ffeeee;'><strong>Error:</strong> {error_msg}</div>"

            success_msg = "<div style='color: green; padding: 10px; border: 1px solid green; border-radius: 4px; background: #eeffee;'><strong>Success!</strong> Video generated successfully with subtitles.</div>"

            return video, subtitles, timeline, subtitle_html, success_msg

        generate_btn.click(
            fn=process_wrapper,
            inputs=[
                audio_input, image_gallery, duration_mode, manual_durations_json, csv_upload,
                resolution, quality, aspect_handling, diarize_checkbox,
                font_name, font_size, primary_colour, secondary_colour, outline_colour, back_colour,
                bold, italic, border_style, alignment, margin_l, margin_r, margin_v, encoding
            ],
            outputs=[video_output, subtitle_download, timeline_chart, subtitle_preview, error_output]
        )