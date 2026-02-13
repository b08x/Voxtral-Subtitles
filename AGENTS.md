# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-13
**Commit:** 713112c
**Branch:** main

## OVERVIEW

Voxtral-Subtitles is a Gradio-based application for high-precision video subtitling and transcription using Mistral's Voxtral API. It supports word-level granularity, speaker diarization, and multilingual translation.

## STRUCTURE

```
.
├── app.py              # Application Entry Point
├── utils.py            # Core Logic (Audio/Transcription/Subtitle Gen)
├── tabs/               # Feature Tabs (UI + Orchestration)
│   ├── vo_subtitles.py # Word-level subtitles
│   ├── multilingual.py # Translated subtitles
│   └── transcription.py# Raw text transcription
├── examples/           # Sample assets
├── styles.css          # UI Customization
└── requirements.txt    # Project dependencies
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| API Integration | `utils.py:transcribe_audio` | Mistral API calls |
| Subtitle Splitting | `utils.py:split_group_by_punctuation_and_time` | Logic for 80-char limit |
| Translation Logic | `utils.py:translate` | LLM-based segment translation |
| UI/Layout | `app.py`, `tabs/*.py` | Gradio interface definitions |

## CODE MAP

| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `Mistral` | Client | `utils.py:17` | High | API client initialization |
| `process_uploaded_video` | Function | `tabs/vo_subtitles.py` | High | VO Tab orchestrator |
| `overlay_subtitles` | Function | `utils.py:340` | Med | FFmpeg burner |
| `translate` | Function | `utils.py:478` | Low | LLM translation wrapper |

## CONVENTIONS

- **Modular Tabs**: Features must be encapsulated in `tabs/` and registered in `app.py`.
- **Async Execution**: Long-running API/FFmpeg tasks use `run_with_timeout` threading.
- **Cleanup**: Always call `cleanup_files()` before and after processing to manage temp assets.

## ANTI-PATTERNS (THIS PROJECT)

- **Bloated utils.py**: Avoid adding UI-specific logic to `utils.py`.
- **Silent Failures**: Don't suppress FFmpeg errors; use `stderr` for diagnostics.
- **Global Paths**: Avoid hardcoded relative paths; use CWD-safe lookups.

## COMMANDS

```bash
python app.py   # Run local gradio server
```

## NOTES

- **80-Char Limit**: Subtitles are strictly split to 80 chars for readability.
- **Dual API Calls**: VO Subtitles require two calls (diarization vs word-granularity mismatch).
- **FFmpeg**: Requires `ffmpeg` and `ffprobe` binaries in PATH.
- **Testing**: No automated tests currently exist.
- **Container**: Dockerfile and compose.yaml available for deployment.
