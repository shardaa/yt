"""Data models for the YouTube video downloader."""

from dataclasses import dataclass, field
from enum import Enum


class URLType(Enum):
    """Type of YouTube URL."""

    SINGLE = "single"
    PLAYLIST = "playlist"


class ConflictResolution(Enum):
    """How to handle existing files with the same name."""

    OVERWRITE = "overwrite"
    RENAME = "rename"
    CANCEL = "cancel"
    ASK = "ask"


@dataclass(frozen=True)
class ResolvedURL:
    """Result of URL validation and resolution."""

    video_ids: list[str]
    url_type: URLType
    playlist_title: str | None = None


@dataclass(frozen=True)
class Stream:
    """A single downloadable stream."""

    format_id: str
    url: str
    container: str  # "mp4", "webm", "mp3", etc.
    resolution: int | None  # Height in pixels (None for audio-only)
    bitrate: int  # In kbps
    codec: str
    file_size: int | None  # In bytes (None if unknown)
    is_audio_only: bool = False
    video_id: str = ""  # YouTube video ID for proper yt-dlp downloads


@dataclass(frozen=True)
class VideoMetadata:
    """Metadata for a single YouTube video."""

    video_id: str
    title: str
    duration_seconds: int
    thumbnail_url: str
    upload_date: str  # ISO 8601 date string
    streams: list[Stream]


@dataclass
class DownloadProgress:
    """Current state of a download."""

    bytes_downloaded: int
    total_bytes: int | None
    speed_bytes_per_sec: float
    eta_seconds: float | None
    percentage: float  # 0.0 to 100.0


@dataclass(frozen=True)
class DownloadResult:
    """Result of a download operation."""

    success: bool
    file_path: str | None
    error_message: str | None = None
    was_resumed: bool = False


@dataclass(frozen=True)
class ConversionResult:
    """Result of a format conversion."""

    success: bool
    output_path: str | None
    original_path: str
    error_message: str | None = None


@dataclass
class PlaylistDownloadSummary:
    """Summary of a playlist download operation."""

    total_videos: int
    successful: list[str]  # List of video titles
    failed: list[tuple[str, str]]  # List of (video_title, error_message)
