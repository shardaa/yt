"""Format conversion using ffmpeg."""

import logging
import os
import re
import subprocess
from collections.abc import Callable

from youtube_downloader.errors import ConversionError, UnsupportedFormatError
from youtube_downloader.models import ConversionResult

logger = logging.getLogger(__name__)


class FormatConverter:
    """Converts media files between formats using ffmpeg."""

    SUPPORTED_FORMATS: set[str] = {"mp4", "mkv", "avi", "mp3", "wav"}

    def convert(
        self,
        input_path: str,
        target_format: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> ConversionResult:
        """
        Convert a media file to the target format.

        Args:
            input_path: Path to the source file.
            target_format: Target container format (e.g., "mkv").
            progress_callback: Called with percentage (0.0-100.0) during conversion.

        Returns:
            ConversionResult with output_path and success status.
            Original file is always retained on failure.

        Raises:
            ConversionError: ffmpeg process failed.
            UnsupportedFormatError: Target format not in SUPPORTED_FORMATS.
        """
        target_format = target_format.lower().strip().lstrip(".")

        if target_format not in self.SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"Format '{target_format}' is not supported. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}",
                requested_format=target_format,
                supported_formats=self.SUPPORTED_FORMATS,
            )

        # Build output path by replacing the extension
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.{target_format}"

        # Avoid overwriting the input file if extensions match
        if os.path.abspath(output_path) == os.path.abspath(input_path):
            output_path = f"{base}_converted.{target_format}"

        # Get input duration for progress calculation
        duration = self._get_duration(input_path)

        logger.info(
            "Converting '%s' to '%s' format -> '%s'",
            input_path,
            target_format,
            output_path,
        )

        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-y",              # Overwrite output without asking
            "-progress", "-",  # Write progress info to stdout
            "-nostats",        # Suppress default stats to stderr
            output_path,
        ]

        stderr_output = ""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            if process.stdout and duration and duration > 0:
                self._read_progress(process.stdout, duration, progress_callback)

            _, stderr_output = process.communicate()

            if process.returncode != 0:
                # Clean up partial output on failure, retain original
                if os.path.exists(output_path):
                    os.remove(output_path)

                logger.error(
                    "ffmpeg conversion failed (exit code %d): %s",
                    process.returncode,
                    stderr_output,
                )
                raise ConversionError(
                    f"ffmpeg conversion failed with exit code {process.returncode}",
                    ffmpeg_stderr=stderr_output,
                    original_file_path=input_path,
                )

        except FileNotFoundError:
            raise ConversionError(
                "ffmpeg not found. Please install ffmpeg and ensure it is on your PATH.",
                ffmpeg_stderr="ffmpeg: command not found",
                original_file_path=input_path,
            )
        except ConversionError:
            raise
        except Exception as exc:
            # Clean up partial output on unexpected errors
            if os.path.exists(output_path):
                os.remove(output_path)

            raise ConversionError(
                f"Unexpected error during conversion: {exc}",
                ffmpeg_stderr=stderr_output,
                original_file_path=input_path,
            )

        if progress_callback:
            progress_callback(100.0)

        logger.info("Conversion complete: '%s'", output_path)

        return ConversionResult(
            success=True,
            output_path=output_path,
            original_path=input_path,
        )

    def _get_duration(self, input_path: str) -> float | None:
        """Get the duration of a media file in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            logger.debug("Could not determine input duration for progress tracking")
        return None

    def _read_progress(
        self,
        stdout: object,
        duration: float,
        progress_callback: Callable[[float], None] | None,
    ) -> None:
        """Parse ffmpeg -progress output from stdout to extract time and compute percentage."""
        if not progress_callback:
            return

        time_pattern = re.compile(r"out_time_us=(\d+)")

        for line in stdout:  # type: ignore[union-attr]
            match = time_pattern.match(line.strip())
            if match:
                time_us = int(match.group(1))
                time_seconds = time_us / 1_000_000
                percentage = min((time_seconds / duration) * 100.0, 100.0)
                progress_callback(percentage)

            if line.strip() == "progress=end":
                break
