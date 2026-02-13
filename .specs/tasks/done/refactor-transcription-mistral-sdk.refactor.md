---
title: Refactor transcription to use Mistral AI Python SDK
---

## Initial User Prompt

refactor the transcription function to use the mistralai python sdk instead of http api

# Description

The application currently uses inconsistent patterns for Mistral AI integration - while a Mistral SDK client is properly initialized (`client = Mistral(api_key=api_key)`), the `transcribe_audio()` function still uses raw HTTP API calls with `requests.post()`. This creates technical debt and maintenance challenges.

This refactor will modernize the transcription implementation to use the official Mistral AI Python SDK, providing better error handling, type safety, and consistency with the rest of the codebase. The SDK is already installed and imported, but not utilized for the core transcription functionality.

The refactor must maintain complete backward compatibility - all existing functionality including granularity control ("word"/"segment"), speaker diarization, retry logic, and response format must be preserved exactly. This ensures no changes are required in the UI components (`tabs/vo_subtitles.py`, `tabs/multilingual.py`, `tabs/transcription.py`) that depend on this function.

**Scope**:
- Included: Refactor `transcribe_audio()` function in `utils.py` to use Mistral SDK instead of HTTP calls
- Excluded: Function signature changes, UI modifications, performance optimization, new transcription features

**User Scenarios**:
1. **Primary Flow**: Application calls transcribe_audio() with audio file, receives identical transcription results via SDK
2. **Alternative Flow**: Function works with both granularity options ("word", "segment") and diarization on/off
3. **Error Handling**: Network failures, file issues, and API errors handled with same retry logic as current implementation

---

## Acceptance Criteria

Clear, testable criteria using Given/When/Then format:

### Functional Requirements

- [ ] **SDK Integration**: transcribe_audio() function uses Mistral SDK client instead of requests.post
  - Given: Mistral client is initialized and audio file exists
  - When: transcribe_audio() is called with valid parameters
  - Then: Function uses SDK methods instead of raw HTTP calls

- [ ] **Granularity Parameter Support**: Both "word" and "segment" granularity options work identically to current implementation
  - Given: Valid audio file and transcribe_audio() function
  - When: Function called with granularity="word" or granularity="segment"
  - Then: Response contains appropriate timestamp granularity data matching current behavior

- [ ] **Diarization Parameter Support**: Speaker diarization toggle works identically to current implementation  
  - Given: Valid audio file and transcribe_audio() function
  - When: Function called with diarize=True or diarize=False
  - Then: Response includes/excludes speaker identification data as expected

- [ ] **Response Format Compatibility**: Function returns data in identical format to current implementation
  - Given: Same audio file and parameters as current implementation
  - When: SDK-based transcribe_audio() is called
  - Then: Response structure is identical to current HTTP-based implementation

- [ ] **Error Handling Preservation**: Retry logic and error handling work as effectively as current implementation
  - Given: Network issues, file problems, or API errors occur
  - When: transcribe_audio() encounters these errors
  - Then: Function retries appropriately and handles errors gracefully

- [ ] **Function Signature Preservation**: Public API remains unchanged for backward compatibility
  - Given: Existing code that calls transcribe_audio()
  - When: Refactored function is used
  - Then: No changes required in calling code

### Non-Functional Requirements

- [ ] **Performance**: Transcription latency does not increase significantly (within 10% of current implementation)
- [ ] **Code Quality**: Implementation is cleaner and more maintainable using SDK methods
- [ ] **Compatibility**: Supports all current audio formats (MP3, WAV, OGG, FLAC, AAC)

### Definition of Done

- [ ] All acceptance criteria pass
- [ ] Manual testing confirms identical transcription results
- [ ] Code review confirms improved maintainability  
- [ ] No requests.post calls remain for transcription in utils.py
