"""Progress reporting for downloads and conversions."""

import sys
import time

from youtube_downloader.models import DownloadProgress


class ProgressReporter:
    """Reports progress for downloads, playlist operations, and conversions."""

    def __init__(self) -> None:
        self._last_report_time: float = 0.0

    def _format_bytes(self, num_bytes: float) -> str:
        """Format a byte count into a human-readable string."""
        for unit in ("B", "KB", "MB", "GB"):
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} TB"

    def _format_time(self, seconds: float) -> str:
        """Format seconds into mm:ss or hh:mm:ss."""
        seconds = int(seconds)
        if seconds < 3600:
            return f"{seconds // 60:02d}:{seconds % 60:02d}"
        hours = seconds // 3600
        remaining = seconds % 3600
        return f"{hours}:{remaining // 60:02d}:{remaining % 60:02d}"

    def report_download_progress(self, progress: DownloadProgress) -> None:
        """Display download progress to the console, throttled to ≤1s intervals."""
        now = time.monotonic()
        if now - self._last_report_time < 1.0:
            return

        self._last_report_time = now

        downloaded = self._format_bytes(progress.bytes_downloaded)
        speed = self._format_bytes(progress.speed_bytes_per_sec) + "/s"

        parts = [f"\r  {progress.percentage:5.1f}%  |  {downloaded}"]

        if progress.total_bytes is not None and progress.total_bytes > 0:
            total = self._format_bytes(progress.total_bytes)
            parts.append(f" / {total}")

        parts.append(f"  |  {speed}")

        if progress.eta_seconds is not None:
            eta = self._format_time(progress.eta_seconds)
            parts.append(f"  |  ETA {eta}")

        line = "".join(parts)
        sys.stdout.write(line + "  ")
        sys.stdout.flush()

    def report_playlist_progress(
        self, current_index: int, total: int, video_title: str
    ) -> None:
        """Display playlist-level progress."""
        print(f"\n[{current_index}/{total}] Downloading: {video_title}")

    def report_conversion_progress(self, percentage: float) -> None:
        """Display format conversion progress."""
        sys.stdout.write(f"\r  Converting: {percentage:5.1f}%  ")
        sys.stdout.flush()
