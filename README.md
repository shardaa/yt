# YouTube Video Downloader

A Python-based YouTube video downloader with a clean web UI and CLI. Paste a URL, pick a quality, download.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-Web_UI-green)
![yt--dlp](https://img.shields.io/badge/yt--dlp-backend-red)

## Features

- Web UI with Google-search-style layout
- Quality selection (resolutions above 720p disabled by default)
- Real-time download progress bar
- Playlist support (CLI)
- Format conversion (CLI)
- Download resume on interruption
- Structured logging

## Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)

## Quick Start

### Option 1: Run script (easiest)

```bash
bash run.sh
```

This installs dependencies and starts the web server. Works on macOS, Windows (Git Bash), and Linux.

### Option 2: Manual setup

```bash
# 1. Install dependencies
pip install yt-dlp click flask

# 2. Start the web UI
python -m youtube_downloader.cli web --port 9090
```

### Option 3: CLI usage

```bash
# Download a video (best quality ≤720p)
python -m youtube_downloader.cli download "https://www.youtube.com/watch?v=VIDEO_ID"

# Download with specific resolution
python -m youtube_downloader.cli download "https://www.youtube.com/watch?v=VIDEO_ID" -r 480

# Download audio only
python -m youtube_downloader.cli download "https://www.youtube.com/watch?v=VIDEO_ID" --audio-only

# Download to a specific folder
python -m youtube_downloader.cli download "https://www.youtube.com/watch?v=VIDEO_ID" -o ~/Videos

# Download a playlist
python -m youtube_downloader.cli download "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

## Using the Web UI

1. Open http://localhost:9090
2. Paste a YouTube URL in the input field
3. Click **Search** — available qualities load in a dropdown
4. Select a quality (720p and below are enabled)
5. Click **Download** — progress bar shows real-time status
6. Click the download link when complete

## Project Structure

```
youtube_downloader/
├── cli.py                 # CLI entry point (Click)
├── web_app.py             # Flask web server + REST API
├── url_resolver.py        # YouTube URL validation & parsing
├── metadata_retriever.py  # Video metadata via yt-dlp
├── stream_selector.py     # Quality/format selection
├── download_engine.py     # Download with progress & resume
├── format_converter.py    # ffmpeg format conversion
├── progress_reporter.py   # Console progress display
├── playlist_downloader.py # Playlist orchestration
├── logging_config.py      # Rotating log file setup
├── models.py              # Data models (dataclasses)
├── errors.py              # Error hierarchy
├── templates/
│   └── index.html         # Web UI page
└── static/
    ├── style.css           # Styles
    └── app.js              # Frontend logic
```

## CLI Reference

```
Usage: python -m youtube_downloader.cli [COMMAND]

Commands:
  download  Download a YouTube video or playlist
  web       Start the web UI server

Download options:
  -o, --output-dir TEXT   Directory to save files (default: ./downloads)
  -r, --resolution INT    Max resolution in pixels (e.g. 720, 480)
  -f, --format TEXT       Container format (mp4, webm)
  --audio-only            Download audio only

Web options:
  -p, --port INT          Server port (default: 9090)
  -o, --output-dir TEXT   Directory to save files (default: ./downloads)
```

## Deploying to Oracle Cloud (Free)

See [deploy/README.md](deploy/README.md) for a step-by-step guide to deploy on an always-free Oracle Cloud VM.

## Troubleshooting

**Downloads are slow:**
- Try a lower resolution (480p or 360p)
- Check your internet connection

**"Requested format not available" error:**
- The selected format/resolution isn't available for this video
- Try a different quality or let it auto-select

**Port 9090 already in use:**
- Use a different port: `python -m youtube_downloader.cli web --port 8080`
