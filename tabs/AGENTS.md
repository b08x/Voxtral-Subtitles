# TABS KNOWLEDGE BASE

## OVERVIEW
The `tabs/` directory contains modular Gradio interface components, each encapsulating a specific feature (VO, Translation, Transcription) and its orchestration logic.

## WHERE TO LOOK
| Feature | File | Role |
|---------|------|------|
| Word-level Subtitles | `vo_subtitles.py` | Orchestrates dual API calls (Diarize + Word) |
| Translated Subtitles | `multilingual.py` | LLM translation + intelligent character-limit splitting |
| Raw Transcription | `transcription.py` | Simple speaker-coded text output |

## CONVENTIONS
- **Export Pattern**: Each module MUST export a `{feature}_tab()` function for registration in `app.py`.
- **Timeout Wrapper**: All long-running logic MUST be wrapped in `run_with_timeout` (default 300s) to prevent Gradio UI freezes.
- **Progress Tracking**: UI functions MUST accept a `gr.Progress()` instance to update the frontend state.
- **Color Mapping**: Speakers are assigned from a `default_colors` list, with the first speaker often set to a user-defined highlight color.

## ANTI-PATTERNS
- **Heavy Logic**: Do not implement core DSP or API logic here; delegate to `utils.py`.
- **State Pollution**: Avoid global variables within tab modules; keep state within Gradio components or function closures.
- **Direct Threading**: Use the provided `run_with_timeout` helper instead of raw `threading.Thread` to ensure consistent error handling.

## NOTES
- **Splitting Logic**: `multilingual.py` uses `split_text_intelligently` to maintain the 80-character subtitle limit while preserving word boundaries.
- **Dual Calls**: `vo_subtitles.py` is the only module that makes two sequential transcription calls to align word-level timestamps with speaker IDs.
