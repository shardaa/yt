"""Error hierarchy for the YouTube video downloader."""


class DownloaderError(Exception):
    """Base exception for all downloader errors."""

    pass


class InvalidURLError(DownloaderError):
    """URL is not a recognized YouTube format."""

    pass


class VideoUnavailableError(DownloaderError):
    """Video is private, deleted, or region-locked."""

    def __init__(self, message: str = "", reason: str = "unknown") -> None:
        super().__init__(message)
        self.reason = reason  # "private", "deleted", "region_locked", "unknown"


class NetworkError(DownloaderError):
    """Network operation failed after retries."""

    def __init__(self, message: str = "", attempts: int = 0) -> None:
        super().__init__(message)
        self.attempts = attempts


class NoMatchingStreamError(DownloaderError):
    """No stream matches the given selection criteria."""

    pass


class DiskSpaceError(DownloaderError):
    """Insufficient disk space."""

    def __init__(
        self, message: str = "", required_bytes: int = 0, available_bytes: int = 0
    ) -> None:
        super().__init__(message)
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes


class ConversionError(DownloaderError):
    """ffmpeg conversion failed."""

    def __init__(
        self,
        message: str = "",
        ffmpeg_stderr: str = "",
        original_file_path: str = "",
    ) -> None:
        super().__init__(message)
        self.ffmpeg_stderr = ffmpeg_stderr
        self.original_file_path = original_file_path  # Always retained


class UnsupportedFormatError(DownloaderError):
    """Requested format is not supported."""

    def __init__(
        self,
        message: str = "",
        requested_format: str = "",
        supported_formats: set[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.requested_format = requested_format
        self.supported_formats = supported_formats or set()
