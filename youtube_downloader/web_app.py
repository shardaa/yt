"""Flask web application for browser-based video downloading."""

import logging
import os
import threading
import uuid

from flask import Flask, jsonify, request, send_from_directory

from youtube_downloader.download_engine import DownloadEngine, sanitize_filename
from youtube_downloader.errors import DownloaderError, InvalidURLError
from youtube_downloader.metadata_retriever import MetadataRetriever
from youtube_downloader.models import ConflictResolution, DownloadProgress
from youtube_downloader.stream_selector import StreamSelector
from youtube_downloader.url_resolver import URLResolver

logger = logging.getLogger(__name__)

# In-memory task store for tracking download progress
download_tasks: dict[str, dict] = {}

# Global output directory, set by run_server()
_output_dir: str = "./downloads"


def create_app(output_dir: str = "./downloads") -> Flask:
    """Create and configure the Flask application."""
    global _output_dir
    _output_dir = output_dir

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    @app.route("/")
    def index() -> str:
        """Serve the main page with centered URL input and download button."""
        template_path = os.path.join(app.template_folder, "index.html")  # type: ignore[arg-type]
        with open(template_path) as f:
            return f.read()

    @app.route("/api/metadata", methods=["POST"])
    def get_metadata_api() -> tuple:
        """Fetch available resolutions for a YouTube URL.

        Request body: {"url": "<youtube_url>"}
        Returns 200: {"video_id", "title", "resolutions": [{height, label, disabled}]}
        """
        data = request.get_json(silent=True)
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' in request body"}), 400

        url = data["url"]
        resolver = URLResolver()
        try:
            resolved = resolver.validate_and_resolve(url)
        except InvalidURLError as exc:
            return jsonify({"error": str(exc)}), 400

        video_id = resolved.video_ids[0]
        retriever = MetadataRetriever()
        try:
            metadata = retriever.get_metadata(video_id)
        except DownloaderError as exc:
            return jsonify({"error": str(exc)}), 500

        # Collect unique resolutions from video streams
        seen: set[int] = set()
        resolutions: list[dict] = []
        for s in metadata.streams:
            if s.is_audio_only or s.resolution is None:
                continue
            if s.resolution in seen:
                continue
            seen.add(s.resolution)
            resolutions.append({
                "height": s.resolution,
                "label": f"{s.resolution}p",
                "disabled": s.resolution > 720,
            })

        resolutions.sort(key=lambda r: r["height"], reverse=True)

        # Add audio-only option
        resolutions.append({"height": 0, "label": "Audio only", "disabled": False})

        return jsonify({
            "video_id": metadata.video_id,
            "title": metadata.title,
            "resolutions": resolutions,
        }), 200

    @app.route("/api/download", methods=["POST"])
    def start_download() -> tuple:
        """Start a video download with a chosen resolution.

        Request body: {"video_id": "...", "title": "...", "height": 720}
        """
        data = request.get_json(silent=True)
        if not data or "video_id" not in data:
            return jsonify({"error": "Missing 'video_id' in request body"}), 400

        video_id = data["video_id"]
        title = data.get("title", video_id)
        height = data.get("height", 720)

        task_id = str(uuid.uuid4())
        download_tasks[task_id] = {
            "status": "downloading",
            "percentage": 0.0,
            "download_url": None,
            "error": None,
        }

        thread = threading.Thread(
            target=_run_download_direct,
            args=(task_id, video_id, title, _output_dir, height),
            daemon=True,
        )
        thread.start()

        return jsonify({"task_id": task_id, "title": title}), 201

    @app.route("/api/progress/<task_id>")
    def get_progress(task_id: str) -> tuple:
        """
        Get download progress for a task.

        Returns:
            200: {"status": ..., "percentage": ..., "download_url": ..., "error": ...}
            404: {"error": "Task not found"}
        """
        task = download_tasks.get(task_id)
        if task is None:
            return jsonify({"error": "Task not found"}), 404

        return jsonify({
            "status": task["status"],
            "percentage": task["percentage"],
            "download_url": task["download_url"],
            "error": task["error"],
        }), 200

    @app.route("/api/files/<filename>")
    def serve_file(filename: str):
        """Serve a downloaded file for the user to save."""
        return send_from_directory(
            os.path.abspath(_output_dir),
            filename,
            as_attachment=True,
        )

    return app


def _run_download(
    task_id: str,
    stream,
    title: str,
    output_dir: str,
) -> None:
    """Execute a download in a background thread, updating task progress."""

    def progress_callback(progress: DownloadProgress) -> None:
        task = download_tasks.get(task_id)
        if task is not None:
            task["percentage"] = progress.percentage

    engine = DownloadEngine(progress_callback=progress_callback)

    try:
        result = engine.download(
            stream=stream,
            output_dir=output_dir,
            filename=title,
            on_conflict=ConflictResolution.RENAME,
        )

        task = download_tasks.get(task_id)
        if task is None:
            return

        if result.success and result.file_path:
            filename = os.path.basename(result.file_path)
            task["status"] = "complete"
            task["percentage"] = 100.0
            task["download_url"] = f"/api/files/{filename}"
        else:
            task["status"] = "error"
            task["error"] = result.error_message or "Download failed"

    except Exception as exc:
        logger.exception("Background download failed for task %s", task_id)
        task = download_tasks.get(task_id)
        if task is not None:
            task["status"] = "error"
            task["error"] = str(exc)


def _run_download_direct(
    task_id: str,
    video_id: str,
    title: str,
    output_dir: str,
    height: int = 720,
) -> None:
    """Download using yt-dlp directly with best combined format at chosen resolution."""
    import yt_dlp as _yt_dlp

    os.makedirs(output_dir, exist_ok=True)

    def progress_hook(d: dict) -> None:
        task = download_tasks.get(task_id)
        if task is None or d.get("status") != "downloading":
            return
        downloaded = d.get("downloaded_bytes", 0) or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if total and total > 0:
            task["percentage"] = min(downloaded / total * 100.0, 100.0)

    if height == 0:
        fmt = "bestaudio/best"
    else:
        # Only use pre-muxed streams (no ffmpeg required)
        # These are single files with video+audio already combined
        fmt = f"best[height<={height}]/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "noprogress": True,
        "quiet": False,
        "no_warnings": False,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "buffersize": 1024 * 64,
        "http_chunk_size": 10485760,  # 10 MB chunks
        "progress_hooks": [progress_hook],
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with _yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        task = download_tasks.get(task_id)
        if task is None:
            return

        if info:
            filename = ydl.prepare_filename(info)
            # After merge the extension may differ — check .mp4 too
            candidates = [filename]
            base, _ = os.path.splitext(filename)
            candidates.append(base + ".mp4")
            candidates.append(base + ".mkv")
            candidates.append(base + ".webm")

            for candidate in candidates:
                if os.path.isfile(candidate):
                    basename = os.path.basename(candidate)
                    task["status"] = "complete"
                    task["percentage"] = 100.0
                    task["download_url"] = f"/api/files/{basename}"
                    return

            # Fallback: scan output dir for file starting with title
            for entry in os.listdir(output_dir):
                if not entry.endswith(".part") and title[:20] in entry:
                    task["status"] = "complete"
                    task["percentage"] = 100.0
                    task["download_url"] = f"/api/files/{entry}"
                    return

        task["status"] = "error"
        task["error"] = "Download completed but file not found"

    except Exception as exc:
        logger.exception("Background download failed for task %s", task_id)
        task = download_tasks.get(task_id)
        if task is not None:
            task["status"] = "error"
            task["error"] = str(exc)


def run_server(port: int = 5000, output_dir: str = "./downloads") -> None:
    """Start the Flask development server."""
    os.makedirs(output_dir, exist_ok=True)
    app = create_app(output_dir=output_dir)
    app.run(host="0.0.0.0", port=port, debug=False)
