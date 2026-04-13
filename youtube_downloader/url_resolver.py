"""URL validation and resolution for YouTube URLs."""

import re
from urllib.parse import parse_qs, urlparse

from youtube_downloader.errors import InvalidURLError
from youtube_downloader.models import ResolvedURL, URLType


class URLResolver:
    """Validates and resolves YouTube URLs into video identifiers."""

    # Valid YouTube video ID: 11 characters, alphanumeric plus - and _
    _VIDEO_ID_RE = r"[A-Za-z0-9_-]{11}"

    # Playlist ID: starts with PL, OL, UU, FL, etc. and is 13-64 chars
    _PLAYLIST_ID_RE = r"[A-Za-z0-9_-]{13,}"

    # Compiled patterns for recognised YouTube URL formats.
    # Each pattern captures either a 'video_id' or 'playlist_id' named group.
    YOUTUBE_URL_PATTERNS: list[re.Pattern[str]] = [
        # Standard watch URL: youtube.com/watch?v=VIDEO_ID
        re.compile(
            r"^(?:https?://)?(?:www\.)?(?:youtube\.com|youtube-nocookie\.com)"
            r"/watch\?.*?v=(?P<video_id>" + _VIDEO_ID_RE + r")",
        ),
        # Short-form URL: youtu.be/VIDEO_ID
        re.compile(
            r"^(?:https?://)?youtu\.be/(?P<video_id>" + _VIDEO_ID_RE + r")",
        ),
        # Embed URL: youtube.com/embed/VIDEO_ID
        re.compile(
            r"^(?:https?://)?(?:www\.)?(?:youtube\.com|youtube-nocookie\.com)"
            r"/embed/(?P<video_id>" + _VIDEO_ID_RE + r")",
        ),
        # Shorts URL: youtube.com/shorts/VIDEO_ID
        re.compile(
            r"^(?:https?://)?(?:www\.)?youtube\.com"
            r"/shorts/(?P<video_id>" + _VIDEO_ID_RE + r")",
        ),
        # Playlist URL: youtube.com/playlist?list=PLAYLIST_ID
        re.compile(
            r"^(?:https?://)?(?:www\.)?youtube\.com"
            r"/playlist\?.*?list=(?P<playlist_id>" + _PLAYLIST_ID_RE + r")",
        ),
        # Watch URL that also contains a playlist parameter
        re.compile(
            r"^(?:https?://)?(?:www\.)?youtube\.com"
            r"/watch\?.*?list=(?P<playlist_id>" + _PLAYLIST_ID_RE + r")",
        ),
    ]

    def validate_and_resolve(self, url: str) -> ResolvedURL:
        """Validate a YouTube URL and extract video/playlist identifiers.

        Args:
            url: Raw URL string from user input.

        Returns:
            ResolvedURL with video_ids and url_type (single/playlist).

        Raises:
            InvalidURLError: URL does not match any recognised YouTube format.
        """
        if not url or not isinstance(url, str):
            raise InvalidURLError(f"Invalid YouTube URL: {url!r}")

        url = url.strip()

        for pattern in self.YOUTUBE_URL_PATTERNS:
            match = pattern.search(url)
            if match:
                groups = match.groupdict()

                if "playlist_id" in groups and groups["playlist_id"]:
                    playlist_id = groups["playlist_id"]
                    return ResolvedURL(
                        video_ids=[playlist_id],
                        url_type=URLType.PLAYLIST,
                    )

                if "video_id" in groups and groups["video_id"]:
                    video_id = groups["video_id"]
                    return ResolvedURL(
                        video_ids=[video_id],
                        url_type=URLType.SINGLE,
                    )

        raise InvalidURLError(
            f"Invalid YouTube URL: {url!r}. "
            "Expected a youtube.com/watch, youtu.be, youtube.com/embed, "
            "youtube.com/shorts, or youtube.com/playlist URL."
        )
