# Implementation Plan: YouTube Video Downloader

## Overview

Build a Python CLI application that downloads YouTube videos using yt-dlp and ffmpeg, with an optional web UI for browser-based access. The implementation follows a modular pipeline architecture: URL validation → metadata retrieval → stream selection → download with progress → optional format conversion. The web UI provides a minimal, Google-search-style page with a centered URL input and download button, backed by a Flask REST API that reuses the core pipeline. Each component is implemented as a separate module with well-defined interfaces, tested incrementally.

## Tasks

- [x] 1. Set up project structure, data models, and error hierarchy
  - [x] 1.1 Create project directory structure and configuration files
    - Create the package directory layout: `youtube_downloader/` with `__init__.py`, `cli.py`, `models.py`, `errors.py`, `url_resolver.py`, `metadata_retriever.py`, `stream_selector.py`, `download_engine.py`, `format_converter.py`, `progress_reporter.py`, `web_app.py`
    - Create `youtube_downloader/templates/` directory for HTML templates and `youtube_downloader/static/` directory for CSS and JS files
    - Create `pyproject.toml` with dependencies: `yt-dlp`, `click` (for CLI), `flask`, `pytest`, `hypothesis`, `pytest-mock`, `pytest-cov`
    - Create `tests/` directory with `__init__.py`, `conftest.py`
    - _Requirements: All_

  - [x] 1.2 Implement data models in `models.py`
    - Define all dataclasses: `ResolvedURL`, `Stream`, `VideoMetadata`, `DownloadProgress`, `DownloadResult`, `ConversionResult`, `PlaylistDownloadSummary`
    - Define enums: `URLType`, `ConflictResolution`
    - _Requirements: 1.1, 2.1, 2.2, 4.2, 5.4, 6.5_

  - [x] 1.3 Implement error hierarchy in `errors.py`
    - Define all exception classes: `DownloaderError`, `InvalidURLError`, `VideoUnavailableError`, `NetworkError`, `NoMatchingStreamError`, `DiskSpaceError`, `ConversionError`, `UnsupportedFormatError`
    - Include relevant attributes on each exception (e.g., `reason` on `VideoUnavailableError`, `required_bytes`/`available_bytes` on `DiskSpaceError`)
    - _Requirements: 1.4, 1.5, 7.1, 7.2, 7.4, 8.4_

  - [ ]* 1.4 Write unit tests for data models and error hierarchy
    - Test dataclass instantiation and frozen immutability
    - Test enum values
    - Test exception inheritance chain
    - _Requirements: 2.1, 2.2, 7.2_

- [x] 2. Implement URL Resolver
  - [x] 2.1 Implement `URLResolver` class in `url_resolver.py`
    - Define regex patterns for valid YouTube URL formats: standard watch URLs, short-form youtu.be, embed URLs, shorts URLs, playlist URLs
    - Implement `validate_and_resolve(url)` method that extracts video/playlist identifiers
    - Raise `InvalidURLError` for unrecognized formats
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write property test: Valid YouTube URL extraction
    - **Property 1: Valid YouTube URL extraction**
    - Generate random video IDs (11 alphanumeric chars), embed in random valid URL templates (watch?v=, youtu.be/, embed/, shorts/) with random query params
    - Assert extracted video ID matches the generated ID
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 2.3 Write property test: Playlist URL identification and extraction
    - **Property 2: Playlist URL identification and extraction**
    - Generate random playlist IDs, embed in playlist URL templates with varying params
    - Assert URL type is PLAYLIST and extracted playlist ID matches
    - **Validates: Requirements 1.3**

  - [ ]* 2.4 Write property test: Invalid URL rejection
    - **Property 3: Invalid URL rejection**
    - Generate random strings, non-YouTube domain URLs, malformed URLs
    - Assert `InvalidURLError` is raised for all inputs
    - **Validates: Requirements 1.4**

  - [ ]* 2.5 Write unit tests for URL Resolver
    - Test specific URL formats: standard, short, playlist, with timestamps, with extra params
    - Test specific invalid inputs: empty string, non-URL text, other-site URLs
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 3. Implement Metadata Retriever
  - [x] 3.1 Implement `MetadataRetriever` class in `metadata_retriever.py`
    - Implement `get_metadata(video_id)` using yt-dlp's extraction API (`yt_dlp.YoutubeDL.extract_info`)
    - Map yt-dlp info dict fields to `VideoMetadata` and `Stream` dataclasses
    - Implement retry logic with exponential backoff (max 3 retries, base 1s)
    - Raise `NetworkError` after retry exhaustion, `VideoUnavailableError` for inaccessible videos
    - _Requirements: 2.1, 2.2, 2.3, 1.5_

  - [ ]* 3.2 Write property test: Metadata extraction completeness
    - **Property 4: Metadata extraction completeness**
    - Generate random yt-dlp info dicts with varying fields and format lists
    - Assert produced `VideoMetadata` has non-null title, duration, thumbnail_url, upload_date, and streams with required fields
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 3.3 Write unit tests for Metadata Retriever
    - Test retry behavior: mock 3 failures then success, mock 4 failures for error
    - Test exponential backoff timing
    - Test `VideoUnavailableError` for private/deleted/region-locked videos
    - _Requirements: 2.1, 2.2, 2.3, 1.5_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Stream Selector
  - [x] 5.1 Implement `StreamSelector` class in `stream_selector.py`
    - Implement `list_streams(metadata, audio_only)` that returns streams sorted by resolution (desc) or bitrate (desc for audio-only)
    - Implement `select_stream(metadata, preferred_resolution, preferred_format, audio_only)` that selects the best matching stream
    - For preferred resolution: select closest available resolution that does not exceed the preferred value
    - Raise `NoMatchingStreamError` when no stream matches criteria
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 5.2 Write property test: Stream sorting by resolution
    - **Property 5: Stream sorting by resolution**
    - Generate random lists of Stream objects with random resolutions
    - Assert returned list is sorted by resolution in descending order
    - **Validates: Requirements 3.1**

  - [ ]* 5.3 Write property test: Closest resolution selection
    - **Property 6: Closest resolution selection without exceeding preferred value**
    - Generate random stream lists + random preferred resolution integers
    - Assert selected stream resolution <= preferred value and no better candidate exists
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 5.4 Write property test: Audio-only stream filtering and sorting
    - **Property 7: Audio-only stream filtering and sorting**
    - Generate mixed lists of audio-only and video Stream objects
    - Assert only audio-only streams returned, sorted by bitrate descending
    - **Validates: Requirements 3.5**

  - [ ]* 5.5 Write unit tests for Stream Selector
    - Test format support (mp4, webm, mp3 in SUPPORTED_FORMATS)
    - Test empty stream list handling
    - Test no-match scenarios raising `NoMatchingStreamError`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Implement Download Engine
  - [x] 6.1 Implement `DownloadEngine` class in `download_engine.py`
    - Implement `download(stream, output_dir, filename, on_conflict)` using yt-dlp's download functionality
    - Implement filename sanitization: strip special characters, path separators, handle unicode, truncate long names, avoid OS-reserved names, append correct extension
    - Create output directory if it doesn't exist
    - Handle file conflict resolution (overwrite, rename, cancel, ask)
    - Wire progress callback for `DownloadProgress` reporting
    - Check available disk space before download, raise `DiskSpaceError` if insufficient
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.4_

  - [x] 6.2 Implement `resume_download` method
    - Detect existing `.part` files and resume from last byte position
    - Verify remote file hasn't changed since partial download began; discard and restart if changed
    - Verify completed download integrity by comparing file size against expected Stream metadata size
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 6.3 Write property test: Filename sanitization
    - **Property 8: Filename sanitization produces valid filenames**
    - Generate random strings with special chars, unicode, path separators, OS-reserved names, very long strings
    - Assert output is non-empty, valid filename on target OS, has correct extension
    - **Validates: Requirements 4.3**

  - [ ]* 6.4 Write property test: Download integrity verification
    - **Property 9: Download integrity verification**
    - Generate random pairs of (expected_size, actual_size) integers
    - Assert integrity check passes iff sizes are equal
    - **Validates: Requirements 5.4**

  - [ ]* 6.5 Write unit tests for Download Engine
    - Test directory creation when output dir doesn't exist
    - Test conflict resolution modes (overwrite, rename, cancel)
    - Test progress callback intervals (≤1 second)
    - Test disk space check and `DiskSpaceError`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 7.4_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Format Converter
  - [x] 8.1 Implement `FormatConverter` class in `format_converter.py`
    - Implement `convert(input_path, target_format, progress_callback)` using ffmpeg via subprocess
    - Validate target format against `SUPPORTED_FORMATS` (mp4, mkv, avi, mp3, wav), raise `UnsupportedFormatError` if invalid
    - Parse ffmpeg stderr output to extract progress percentage and invoke callback
    - On failure: retain original file, raise `ConversionError` with ffmpeg stderr
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 8.2 Write unit tests for Format Converter
    - Test supported format validation (mp4, mkv, avi, mp3, wav)
    - Test conversion failure retains original file
    - Test progress percentage bounds (0.0 to 100.0)
    - Test `UnsupportedFormatError` for invalid formats
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 9. Implement Progress Reporter
  - [x] 9.1 Implement `ProgressReporter` class in `progress_reporter.py`
    - Implement `report_download_progress(progress)` with console output throttled to ≤1s intervals
    - Implement `report_playlist_progress(current_index, total, video_title)` for playlist-level progress
    - Implement `report_conversion_progress(percentage)` for format conversion progress
    - _Requirements: 4.2, 6.3, 8.3_

- [x] 10. Implement Playlist Download Logic and Summary
  - [x] 10.1 Implement playlist download orchestration
    - Download each video sequentially using selected quality preference
    - On individual video failure after retries: log the failure, skip the video, continue with remaining
    - Track successful and failed downloads
    - Build and return `PlaylistDownloadSummary` at completion
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 10.2 Write property test: Playlist download summary accuracy
    - **Property 10: Playlist download summary accuracy**
    - Generate random lists of (title, success/failure) tuples
    - Assert total_videos == len(successful) + len(failed), successful list matches expected, failed list matches expected
    - **Validates: Requirements 6.3, 6.5**

  - [ ]* 10.3 Write unit tests for playlist download
    - Test sequential download order
    - Test skip-on-failure behavior
    - Test summary display with mixed success/failure
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 11. Implement Logging and CLI Entry Point
  - [x] 11.1 Set up structured logging
    - Configure Python `logging` module with rotating file handler (max 5MB, 3 backups)
    - Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
    - Log to both console (INFO+) and file (DEBUG+)
    - Log file location: `youtube_downloader.log` in the output directory
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 11.2 Implement CLI entry point in `cli.py`
    - Wire all components together using Click for argument parsing
    - Accept arguments: URL, output directory, preferred resolution, preferred format, audio-only flag
    - Orchestrate the full pipeline: validate URL → fetch metadata → display metadata → select stream → download → offer conversion
    - Handle playlist URLs: display video list, confirm, download sequentially, show summary
    - Display human-readable error messages for all `DownloaderError` subclasses
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 3.1, 3.2, 4.1, 6.1, 6.2, 7.2, 8.1_

- [ ] 12. Integration tests and final wiring
  - [ ]* 12.1 Write integration tests
    - Test video unavailability flow: mock yt-dlp returning private/deleted/region-locked errors
    - Test download resume flow: mock interrupted downloads, verify resume from correct byte position, verify stale file detection
    - Test disk space handling: mock disk full errors, verify pause and notification
    - Test playlist error resilience: mock playlist with one failing video, verify skip and continue
    - Test format conversion flow: mock ffmpeg subprocess, verify conversion and error handling
    - Test web UI end-to-end: use Flask test client to submit URL, poll progress, verify download link or error
    - _Requirements: 1.5, 5.1, 5.2, 5.3, 6.4, 7.4, 8.1, 8.2, 8.3, 8.4, 9.3, 9.4, 9.5, 9.6_

- [x] 13. Implement Web UI
  - [x] 13.1 Create Flask application and REST API in `web_app.py`
    - Create `youtube_downloader/web_app.py` with Flask app
    - Implement `GET /` route to serve the main HTML page
    - Implement `POST /api/download` route that accepts `{"url": "<youtube_url>"}`, validates the URL using `URLResolver`, fetches metadata via `MetadataRetriever`, selects best stream via `StreamSelector`, starts download in a background thread using `DownloadEngine`, returns `{"task_id": "<uuid>", "title": "<video_title>"}` on success or `{"error": "<message>"}` with 400/500 status on failure
    - Implement `GET /api/progress/<task_id>` route that returns `{"status": "downloading"|"complete"|"error", "percentage": float, "download_url": str|null, "error": str|null}`
    - Implement `GET /api/files/<filename>` route to serve downloaded files using `send_from_directory`
    - Use an in-memory dict to track download tasks and their progress
    - Implement `run_server(port, output_dir)` function to start the Flask server
    - _Requirements: 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 13.2 Create HTML template `templates/index.html`
    - Create `youtube_downloader/templates/index.html`
    - Build a single-page layout with full viewport height, vertically and horizontally centered content using flexbox
    - Add an application title at the top of the centered block
    - Add a wide URL input field with placeholder "Paste YouTube URL here"
    - Add a styled download button below the input
    - Add a hidden results section that shows: progress bar during download, download link on success, error message on failure
    - Link to `static/style.css` and `static/app.js`
    - _Requirements: 9.1, 9.2_

  - [x] 13.3 Create CSS styles `static/style.css`
    - Create `youtube_downloader/static/style.css`
    - Style the page with a clean, minimal Google-search-inspired layout
    - Center content vertically and horizontally using flexbox on the body
    - Style the input field: wide (min 500px), rounded border, padding, focus outline
    - Style the download button: prominent color, rounded, hover effect
    - Style the progress bar: horizontal bar with percentage fill and label
    - Style error messages: red text below the input area
    - Style the download link: visible, clickable link after successful download
    - _Requirements: 9.1, 9.2_

  - [x] 13.4 Create JavaScript `static/app.js`
    - Create `youtube_downloader/static/app.js`
    - Handle form submission: prevent default, read URL from input, POST to `/api/download` via `fetch()`
    - On successful submission: show progress area, start polling `GET /api/progress/{task_id}` every 1 second
    - Update progress bar with current percentage on each poll
    - On download complete: stop polling, show download link pointing to `/api/files/{filename}`
    - On error (400/500 from submit or error status from progress): stop polling, display error message below input
    - Disable the download button while a download is in progress, re-enable on completion or error
    - _Requirements: 9.3, 9.4, 9.5, 9.6_

  - [x] 13.5 Add `web` command to CLI entry point
    - Add a `web` subcommand to `cli.py` using Click that starts the Flask server
    - Accept options: `--port` (default 5000), `--output-dir` (default `./downloads`)
    - Call `run_server(port, output_dir)` from `web_app.py`
    - _Requirements: 9.7_

  - [ ]* 13.6 Write unit tests for Web UI
    - Test Flask routes using `app.test_client()`
    - Test `GET /` returns 200 with HTML content
    - Test `POST /api/download` with valid URL (mocked backend) returns 201 with task_id
    - Test `POST /api/download` with invalid URL returns 400 with error message
    - Test `GET /api/progress/<task_id>` with known task returns progress data
    - Test `GET /api/progress/<unknown_id>` returns 404
    - Test `GET /api/files/<filename>` serves the correct file
    - _Requirements: 9.1, 9.3, 9.4, 9.5, 9.6, 9.7_

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All external dependencies (yt-dlp, ffmpeg) are mocked in tests
