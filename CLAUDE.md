# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py

# Set required environment variables
cp .env.example .env
# Edit .env to add MISTRAL_API_KEY
```

### Docker Development
```bash
# Quick start (CPU-only)
./start.sh

# With specific hardware acceleration
./start.sh up cpu|nvidia|intel

# Rebuild containers
./start.sh up --build

# Stop services
./start.sh down

# Clean build caches and temp files
./start.sh clean
```

### Testing
```bash
# Manual testing with example videos
# Use files in examples/ directory for testing tabs

# Check container logs
docker compose logs -f
```

## Architecture Overview

### Core Design Pattern
This is a **hub-and-spoke architecture** where `utils.py` (745 lines) serves as the central processing hub for all AI and video operations. Each Gradio tab imports from utils and handles only UI concerns.

```
app.py (main entry)
├── tabs/vo_subtitles.py     → utils.py (word-level subtitles)
├── tabs/multilingual.py     → utils.py (translation + subtitles)
├── tabs/transcription.py    → utils.py (text-only transcription)
└── styles.css (shared styling)
```

### Key Processing Pipeline
```
Video → Audio Extraction (FFmpeg) → Mistral AI → Subtitle Generation → Video Overlay
```

**Critical Implementation Detail**: Mistral AI doesn't support diarization + word-level granularity simultaneously, so the codebase uses a **dual API strategy**:
1. First call: `diarize=True, granularity="segment"` for speaker identification
2. Second call: `granularity="word"` for precise timestamps
3. Algorithmic mapping using `match_words_to_speakers()` to combine results

### File Responsibilities

**utils.py (Central Hub)**
- `transcribe_audio()` - Mistral AI integration with dual API strategy
- `extract_audio_from_video()` - FFmpeg wrapper for audio extraction
- `match_words_to_speakers()` - Core algorithm mapping segment speakers to words
- `generate_subtitles()` - Intelligent subtitle line creation (80 char max, punctuation-aware)
- `overlay_subtitles()` - FFmpeg video processing with .ass subtitle overlay
- `translate()` - Mistral AI translation for multilingual subtitles

**Tab Files (UI Only)**
- Handle Gradio components, user interactions, and progress updates
- All business logic delegated to utils.py functions
- Include timeout handling for long-running operations

### Environment Configuration

**Required Environment Variables**
```bash
MISTRAL_API_KEY=your_api_key_here
```

**Docker Environment**
- Supports hardware acceleration profiles: cpu, nvidia, intel
- Custom network MTU (1400) for API reliability
- Non-root user for security
- Persistent temp file management

### Development Patterns

**When modifying AI processing**: Work in `utils.py`, test across all three tabs
**When changing UI**: Modify individual tab files, shared styling in `styles.css`
**When adding features**: Follow the existing pattern of UI in tabs/ + logic in utils.py
**Subtitle formatting**: Use `split_text_intelligently()` for proper line breaks, respect 80-character limit

### Use Context7 MCP for Loading Documentation

Context7 MCP is available to fetch up-to-date documentation with code examples.

**Recommended library IDs**:

- `/mistralai/client-python` - Mistral AI Python SDK documentation
- `/mistralai/platform-docs-public` - Mistral AI Platform documentation
- `/llmstxt/mistral_ai_llms-full_txt` - Full text documentation for Mistral AI APIs
- `/websites/dspy_ai` - DSPy framework website with comprehensive documentation and examples
- `/stanfordnlp/dspy` - Official DSPy GitHub repository with source code and API reference
- `/llmstxt/dspy_ai_llms_txt` - Complete DSPy framework documentation for programming LLMs
- `/haasonsaas/dspy-0to1-guide` - DSPy beginner's guide for getting started with the framework
