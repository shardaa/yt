"""CLI entry point for the YouTube video downloader."""

import sys

import click

from youtube_downloader.download_engine import DownloadEngine
from youtube_downloader.errors import (
    ConversionError,
    DiskSpaceError,
    DownloaderError,
    InvalidURLError,
    NetworkError,
    NoMatchingStreamError,
    UnsupportedFormatError,
    VideoUnavailableError,
)
from youtube_downloader.format_converter import FormatConverter
from youtube_downloader.logging_config import setup_logging
from youtube_downloader.metadata_retriever import MetadataRetriever
from youtube_downloader.models import ConflictResolution, URLType, VideoMetadata
from youtube_downloader.playlist_downloader import PlaylistDownloader
from youtube_downloader.progress_reporter import ProgressReporter
from youtube_downloader.stream_selector import StreamSelector
from youtube_downloader.url_resolver import URLResolver


def _format_duration(seconds: int) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    hours = seconds // 3600
    remaining = seconds % 3600
    return f"{hours}:{remaining // 60:02d}:{remaining % 60:02d}"


def _format_bytes(num_bytes: int | None) -> str:
    """Format a byte count into a human-readable string."""
    if num_bytes is None:
        return "unknown size"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def _display_metadata(metadata: VideoMetadata) -> None:
    """Display video metadata to the console."""
    click.echo("")
    click.echo(f"  Title:    {metadata.title}")
    click.echo(f"  Duration: {_format_duration(metadata.duration_seconds)}")
    click.echo(f"  Uploaded: {metadata.upload_date}")
    click.echo(f"  Video ID: {metadata.video_id}")

    video_streams = [s for s in metadata.streams if not s.is_audio_only]
    audio_streams = [s for s in metadata.streams if s.is_audio_only]
    click.echo(f"  Streams:  {len(video_streams)} video, {len(audio_streams)} audio")
    click.echo("")


def _display_error(error: DownloaderError) -> None:
    """Display a human-readable error message for any DownloaderError subclass."""
    if isinstance(error, InvalidURLError):
        click.secho(f"Error: {error}", fg="red")
        click.echo("Please provide a valid YouTube URL (e.g. https://www.youtube.com/watch?v=...)")

    elif isinstance(error, VideoUnavailableError):
        reason_map = {
            "private": "This video is private.",
            "deleted": "This video has been deleted.",
            "region_locked": "This video is not available in your region.",
        }
        detail = reason_map.get(error.reason, "This video is unavailable.")
        click.secho(f"Error: {detail}", fg="red")

    elif isinstance(error, NetworkError):
        click.secho(f"Network error after {error.attempts} attempts: {error}", fg="red")
        click.echo("Please check your internet connection and try again.")

    elif isinstance(error, NoMatchingStreamError):
        click.secho(f"Error: {error}", fg="red")
        click.echo("Try different resolution/format options, or omit them to get the best available.")

    elif isinstance(error, DiskSpaceError):
        click.secho("Error: Insufficient disk space.", fg="red")
        click.echo(f"  Required:  {_format_bytes(error.required_bytes)}")
        click.echo(f"  Available: {_format_bytes(error.available_bytes)}")
        click.echo("Free up disk space and try again.")

    elif isinstance(error, UnsupportedFormatError):
        click.secho(f"Error: Unsupported format '{error.requested_format}'.", fg="red")
        click.echo(f"Supported formats: {', '.join(sorted(error.supported_formats))}")

    elif isinstance(error, ConversionError):
        click.secho(f"Conversion error: {error}", fg="red")
        if error.original_file_path:
            click.echo(f"Original file retained at: {error.original_file_path}")

    else:
        click.secho(f"Error: {error}", fg="red")


def _offer_conversion(file_path: str, progress_reporter: ProgressReporter) -> None:
    """Offer the user an option to convert the downloaded file."""
    converter = FormatConverter()
    supported = ", ".join(sorted(converter.SUPPORTED_FORMATS))

    if not click.confirm(f"\nConvert to a different format? (supported: {supported})", default=False):
        return

    target_format = click.prompt("Target format", type=str).strip().lower()

    try:
        click.echo(f"Converting to {target_format}...")
        result = converter.convert(
            input_path=file_path,
            target_format=target_format,
            progress_callback=progress_reporter.report_conversion_progress,
        )
        click.echo("")  # newline after progress
        if result.success:
            click.secho(f"Converted: {result.output_path}", fg="green")
        else:
            click.secho(f"Conversion failed: {result.error_message}", fg="red")
    except DownloaderError as exc:
        click.echo("")
        _display_error(exc)


def _download_single_video(
    video_id: str,
    output_dir: str,
    preferred_resolution: int | None,
    preferred_format: str | None,
    audio_only: bool,
    metadata_retriever: MetadataRetriever,
    stream_selector: StreamSelector,
    download_engine: DownloadEngine,
    progress_reporter: ProgressReporter,
) -> None:
    """Download a single video through the full pipeline."""
    # Fetch metadata
    click.echo("Fetching video metadata...")
    metadata = metadata_retriever.get_metadata(video_id)
    _display_metadata(metadata)

    # Select stream
    stream = stream_selector.select_stream(
        metadata,
        preferred_resolution=preferred_resolution,
        preferred_format=preferred_format,
        audio_only=audio_only,
    )

    kind = "audio" if stream.is_audio_only else "video"
    res_info = f"{stream.resolution}p" if stream.resolution else "audio-only"
    click.echo(
        f"Selected {kind} stream: {res_info} {stream.container} "
        f"({stream.codec}, {_format_bytes(stream.file_size)})"
    )

    # Download
    click.echo(f"\nDownloading to {output_dir}...")
    result = download_engine.download(
        stream=stream,
        output_dir=output_dir,
        filename=metadata.title,
        on_conflict=ConflictResolution.RENAME,
    )
    click.echo("")  # newline after progress

    if result.success and result.file_path:
        click.secho(f"Downloaded: {result.file_path}", fg="green")
        _offer_conversion(result.file_path, progress_reporter)
    else:
        click.secho(f"Download failed: {result.error_message}", fg="red")


def _download_playlist(
    resolved_url,
    output_dir: str,
    preferred_resolution: int | None,
    preferred_format: str | None,
    audio_only: bool,
    metadata_retriever: MetadataRetriever,
    stream_selector: StreamSelector,
    download_engine: DownloadEngine,
    progress_reporter: ProgressReporter,
) -> None:
    """Handle playlist download: display list, confirm, download, show summary."""
    playlist_id = resolved_url.video_ids[0]

    click.echo(f"\nPlaylist detected: {playlist_id}")
    click.echo("Fetching playlist information...")

    # For playlists, yt-dlp needs to extract the playlist to get video IDs.
    # The URLResolver returns the playlist ID; we use yt-dlp to expand it.
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/playlist?list={playlist_id}",
                download=False,
            )
    except Exception as exc:
        click.secho(f"Failed to fetch playlist: {exc}", fg="red")
        return

    if not info or "entries" not in info:
        click.secho("Could not retrieve playlist entries.", fg="red")
        return

    entries = [e for e in info["entries"] if e is not None]
    playlist_title = info.get("title", playlist_id)

    click.echo(f"\nPlaylist: {playlist_title}")
    click.echo(f"Videos:   {len(entries)}")
    click.echo("")

    for i, entry in enumerate(entries, start=1):
        title = entry.get("title", entry.get("id", "Unknown"))
        duration = entry.get("duration")
        dur_str = f" ({_format_duration(int(duration))})" if duration else ""
        click.echo(f"  {i:3d}. {title}{dur_str}")

    click.echo("")
    if not click.confirm(f"Download all {len(entries)} videos?", default=True):
        click.echo("Cancelled.")
        return

    # Build a ResolvedURL with actual video IDs for the PlaylistDownloader
    from youtube_downloader.models import ResolvedURL

    video_ids = [e.get("id") for e in entries if e.get("id")]
    playlist_resolved = ResolvedURL(
        video_ids=video_ids,
        url_type=URLType.PLAYLIST,
        playlist_title=playlist_title,
    )

    playlist_downloader = PlaylistDownloader(
        metadata_retriever=metadata_retriever,
        stream_selector=stream_selector,
        download_engine=download_engine,
        progress_reporter=progress_reporter,
    )

    summary = playlist_downloader.download_playlist(
        resolved_url=playlist_resolved,
        output_dir=output_dir,
        preferred_resolution=preferred_resolution,
        preferred_format=preferred_format,
        audio_only=audio_only,
        on_conflict=ConflictResolution.RENAME,
    )

    # Display summary
    click.echo("\n" + "=" * 50)
    click.echo("Playlist Download Summary")
    click.echo("=" * 50)
    click.echo(f"Total:      {summary.total_videos}")
    click.secho(f"Successful: {len(summary.successful)}", fg="green")

    if summary.failed:
        click.secho(f"Failed:     {len(summary.failed)}", fg="red")
        click.echo("\nFailed videos:")
        for title, error_msg in summary.failed:
            click.echo(f"  - {title}: {error_msg}")

    click.echo("")


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """YouTube video downloader CLI."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("url")
@click.option(
    "-o", "--output-dir",
    default="./downloads",
    show_default=True,
    help="Directory to save downloaded files.",
)
@click.option(
    "-r", "--resolution",
    type=int,
    default=None,
    help="Preferred maximum resolution in pixels (e.g. 1080, 720, 480).",
)
@click.option(
    "-f", "--format",
    "fmt",
    type=str,
    default=None,
    help="Preferred container format (e.g. mp4, webm).",
)
@click.option(
    "--audio-only",
    is_flag=True,
    default=False,
    help="Download audio-only stream.",
)
def download(
    url: str,
    output_dir: str,
    resolution: int | None,
    fmt: str | None,
    audio_only: bool,
) -> None:
    """Download a YouTube video or playlist.

    URL is the YouTube video or playlist URL to download.
    """
    # Set up logging
    setup_logging(output_dir)

    # Initialize components
    progress_reporter = ProgressReporter()
    url_resolver = URLResolver()
    metadata_retriever = MetadataRetriever()
    stream_selector = StreamSelector()
    download_engine = DownloadEngine(
        progress_callback=progress_reporter.report_download_progress,
    )

    try:
        # Validate and resolve URL
        click.echo(f"Resolving URL: {url}")
        resolved = url_resolver.validate_and_resolve(url)

        if resolved.url_type == URLType.PLAYLIST:
            _download_playlist(
                resolved_url=resolved,
                output_dir=output_dir,
                preferred_resolution=resolution,
                preferred_format=fmt,
                audio_only=audio_only,
                metadata_retriever=metadata_retriever,
                stream_selector=stream_selector,
                download_engine=download_engine,
                progress_reporter=progress_reporter,
            )
        else:
            video_id = resolved.video_ids[0]
            _download_single_video(
                video_id=video_id,
                output_dir=output_dir,
                preferred_resolution=resolution,
                preferred_format=fmt,
                audio_only=audio_only,
                metadata_retriever=metadata_retriever,
                stream_selector=stream_selector,
                download_engine=download_engine,
                progress_reporter=progress_reporter,
            )

    except DownloaderError as exc:
        _display_error(exc)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nDownload interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        click.secho(f"Unexpected error: {exc}", fg="red")
        sys.exit(1)


@main.command()
@click.option(
    "-p", "--port",
    type=int,
    default=5000,
    show_default=True,
    help="Port to run the web server on.",
)
@click.option(
    "-o", "--output-dir",
    default="./downloads",
    show_default=True,
    help="Directory to save downloaded files.",
)
def web(port: int, output_dir: str) -> None:
    """Start the web UI server for browser-based downloading."""
    from youtube_downloader.web_app import run_server

    click.echo(f"Starting web server on port {port}...")
    click.echo(f"Downloads will be saved to: {output_dir}")
    run_server(port=port, output_dir=output_dir)


if __name__ == "__main__":
    main()
