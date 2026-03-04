---
title: project
tags:
  - video-topic-clustering
  - ass-subtitle-parsing
  - screencast-ui-analysis
  - vlm-frame-contextualization
  - perceptual-frame-deduplication
  - video-semantic-retrieval
  - video-analysis
  - screencast-processing
  - vision-language-models
  - scene-detection
last updated: Sunday, March 1st 2026, 8:18:08 am
---

# VLMRAG Project: Video Semantic Retrieval System

> **Project Status**: In Progress  
> **Last Updated**: 2026-03-01

---

## 1. Overview

This project builds a **Video Semantic Retrieval System** that processes screencast videos to extract actionable insights about user interface components and workflow patterns. The system combines Vision-Language Models (VLMs), vector databases, and contextual retrieval to transform raw video content into searchable, structured knowledge.

### Core Objective

Process screencast videos (especially React software demonstrations) to:
1. Extract topic clusters from `.ass` subtitle files
2. Segment videos using scene detection
3. Identify UI components, workflow insights, and interaction patterns
4. Enable semantic search across processed video content

---

## 2. Daily Notes Correlation

### From 2026-03-01 Daily

| Daily Note Requirement | VLMRAG Component | Implementation |
|------------------------|------------------|----------------|
| Parse `.ass` subtitle file | Audio/Subtitle Processing | New module: `subtitle.py` |
| Extract topic clusters with timestamps | Topic Modeling | Scene-based clustering |
| Create CSV scene list for scene-detect | Video Segmentation | Use PySceneDetect with custom scene list |
| Extract 3+ frames per segment, dedupe with imagehash | Frame Extraction | OpenCV + imagehash |
| Generate contextual summaries | Contextual Retrieval | Topic cluster → Scene context |
| Process scene frames with context | VLM Analysis | Ollama/Granite Vision |
| Output: UI components, workflow insights | Synthesis | JSON + Markdown output |
| Chunk large JSON files | Data Management | Streaming JSON parser |

### Data Flow

```shell
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ .ass File   │────▶│ Topic Cluster│────▶│ CSV Scene List  │
└─────────────┘     │ Extractor    │     └────────┬────────┘
                   └──────────────┘              │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ VLM Frames  │◀────│ Scene Detect │◀────│ Video File      │
└─────────────┘     └──────┬───────┘     └─────────────────┘
       │                   │
       ▼                   ▼
┌──────────────────────────────────────────────────────┐
│ Contextual Summary Generation                         │
│ (Topic Cluster Context + Frame Analysis)             │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ UI Components│     │ Workflow     │
│ JSON        │     │ Insights     │
└─────────────┘     └──────────────┘
```

---

## 3. Tech Stack

### Core Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Video Processing** | PySceneDetect, FFmpeg, OpenCV | Scene detection, frame extraction |
| **Subtitle Parsing** | `ass_parser` library | Parse `.ass` subtitle files |
| **Frame Deduplication** | `imagehash` | Remove duplicate frames via perceptual hashing |
| **Vision Models** | Ollama + Granite Vision 2B / Llama 3.2 Vision | Analyze screen content |
| **Transcription** | Groq Whisper / Local Whisper | Audio-to-text |
| **Vector Storage** | pgvector (PostgreSQL) | Semantic search + metadata |
| **Orchestration** | CrewAI | Agentic workflow automation |
| **Package Manager** | uv | Python dependency management |

### Model Configuration (from 03_Technical)

* **Vision Model**: `granite3.2-vision:2b` or `llama3.2-vision`
* **Embedding Model**: `granite-embedding:30m` (384 dimensions)
* **Image Resolution**: 1344px max edge (Lanczos resampling)
* **Quantization**: Q8_0 (preferred) or FP16
* **Context Window**: 8192+ tokens

### Dependencies

```bash
# Core
uv add scenedetect[opencv] opencv-python-headless pillow imagehash
uv add psycopg2-binary pgvector sqlalchemy
uv add ollama

# Audio
uv add whisper python-whois  # or groq for cloud

# Utilities
uv add rich python-dotenv typer jinja2
```

---

## 4. Architecture

### Storage: Integrated (pgvector)

Based on `01_Architecture/Hybrid_Storage_Architecture.md`, we use **pgvector** for:
* ACID compliance between metadata and vectors
* Hybrid search (semantic + metadata filtering)
* Single query execution for complex queries

### Schema Design

```sql
-- Videos table
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    duration_seconds FLOAT,
    subtitle_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scenes table (from scene detect + topic clusters)
CREATE TABLE scenes (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    topic_cluster TEXT,
    contextual_summary TEXT,
    ui_components JSONB,
    workflow_insights JSONB
);

-- Frames table (extracted + analyzed)
CREATE TABLE frames (
    id SERIAL PRIMARY KEY,
    scene_id INTEGER REFERENCES scenes(id),
    timestamp FLOAT NOT NULL,
    image_path TEXT,
    frame_hash TEXT,  -- imagehash for deduplication
    vlm_analysis JSONB,
    embedding vector(384)
);

-- Index for semantic search
CREATE INDEX ON frames USING hnsw (embedding vector_cosine_ops);
```

---

## 5. Implementation Guide

### Module Structure

```shell
vlmrag/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI Entry Point
│   ├── video.py             # Scene Detection & Frame Extraction
│   ├── subtitle.py           # .ass parsing & topic clustering
│   ├── vision.py            # VLM Analysis (Ollama)
│   ├── audio.py             # Transcription (Groq/Whisper)
│   ├── deduplication.py     # Frame deduplication (imagehash)
│   ├── synthesis.py         # JSON Compilation & Markdown Generation
│   └── storage.py           # pgvector operations
├── tests/
├── notebooks/
└── data/
```

### Pipeline Stages

#### Stage 1: Subtitle Processing

```shell
Input: video.srt / video.ass
Process:
  1. Parse subtitle timestamps and text
  2. Group into topic clusters (NLP/embedding)
  3. Output: timestamped topic list
```

#### Stage 2: Scene Detection

```shell
Input: Topic list + Video
Process:
  1. Use topic timestamps as scene boundaries
  2. Run PySceneDetect for refinement
  3. Output: CSV scene list (start, end, topic)
```

#### Stage 3: Frame Extraction

```shell
Input: Video + Scene List
Process:
  1. Extract 3+ frames per scene (start, middle, end)
  2. Compute perceptual hash (imagehash)
  3. Deduplicate across scenes
  4. Output: unique frames with timestamps
```

#### Stage 4: Contextual Analysis

```shell
Input: Frames + Topic Clusters
Process:
  1. Generate contextual prompt (topic context + frame)
  2. Send to VLM (Ollama)
  3. Extract UI components, actions, state
  4. Output: structured JSON per frame
```

#### Stage 5: Storage & Synthesis

```shell
Input: Frame Analyses
Process:
  1. Store in pgvector with metadata
  2. Generate narrative Markdown
  3. Chunk large JSON files
  4. Output: searchable database + documents
```

---

## 6. User Stories

### Story 1: Subtitle-to-Scene Mapping

> **As a** content analyst  
> **I want to** process `.ass` subtitle files to extract topic clusters  
> **So that** I can create scene boundaries that align with actual content topics

**Acceptance Criteria:**
- [ ] Parse `.ass` files with timestamp precision
- [ ] Cluster subtitle text into topics using embeddings
- [ ] Output CSV with `start_time, end_time, topic_label`
- [ ] Handle multi-line subtitles within single timestamp

### Story 2: Intelligent Frame Extraction

> **As a** video processor  
> **I want to** extract 6+ frames per scene with deduplication  
> **So that** I don't process redundant visual content

**Acceptance Criteria:**
- [ ] Extract frames at start, 1/3, 2/3, end of each scene
- [ ] Compute perceptual hash for each frame
- [ ] Remove duplicates within threshold (hamming distance < 5)
- [ ] Preserve at least 1 frame per scene

### Story 3: Contextual VLM Analysis

> **As a** workflow analyst  
> **I want to** analyze frames with topic context  
> **So that** the VLM understands what the user is trying to do

**Acceptance Criteria:**
- [ ] Inject topic cluster context into VLM prompt
- [ ] Extract: application name, UI components, user actions, state changes
- [ ] Return structured JSON (not raw text)
- [ ] Handle API failures gracefully with retries

### Story 4: Semantic Video Search

> **As a** researcher  
> **I want to** search processed videos semantically  
> **So that** I can find specific UI interactions or workflow patterns

**Acceptance Criteria:**
- [ ] Vectorize natural language queries
- [ ] Search across all processed frames
- [ ] Filter by video, date, or topic cluster
- [ ] Return ranked results with timestamps and snippets

### Story 5: Workflow Insight Extraction

> **As a** UX researcher  
> **I want to** extract workflow patterns from screencasts  
> **So that** I can analyze how users interact with the application

**Acceptance Criteria:**
- [ ] Identify UI components (buttons, forms, toggles)
- [ ] Track state changes within scenes
- [ ] Generate workflow graph (action sequence)
- [ ] Export to JSON for further analysis

---

## 7. API Reference

### CLI Usage

```bash
# Full pipeline
uv run -m src.main process video.mp4 --subtitles video.ass

# Individual stages
uv run -m src.main extract-scenes video.mp4 --subtitles video.ass
uv run -m src.main analyze-frames ./scenes/
uv run -m src.main search "button click workflow"
```

### Python API

```python
from vlmrag import SubtitleProcessor, SceneDetector, FrameAnalyzer

# Process subtitles
processor = SubtitleProcessor()
topics = processor.extract_topics("video.ass")

# Detect scenes
detector = SceneDetector()
scenes = detector.create_scene_list(topics)

# Analyze frames
analyzer = FrameAnalyzer()
results = analyzer.process_scenes(scenes, video_path)
```

---

## 8. Configuration

### Environment Variables

```env
# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2-vision

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/vlmrag

# Transcription (optional)
GROQ_API_KEY=gsk_xxx

# Processing
FRAME_DEDUP_THRESHOLD=5
MAX_FRAMES_PER_SCENE=5
```

### Config File (`config.yaml`)

```yaml
processing:
  scene_threshold: 27.0
  frames_per_scene: 3
  dedup_threshold: 5

vlm:
  model: llama3.2-vision
  temperature: 0.1
  max_tokens: 512

storage:
  vector_dim: 384
  index_type: hnsw
```

---

## 9. Related Documentation

| Document | Description |
|----------|-------------|
| [Architecture](./01_Architecture/Hybrid_Storage_Architecture.md) | Storage design with pgvector |
| [Pipeline](./02_Implementation/Orchestration_Pipeline.md) | Implementation details |
| [Screenshot Config](./03_Technical/Screenshot_Analysis_Config.md) | VLM optimization settings |
| [Daily Notes](../Daily/2026-03-01.md) | Original requirements |

---

## 10. Future Enhancements

- [ ] CrewAI agent for natural language video queries
- [ ] Real-time streaming analysis
- [ ] Multi-video correlation (find same UI across videos)
- [ ] Export to knowledge graph format
- [ ] Web UI for visual search
