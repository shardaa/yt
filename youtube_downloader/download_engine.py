"""Download engine with progress tracking and resume support."""

import logging
import os
import re
import shutil
import unicodedata
from collections.abc import Callable

import yt_dlp

from youtube_downloader.errors import DiskSpaceError, NetworkError
from youtube_downloader.models import (
    ConflictResolution,
    DownloadProgress,
    DownloadResult,
    Stream,
)

logger = logging.getLogger(__name__)

# Reserved filenames on Windows
_WINDOWS_RESERVED = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
)

_MAX_FILENAME_LENGTH = 200


def sanitize_filename(name: str, extension: str) -> str:
    """Sanitize a string into a valid filename and append the given extension.

    Steps:
    1. Normalize unicode to NFKD and strip non-ASCII combining marks.
    2. Strip path separators (``/``, ``\\``) and other special characters.
    3. Replace reserved characters with underscores.
    4. Collapse consecutive underscores / whitespace.
    5. Truncate to ``_MAX_FILENAME_LENGTH`` characters (before extension).
    6. Avoid OS-reserved names by prefixing with an underscore.
    7. Append the correct file extension.

    Always returns a non-empty filename.
    """
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    # Remove combining characters (accents etc.) but keep base letters
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Remove path separators
    name = name.replace("/", " ").replace("\\", " ")

    # Strip characters that are problematic on common OSes
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)

    # Collapse whitespace and underscores
    name = re.sub(r"[\s_]+", "_", name).strip("_. ")

    # Truncate
    if len(name) > _MAX_FILENAME_LENGTH:
        name = name[:_MAX_FILENAME_LENGTH].rstrip("_. ")

    # Avoid reserved names (case-insensitive check)
    stem_upper = name.upper()
    if stem_upper in _WINDOWS_RESERVED or stem_upper.split(".")[0] in _WINDOWS_RESERVED:
        name = f"_{name}"

    # Fallback for empty result
    if not name:
        name = "download"

    # Ensure extension starts with a dot
    if extension and not extension.startswith("."):
        extension = f".{extension}"

    return f"{name}{extension}"


class DownloadEngine:
    """Downloads video/audio streams with progress tracking and resume support."""

    def __init__(
        self,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> None:
        self._progress_callback = progress_callback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        stream: Stream,
        output_dir: str,
        filename: str,
        on_conflict: ConflictResolution = ConflictResolution.ASK,
    ) -> DownloadResult:
        """Download a stream to *output_dir*.

        Args:
            stream: The stream to download.
            output_dir: Target directory (created if missing).
            filename: Desired filename **without** extension.
            on_conflict: How to handle an existing file with the same name.

        Returns:
            A ``DownloadResult`` describing the outcome.

        Raises:
            DiskSpaceError: Not enough disk space for the download.
            NetworkError: After retry exhaustion.
        """
        # 1. Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # 2. Sanitize filename and build full path
        safe_name = sanitize_filename(filename, stream.container)
        dest_path = os.path.join(output_dir, safe_name)

        # 3. Check disk space
        if stream.file_size is not None:
            self._check_disk_space(output_dir, stream.file_size)

        # 4. Handle file conflicts
        dest_path = self._resolve_conflict(dest_path, on_conflict)
        if dest_path is None:
            # CANCEL was chosen
            return DownloadResult(
                success=False,
                file_path=None,
                error_message="Download cancelled due to existing file.",
            )

        # 5. Download via yt-dlp
        return self._run_download(stream, dest_path, resumed=False)

    def resume_download(
        self,
        partial_file_path: str,
        stream: Stream,
    ) -> DownloadResult:
        """Resume a previously interrupted download.

        Args:
            partial_file_path: Path to the ``.part`` file.
            stream: The original stream metadata.

        Returns:
            A ``DownloadResult`` with the final file path and status.
        """
        if not os.path.exists(partial_file_path):
            logger.warning("Partial file not found: %s – starting fresh.", partial_file_path)
            output_dir = os.path.dirname(partial_file_path) or "."
            base = os.path.basename(partial_file_path)
            if base.endswith(".part"):
                base = base[: -len(".part")]
            stem, _ = os.path.splitext(base)
            return self.download(
                stream,
                output_dir,
                stem,
                on_conflict=ConflictResolution.OVERWRITE,
            )

        # Check if remote file changed by comparing expected size with what
        # yt-dlp reports.  If the expected size is known and the partial file
        # is already larger, the remote likely changed – discard and restart.
        partial_size = os.path.getsize(partial_file_path)
        if stream.file_size is not None and partial_size > stream.file_size:
            logger.warning(
                "Partial file (%d bytes) exceeds expected size (%d bytes). "
                "Remote file may have changed – restarting download.",
                partial_size,
                stream.file_size,
            )
            os.remove(partial_file_path)
            output_dir = os.path.dirname(partial_file_path) or "."
            base = os.path.basename(partial_file_path)
            if base.endswith(".part"):
                base = base[: -len(".part")]
            stem, _ = os.path.splitext(base)
            return self.download(
                stream,
                output_dir,
                stem,
                on_conflict=ConflictResolution.OVERWRITE,
            )

        # Derive the final destination from the .part path
        if partial_file_path.endswith(".part"):
            dest_path = partial_file_path[: -len(".part")]
        else:
            dest_path = partial_file_path

        logger.info(
            "Resuming download from byte %d for %s",
            partial_size,
            dest_path,
        )

        result = self._run_download(stream, dest_path, resumed=True)

        # Verify integrity after completion
        if result.success and result.file_path and stream.file_size is not None:
            actual_size = os.path.getsize(result.file_path)
            if actual_size != stream.file_size:
                msg = (
                    f"Integrity check failed: expected {stream.file_size} bytes, "
                    f"got {actual_size} bytes."
                )
                logger.error(msg)
                return DownloadResult(
                    success=False,
                    file_path=result.file_path,
                    error_message=msg,
                    was_resumed=True,
                )

        return DownloadResult(
            success=result.success,
            file_path=result.file_path,
            error_message=result.error_message,
            was_resumed=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_disk_space(self, directory: str, required_bytes: int) -> None:
        """Raise ``DiskSpaceError`` if *directory* lacks space."""
        usage = shutil.disk_usage(directory)
        if usage.free < required_bytes:
            raise DiskSpaceError(
                f"Insufficient disk space: need {required_bytes} bytes, "
                f"only {usage.free} bytes available.",
                required_bytes=required_bytes,
                available_bytes=usage.free,
            )

    def _resolve_conflict(
        self,
        dest_path: str,
        on_conflict: ConflictResolution,
    ) -> str | None:
        """Return the final destination path after applying conflict policy.

        Returns ``None`` when the caller should abort (CANCEL / ASK-cancel).
        """
        if not os.path.exists(dest_path):
            return dest_path

        if on_conflict == ConflictResolution.OVERWRITE:
            logger.info("Overwriting existing file: %s", dest_path)
            return dest_path

        if on_conflict == ConflictResolution.RENAME:
            return self._find_unique_path(dest_path)

        if on_conflict == ConflictResolution.CANCEL:
            logger.info("Download cancelled – file already exists: %s", dest_path)
            return None

        # ASK – default to rename in non-interactive contexts
        logger.info(
            "File already exists: %s – auto-renaming (ASK mode, non-interactive).",
            dest_path,
        )
        return self._find_unique_path(dest_path)

    @staticmethod
    def _find_unique_path(path: str) -> str:
        """Append a numeric suffix to *path* until it is unique."""
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def _make_progress_hook(self) -> Callable[[dict], None]:
        """Return a yt-dlp progress hook that forwards to our callback."""
        callback = self._progress_callback

        def hook(d: dict) -> None:
            if callback is None:
                return
            if d.get("status") != "downloading":
                return

            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed") or 0.0
            eta = d.get("eta")
            if total and total > 0:
                pct = min(downloaded / total * 100.0, 100.0)
            else:
                pct = 0.0

            callback(
                DownloadProgress(
                    bytes_downloaded=downloaded,
                    total_bytes=total,
                    speed_bytes_per_sec=float(speed),
                    eta_seconds=float(eta) if eta is not None else None,
                    percentage=pct,
                )
            )

        return hook

    def _run_download(
        self,
        stream: Stream,
        dest_path: str,
        *,
        resumed: bool,
    ) -> DownloadResult:
        """Execute the actual yt-dlp download."""
        output_dir = os.path.dirname(dest_path) or "."
        base_name = os.path.basename(dest_path)
        # yt-dlp output template – use the exact filename we computed
        outtmpl = os.path.join(output_dir, base_name)

        ydl_opts: dict = {
            "format": stream.format_id,
            "outtmpl": outtmpl,
            "noprogress": True,
            "continuedl": True,  # enable resume
            "retries": 3,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._make_progress_hook()],
        }

        # Use the YouTube video URL (not the raw CDN URL) so yt-dlp can
        # properly apply format selection via the "format" option.
        if stream.video_id:
            download_url = f"https://www.youtube.com/watch?v={stream.video_id}"
        else:
            download_url = stream.url

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download_url])
        except yt_dlp.utils.DownloadError as exc:
            msg = str(exc)
            logger.error("yt-dlp download failed: %s", msg)
            return DownloadResult(
                success=False,
                file_path=None,
                error_message=msg,
                was_resumed=resumed,
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected download error: {exc}"
            logger.error(msg)
            return DownloadResult(
                success=False,
                file_path=None,
                error_message=msg,
                was_resumed=resumed,
            )

        # yt-dlp may add its own extension – find the actual file
        final_path = self._locate_output_file(dest_path)

        if final_path is None:
            return DownloadResult(
                success=False,
                file_path=None,
                error_message=f"Downloaded file not found at expected path: {dest_path}",
                was_resumed=resumed,
            )

        logger.info("Download complete: %s", final_path)
        return DownloadResult(
            success=True,
            file_path=final_path,
            was_resumed=resumed,
        )

    @staticmethod
    def _locate_output_file(expected_path: str) -> str | None:
        """Return the actual output path, accounting for yt-dlp quirks."""
        if os.path.isfile(expected_path):
            return expected_path

        # yt-dlp sometimes appends a different extension
        directory = os.path.dirname(expected_path) or "."
        stem, _ = os.path.splitext(os.path.basename(expected_path))
        for entry in os.listdir(directory):
            if entry.startswith(stem) and not entry.endswith(".part"):
                candidate = os.path.join(directory, entry)
                if os.path.isfile(candidate):
                    return candidate

        return None
