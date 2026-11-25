"""Interactive Highlight Clip & Acoustic Audio Trimmer (`UC-15`, Module M01)."""

from pathlib import Path
import subprocess
import wave

from app.m00_core_contracts import (
    MASTER_AUDIO_SAMPLE_RATE,
    MediaIngestError,
    MediaTrimResultDTO,
    NVENC_CQ,
    NVENC_PRESET,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
)

from .ffprobe_inspector import FFprobeInspector


class FFmpegMediaTrimmer:
    """Probes exact millisecond durations and trims highlight segments from video/audio clips."""

    @staticmethod
    def probe_duration_ms(media_path: Path) -> int:
        """Return duration in integer milliseconds for video/audio files, or `0` if non-timed."""
        if not media_path.exists():
            return 0
        ext = media_path.suffix.lower()
        if ext == ".wav":
            try:
                with wave.open(str(media_path), "rb") as wf:
                    sr = wf.getframerate()
                    frames = wf.getnframes()
                    if sr > 0 and frames > 0:
                        return max(100, int(round((frames / float(sr)) * 1000.0)))
            except Exception:
                pass
        if ext not in SUPPORTED_VIDEO_EXTENSIONS and ext not in SUPPORTED_AUDIO_EXTENSIONS:
            return 0
        try:
            info = FFprobeInspector.inspect(media_path, require_video=False)
            return max(0, int(info.duration_ms))
        except Exception:
            return 0

    @classmethod
    def trim_segment(
        cls,
        src_path: Path,
        dst_dir: Path,
        start_ms: int,
        end_ms: int,
        use_nvenc: bool = False,
    ) -> MediaTrimResultDTO:
        """Trim `[start_ms, end_ms]` cleanly into `dst_dir` preserving smooth playback."""
        if not src_path.exists():
            raise MediaIngestError(f"Không tìm thấy tệp gốc để cắt: {src_path.name}")
        clean_start = max(0, int(start_ms))
        clean_end = int(end_ms)
        if clean_end - clean_start < 600:
            raise MediaIngestError("Đoạn cắt tối thiểu cần dài ít nhất 0.6 giây.")

        dst_dir.mkdir(parents=True, exist_ok=True)
        ext = src_path.suffix.lower()
        start_sec = clean_start / 1000.0
        dur_sec = (clean_end - clean_start) / 1000.0
        stem_tag = f"{src_path.stem}_trim_{clean_start}_{clean_end}"

        if ext in SUPPORTED_VIDEO_EXTENSIONS:
            out_path = dst_dir / f"{stem_tag}.mp4"
            v_enc = (
                ["-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-cq", str(NVENC_CQ)]
                if use_nvenc
                else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start_sec:.3f}",
                "-t",
                f"{dur_sec:.3f}",
                "-i",
                str(src_path),
                *v_enc,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
            if (proc.returncode != 0 or not out_path.exists()) and use_nvenc:
                return cls.trim_segment(src_path, dst_dir, clean_start, clean_end, use_nvenc=False)
            if proc.returncode != 0 or not out_path.exists():
                raise MediaIngestError(f"Cắt đoạn video thất bại: {(proc.stderr or '').strip()}")
        elif ext in SUPPORTED_AUDIO_EXTENSIONS:
            out_path = dst_dir / f"{stem_tag}.wav"
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start_sec:.3f}",
                "-t",
                f"{dur_sec:.3f}",
                "-i",
                str(src_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(MASTER_AUDIO_SAMPLE_RATE),
                "-ac",
                "2",
                str(out_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
            if proc.returncode != 0 or not out_path.exists():
                raise MediaIngestError(f"Cắt đoạn âm thanh thất bại: {(proc.stderr or '').strip()}")
        else:
            raise MediaIngestError(f"Định dạng '{ext}' không hỗ trợ cắt thời gian.")

        actual_dur_ms = cls.probe_duration_ms(out_path) or (clean_end - clean_start)
        return MediaTrimResultDTO(
            output_path=out_path,
            duration_ms=max(500, actual_dur_ms),
            start_ms=clean_start,
            end_ms=clean_end,
        )
