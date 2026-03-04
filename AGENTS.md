# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-04
**Branch:** main

## OVERVIEW

Voxtral-Subtitles is a Gradio-based application for high-precision video subtitling and transcription. It supports word-level granularity, speaker diarization, and multilingual translation using AssemblyAI and Deepgram for transcription, and Mistral for translation.

## STRUCTURE

```
.
├── app.py              # Application Entry Point
├── utils.py            # Core Logic (Audio/Transcription/Subtitle Gen)
├── tabs/               # Feature Tabs (UI + Orchestration)
│   ├── vo_subtitles.py # Word-level subtitles
│   ├── multilingual.py # Translated subtitles
│   ├── transcription.py# Raw text transcription
│   └── image_slideshow.py # Audio + Images to Video
├── styles.css          # UI Customization
└── requirements.txt    # Project dependencies
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| API Integration | `utils.py:transcribe_audio_unified` | AssemblyAI/Deepgram logic |
| Subtitle Splitting | `utils.py:split_group_by_punctuation_and_time` | Logic for 80-char limit |
| Translation Logic | `utils.py:translate` | LLM-based segment translation (Mistral) |
| UI/Layout | `app.py`, `tabs/*.py` | Gradio interface definitions |

## CODE MAP

| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `DeepgramClient` | Client | `utils.py:28` | High | Fallback API client |
| `Mistral` | Client | `utils.py:17` | High | Translation API client |
| `transcribe_audio_unified` | Function | `utils.py:251` | High | Central transcription router |
| `process_uploaded_video` | Function | `tabs/vo_subtitles.py` | High | VO Tab orchestrator |
| `overlay_subtitles` | Function | `utils.py:537` | Med | FFmpeg burner |
| `translate` | Function | `utils.py:832` | Low | LLM translation wrapper |

## CONVENTIONS

- **Modular Tabs**: Features must be encapsulated in `tabs/` and registered in `app.py`.
- **Async Execution**: Long-running API/FFmpeg tasks use `run_with_timeout` threading.
- **Cleanup**: Always call `cleanup_files()` before and after processing to manage temp assets.
- **Hardware Acceleration**: Use `COMPUTE_DEVICE=CUDA` to enable NVIDIA NVENC.

## ANTI-PATTERNS (THIS PROJECT)

- **Bloated utils.py**: Avoid adding UI-specific logic to `utils.py`.
- **Silent Failures**: Don't suppress FFmpeg errors; use `stderr` for diagnostics.
- **Direct Mistral Transcription**: Mistral is deprecated for transcription in favor of Deepgram.

## COMMANDS

```bash
./start.sh nvidia --build # Start with GPU support
```

## NOTES

- **80-Char Limit**: Subtitles are strictly split to 80 chars for readability.
- **Unified Transcription**: Uses AssemblyAI by default, falls back to Deepgram.
- **Persistent Storage**: `/app/temp_files` is a volume for reliable Podman cleanup.
- **Container**: Dockerfile and compose.yaml optimized for Podman/NVIDIA.
