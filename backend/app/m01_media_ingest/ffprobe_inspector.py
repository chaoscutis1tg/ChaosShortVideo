"""FFprobe stream metadata inspector for Module M01."""

from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import subprocess

from app.m00_core_contracts import MediaIngestError, NoAudioStreamError


@dataclass(frozen=True)
class ProbedMediaInfo:
    """Parsed technical properties of a source video file."""

    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool


class FFprobeInspector:
    """Inspects video/audio streams using `ffprobe` CLI."""

    @staticmethod
    def inspect(video_path: Path, require_audio: bool = True) -> ProbedMediaInfo:
        """Probe video dimensions, frame rate, duration (ms), and audio presence.

        Args:
            video_path: Path to the local video file.
            require_audio: Whether to raise NoAudioStreamError if no audio track exists.

        Returns:
            ProbedMediaInfo with integer millisecond duration and stream dimensions.

        Raises:
            MediaIngestError: If ffprobe fails or no video stream is present.
            NoAudioStreamError: If require_audio is True and no audio stream exists.
        """
        if not video_path.exists():
            raise MediaIngestError(f"Không tìm thấy tệp video: {video_path}")

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if proc.returncode != 0 or not proc.stdout.strip():
            raise MediaIngestError(f"Không thể đọc thông số video bằng ffprobe: {video_path.name}")

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise MediaIngestError(f"Dữ liệu ffprobe không hợp lệ: {exc}") from exc

        streams = payload.get("streams", [])
        fmt = payload.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if video_stream is None:
            raise MediaIngestError(f"Tệp '{video_path.name}' không chứa luồng hình ảnh hợp lệ.")
        if require_audio and audio_stream is None:
            raise NoAudioStreamError(
                f"Tệp '{video_path.name}' không có kênh âm thanh để tách thoại hoặc trộn âm."
            )

        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
        if width <= 0 or height <= 0:
            raise MediaIngestError(f"Kích thước khung hình không hợp lệ ({width}x{height}).")

        raw_fps = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "30/1"
        try:
            fps_val = float(Fraction(raw_fps)) if "/" in str(raw_fps) else float(raw_fps)
            if fps_val <= 0 or fps_val > 240:
                fps_val = 30.0
        except (ValueError, ZeroDivisionError):
            fps_val = 30.0

        dur_str = fmt.get("duration") or video_stream.get("duration") or "0"
        duration_ms = int(round(float(dur_str) * 1000.0))
        if duration_ms <= 0:
            raise MediaIngestError(f"Thời lượng video không hợp lệ ({duration_ms} ms).")

        return ProbedMediaInfo(
            duration_ms=duration_ms,
            width=width,
            height=height,
            fps=round(fps_val, 3),
            has_audio=audio_stream is not None,
        )

