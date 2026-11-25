"""Concrete implementation of Module M01 (`IMediaIngestor`)."""

import asyncio
from pathlib import Path
import subprocess
from typing import List, Optional
import uuid

from app.m00_core_contracts import (
    IMediaIngestor,
    IngestRequestDTO,
    MASTER_AUDIO_SAMPLE_RATE,
    MediaAssetDTO,
    MediaIngestError,
    ProgressCallback,
    SourceType,
    SUPPORTED_SUBTITLE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    UnsupportedMediaFormatError,
    WHISPER_SAMPLE_RATE,
)

from .ffprobe_inspector import FFprobeInspector
from .url_downloader import YtDlpDownloader, normalize_video_url

PREVIEW_FRAME_RATIOS = (0.20, 0.50, 0.80)


class FFmpegMediaIngestor(IMediaIngestor):
    """Ingests local movie files or URLs, probes streams, and extracts standardized WAVs."""

    def __init__(self, downloader: Optional[YtDlpDownloader] = None) -> None:
        self._downloader = downloader or YtDlpDownloader()

    async def ingest(
        self,
        req: IngestRequestDTO,
        work_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> MediaAssetDTO:
        """Validate/download source video and extract 16kHz mono WAV + 44.1kHz stereo WAV."""
        project_dir = work_dir / req.project_id / "ingest"
        project_dir.mkdir(parents=True, exist_ok=True)

        external_srt: Optional[Path] = req.external_srt_path
        if external_srt is not None:
            if not external_srt.exists():
                raise MediaIngestError(f"Không tìm thấy tệp phụ đề rời: {external_srt}")
            if external_srt.suffix.lower() not in SUPPORTED_SUBTITLE_EXTENSIONS:
                raise UnsupportedMediaFormatError(
                    f"Định dạng phụ đề '{external_srt.suffix}' không được hỗ trợ."
                )

        raw_target = req.path_or_url.strip()
        is_remote_url = req.source_type == SourceType.VIDEO_URL or (
            "http://" in raw_target.lower() or "https://" in raw_target.lower()
        )

        title_hint = req.project_id
        if not is_remote_url:
            video_path = Path(raw_target).resolve()
            if not video_path.exists():
                raise MediaIngestError(f"Tệp video không tồn tại: {video_path}")
            if video_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
                raise UnsupportedMediaFormatError(
                    f"Định dạng video '{video_path.suffix}' không nằm trong danh sách hỗ trợ."
                )
            title_hint = video_path.stem
            if on_progress:
                on_progress("INGESTING", 25.0, f"Đã liên kết tệp gốc: {video_path.name}")
        else:
            clean_url = normalize_video_url(raw_target)
            if not clean_url.startswith(("http://", "https://")):
                raise MediaIngestError("Đường dẫn tải video phải bắt đầu bằng http:// hoặc https://")
            bundle = await self._downloader.download(
                url=clean_url,
                dest_dir=project_dir,
                on_progress=on_progress,
            )
            video_path = bundle.video_path
            title_hint = bundle.title
            if external_srt is None and bundle.subtitle_path is not None:
                external_srt = bundle.subtitle_path

        info = await asyncio.to_thread(FFprobeInspector.inspect, video_path, True)

        audio_16k = project_dir / "audio_16k_mono.wav"
        stereo_wav = project_dir / "audio_44k_stereo.wav"

        if on_progress:
            on_progress("INGESTING", 60.0, "Đang tách kênh âm thanh chuẩn 16kHz & Stereo...")

        await asyncio.to_thread(self._extract_wav, video_path, audio_16k, WHISPER_SAMPLE_RATE, 1)
        await asyncio.to_thread(
            self._extract_wav, video_path, stereo_wav, MASTER_AUDIO_SAMPLE_RATE, 2
        )

        if on_progress:
            on_progress("INGESTING", 85.0, "Đang trích xuất khung hình mẫu để căn chỉnh 9:16...")

        preview_frames = await asyncio.to_thread(
            self._extract_preview_frames, video_path, project_dir, info.duration_ms
        )

        if on_progress:
            on_progress("INGESTING", 100.0, "Hoàn tất nạp phim nguồn.")

        return MediaAssetDTO(
            media_id=f"med_{uuid.uuid4().hex[:10]}",
            project_id=req.project_id,
            video_path=video_path,
            audio_16k_wav_path=audio_16k,
            original_stereo_wav_path=stereo_wav,
            duration_ms=info.duration_ms,
            width=info.width,
            height=info.height,
            fps=info.fps,
            preview_frames=preview_frames,
            external_srt_path=external_srt,
            title_hint=title_hint,
        )

    @staticmethod
    def _extract_wav(video_path: Path, out_wav: Path, sample_rate: int, channels: int) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            str(out_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if proc.returncode != 0 or not out_wav.exists():
            raise MediaIngestError(f"Tách âm thanh WAV thất bại: {proc.stderr.strip()}")

    @staticmethod
    def _extract_preview_frames(
        video_path: Path, project_dir: Path, duration_ms: int
    ) -> List[Path]:
        frames: List[Path] = []
        for idx, ratio in enumerate(PREVIEW_FRAME_RATIOS, start=1):
            ts_sec = max((duration_ms * ratio) / 1000.0, 0.1)
            out_jpg = project_dir / f"preview_{idx}.jpg"
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{ts_sec:.2f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(out_jpg),
            ]
            subprocess.run(cmd, capture_output=True, check=False)
            if out_jpg.exists() and out_jpg.stat().st_size > 0:
                frames.append(out_jpg)
        return frames

