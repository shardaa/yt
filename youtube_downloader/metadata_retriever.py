"""Video metadata retrieval via yt-dlp."""

import logging
import time

import yt_dlp

from youtube_downloader.errors import NetworkError, VideoUnavailableError
from youtube_downloader.models import Stream, VideoMetadata

logger = logging.getLogger(__name__)


class MetadataRetriever:
    """Retrieves video metadata from YouTube via yt-dlp."""

    def __init__(self, max_retries: int = 3, backoff_base: float = 1.0) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def get_metadata(self, video_id: str) -> VideoMetadata:
        """
        Fetch metadata for a single video.

        Args:
            video_id: YouTube video identifier.

        Returns:
            VideoMetadata including title, duration, streams, etc.

        Raises:
            NetworkError: After max_retries with exponential backoff.
            VideoUnavailableError: Video cannot be accessed.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "Fetching metadata for video %s (attempt %d/%d)",
                    video_id,
                    attempt,
                    self.max_retries,
                )
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                if info is None:
                    raise VideoUnavailableError(
                        f"No info returned for video {video_id}",
                        reason="unknown",
                    )

                return self._map_info_to_metadata(info, video_id)

            except yt_dlp.utils.DownloadError as exc:
                error_msg = str(exc).lower()

                if self._is_unavailable_error(error_msg):
                    reason = self._classify_unavailable_reason(error_msg)
                    logger.warning(
                        "Video %s is unavailable: %s", video_id, reason
                    )
                    raise VideoUnavailableError(
                        f"Video {video_id} is unavailable: {reason}",
                        reason=reason,
                    ) from exc

                # Retryable network error
                last_exception = exc
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        "Network error fetching %s (attempt %d/%d), retrying in %.1fs: %s",
                        video_id,
                        attempt,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Failed to fetch metadata for %s after %d attempts: %s",
                        video_id,
                        self.max_retries,
                        exc,
                    )

            except Exception as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        "Unexpected error fetching %s (attempt %d/%d), retrying in %.1fs: %s",
                        video_id,
                        attempt,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Failed to fetch metadata for %s after %d attempts: %s",
                        video_id,
                        self.max_retries,
                        exc,
                    )

        raise NetworkError(
            f"Failed to fetch metadata for video {video_id} after {self.max_retries} attempts: {last_exception}",
            attempts=self.max_retries,
        )

    def _map_info_to_metadata(
        self, info: dict, video_id: str
    ) -> VideoMetadata:
        """Map a yt-dlp info dict to a VideoMetadata dataclass."""
        vid = info.get("id", video_id)
        streams = self._extract_streams(info.get("formats") or [], vid)

        upload_date_raw = info.get("upload_date", "")
        if upload_date_raw and len(upload_date_raw) == 8:
            upload_date = (
                f"{upload_date_raw[:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:]}"
            )
        else:
            upload_date = upload_date_raw or ""

        return VideoMetadata(
            video_id=vid,
            title=info.get("title", "Unknown"),
            duration_seconds=int(info.get("duration") or 0),
            thumbnail_url=info.get("thumbnail", ""),
            upload_date=upload_date,
            streams=streams,
        )

    def _extract_streams(self, formats: list[dict], video_id: str = "") -> list[Stream]:
        """Convert yt-dlp format dicts to Stream dataclasses."""
        streams: list[Stream] = []

        for fmt in formats:
            # Skip formats without a URL
            if not fmt.get("url"):
                continue

            vcodec = fmt.get("vcodec", "none")
            acodec = fmt.get("acodec", "none")
            is_audio_only = vcodec == "none" and acodec != "none"

            resolution = None
            if not is_audio_only and fmt.get("height"):
                resolution = int(fmt["height"])

            # Determine bitrate in kbps
            tbr = fmt.get("tbr")
            abr = fmt.get("abr")
            bitrate = int(tbr or abr or 0)

            codec = acodec if is_audio_only else vcodec
            if codec == "none":
                codec = "unknown"

            container = fmt.get("ext", "unknown")

            file_size = fmt.get("filesize") or fmt.get("filesize_approx")
            if file_size is not None:
                file_size = int(file_size)

            streams.append(
                Stream(
                    format_id=str(fmt.get("format_id", "")),
                    url=fmt["url"],
                    container=container,
                    resolution=resolution,
                    bitrate=bitrate,
                    codec=codec,
                    file_size=file_size,
                    is_audio_only=is_audio_only,
                    video_id=video_id,
                )
            )

        return streams

    @staticmethod
    def _is_unavailable_error(error_msg: str) -> bool:
        """Check if a yt-dlp error indicates the video is unavailable."""
        unavailable_indicators = [
            "private video",
            "video is private",
            "this video is unavailable",
            "video unavailable",
            "removed by the uploader",
            "deleted video",
            "been removed",
            "not available",
            "is not available in your country",
            "geo restricted",
            "geo-restricted",
            "blocked",
            "copyright",
            "age-restricted",
            "sign in to confirm your age",
            "join this channel",
            "members-only",
        ]
        return any(indicator in error_msg for indicator in unavailable_indicators)

    @staticmethod
    def _classify_unavailable_reason(error_msg: str) -> str:
        """Classify the reason a video is unavailable."""
        if any(
            kw in error_msg
            for kw in ("private video", "video is private")
        ):
            return "private"

        if any(
            kw in error_msg
            for kw in (
                "removed by the uploader",
                "deleted video",
                "been removed",
            )
        ):
            return "deleted"

        if any(
            kw in error_msg
            for kw in (
                "not available in your country",
                "geo restricted",
                "geo-restricted",
                "blocked",
            )
        ):
            return "region_locked"

        return "unknown"
