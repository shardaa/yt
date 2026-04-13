"""Stream selection and filtering based on user preferences."""

from youtube_downloader.errors import NoMatchingStreamError
from youtube_downloader.models import Stream, VideoMetadata


class StreamSelector:
    """Selects the best matching stream based on user preferences."""

    SUPPORTED_FORMATS: set[str] = {"mp4", "webm", "mp3"}

    def list_streams(
        self,
        metadata: VideoMetadata,
        audio_only: bool = False,
    ) -> list[Stream]:
        """
        Return available streams sorted by resolution (desc) or bitrate (desc for audio).

        Args:
            metadata: Video metadata containing available streams.
            audio_only: If True, return only audio streams sorted by bitrate.

        Returns:
            Sorted list of Stream objects.
        """
        if audio_only:
            streams = [s for s in metadata.streams if s.is_audio_only]
            return sorted(streams, key=lambda s: s.bitrate, reverse=True)

        streams = [s for s in metadata.streams if not s.is_audio_only]
        return sorted(
            streams, key=lambda s: s.resolution if s.resolution is not None else 0, reverse=True
        )

    def select_stream(
        self,
        metadata: VideoMetadata,
        preferred_resolution: int | None = None,
        preferred_format: str | None = None,
        audio_only: bool = False,
    ) -> Stream:
        """
        Select the best matching stream from available options.

        Args:
            metadata: Video metadata containing available streams.
            preferred_resolution: Max resolution in pixels (e.g., 1080). Selects closest <= value.
            preferred_format: Desired container format.
            audio_only: If True, only consider audio streams.

        Returns:
            The best matching Stream.

        Raises:
            NoMatchingStreamError: No stream matches the given criteria.
        """
        candidates = self.list_streams(metadata, audio_only=audio_only)

        if preferred_format is not None:
            candidates = [s for s in candidates if s.container == preferred_format]

        if not audio_only and preferred_resolution is not None:
            candidates = [
                s for s in candidates
                if s.resolution is not None and s.resolution <= preferred_resolution
            ]

        if not candidates:
            raise NoMatchingStreamError("No stream matches the given criteria.")

        # candidates are already sorted desc by resolution (or bitrate for audio),
        # so the first element is the best match.
        return candidates[0]
