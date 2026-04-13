"""Playlist download orchestration."""

import logging

from youtube_downloader.download_engine import DownloadEngine
from youtube_downloader.errors import DownloaderError
from youtube_downloader.metadata_retriever import MetadataRetriever
from youtube_downloader.models import (
    ConflictResolution,
    PlaylistDownloadSummary,
    ResolvedURL,
)
from youtube_downloader.progress_reporter import ProgressReporter
from youtube_downloader.stream_selector import StreamSelector

logger = logging.getLogger(__name__)


class PlaylistDownloader:
    """Orchestrates downloading all videos in a playlist."""

    def __init__(
        self,
        metadata_retriever: MetadataRetriever,
        stream_selector: StreamSelector,
        download_engine: DownloadEngine,
        progress_reporter: ProgressReporter,
    ) -> None:
        self._metadata_retriever = metadata_retriever
        self._stream_selector = stream_selector
        self._download_engine = download_engine
        self._progress_reporter = progress_reporter

    def download_playlist(
        self,
        resolved_url: ResolvedURL,
        output_dir: str,
        preferred_resolution: int | None = None,
        preferred_format: str | None = None,
        audio_only: bool = False,
        on_conflict: ConflictResolution = ConflictResolution.RENAME,
    ) -> PlaylistDownloadSummary:
        """Download all videos in a playlist sequentially.

        Args:
            resolved_url: A resolved playlist URL containing video IDs.
            output_dir: Directory to save downloaded files.
            preferred_resolution: Max resolution in pixels (e.g., 1080).
            preferred_format: Desired container format.
            audio_only: If True, download audio-only streams.
            on_conflict: How to handle existing files.

        Returns:
            A PlaylistDownloadSummary with results for every video.
        """
        video_ids = resolved_url.video_ids
        total = len(video_ids)
        successful: list[str] = []
        failed: list[tuple[str, str]] = []

        logger.info(
            "Starting playlist download: %d videos, output_dir=%s",
            total,
            output_dir,
        )

        for index, video_id in enumerate(video_ids, start=1):
            title = video_id  # fallback if metadata fetch fails
            try:
                metadata = self._metadata_retriever.get_metadata(video_id)
                title = metadata.title

                self._progress_reporter.report_playlist_progress(
                    index, total, title
                )

                stream = self._stream_selector.select_stream(
                    metadata,
                    preferred_resolution=preferred_resolution,
                    preferred_format=preferred_format,
                    audio_only=audio_only,
                )

                result = self._download_engine.download(
                    stream=stream,
                    output_dir=output_dir,
                    filename=title,
                    on_conflict=on_conflict,
                )

                if result.success:
                    logger.info("Downloaded [%d/%d]: %s", index, total, title)
                    successful.append(title)
                else:
                    error_msg = result.error_message or "Unknown download error"
                    logger.warning(
                        "Failed [%d/%d]: %s - %s", index, total, title, error_msg
                    )
                    failed.append((title, error_msg))

            except DownloaderError as exc:
                error_msg = str(exc)
                logger.warning(
                    "Failed [%d/%d]: %s - %s", index, total, title, error_msg
                )
                failed.append((title, error_msg))
            except Exception as exc:
                error_msg = f"Unexpected error: {exc}"
                logger.error(
                    "Failed [%d/%d]: %s - %s", index, total, title, error_msg
                )
                failed.append((title, error_msg))

        summary = PlaylistDownloadSummary(
            total_videos=total,
            successful=successful,
            failed=failed,
        )

        logger.info(
            "Playlist download complete: %d/%d succeeded, %d failed",
            len(successful),
            total,
            len(failed),
        )

        return summary
