"""Unit & I/O Contract Tests for Module M01 (`m01_media_ingest`)."""

from pathlib import Path
import subprocess
import wave
import pytest

from app.m00_core_contracts import (
    IngestRequestDTO,
    NoAudioStreamError,
    SourceType,
    UnsupportedMediaFormatError,
    WHISPER_SAMPLE_RATE,
)
from app.m01_media_ingest import FFmpegMediaIngestor, normalize_video_url


def test_m01_normalize_bilibili_localized_and_share_urls() -> None:
    """Verify localized Bilibili `/vi/video/BV...` and share strings normalize cleanly."""
    raw_bili_vi = (
        "https://www.bilibili.com/vi/video/BV1TdWL6WEmK/"
        "?trackid=web_pegasus_0.router&spm_id_from=333.1007&p=2"
    )
    assert normalize_video_url(raw_bili_vi) == "https://www.bilibili.com/video/BV1TdWL6WEmK/?p=2"

    raw_bstar = "Xem phim hay: https://www.bilibili.tv/vi/video/4801343185492992?bstar_from=bstar-web.homepage"
    assert normalize_video_url(raw_bstar) == "https://www.bilibili.tv/vi/video/4801343185492992"


def _make_sample_mp4(out_path: Path, with_audio: bool = True, duration_sec: float = 2.5) -> Path:
    """Create a synthetic 1280x720 MP4 video using FFmpeg lavfi for deterministic testing."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=1280x720:rate=30:duration={duration_sec}",
    ]
    if with_audio:
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=44100:duration={duration_sec}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
            ]
        )
    else:
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"])
    cmd.append(str(out_path))
    subprocess.run(cmd, check=True)
    return out_path


@pytest.mark.asyncio
async def test_m01_ingest_local_mp4_contract(tmp_path: Path) -> None:
    """Verify M01 produces a valid MediaAssetDTO with 16kHz mono WAV and preview frames."""
    sample_mp4 = _make_sample_mp4(tmp_path / "episode_01.mp4", with_audio=True, duration_sec=3.0)
    ingestor = FFmpegMediaIngestor()

    req = IngestRequestDTO(
        project_id="proj_m01",
        source_type=SourceType.LOCAL_FILE,
        path_or_url=str(sample_mp4),
    )
    asset = await ingestor.ingest(req, work_dir=tmp_path / "work")

    assert asset.project_id == "proj_m01"
    assert asset.width == 1280
    assert asset.height == 720
    assert 2800 <= asset.duration_ms <= 3200
    assert asset.audio_16k_wav_path.exists()
    assert asset.original_stereo_wav_path is not None and asset.original_stereo_wav_path.exists()
    assert len(asset.preview_frames) == 3

    with wave.open(str(asset.audio_16k_wav_path), "rb") as wf:
        assert wf.getframerate() == WHISPER_SAMPLE_RATE
        assert wf.getnchannels() == 1


@pytest.mark.asyncio
async def test_m01_rejects_unsupported_extension(tmp_path: Path) -> None:
    """Ensure unsupported file extensions raise UnsupportedMediaFormatError."""
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not a video", encoding="utf-8")

    ingestor = FFmpegMediaIngestor()
    req = IngestRequestDTO(
        project_id="proj_bad",
        source_type=SourceType.LOCAL_FILE,
        path_or_url=str(bad_file),
    )
    with pytest.raises(UnsupportedMediaFormatError):
        await ingestor.ingest(req, work_dir=tmp_path / "work")


@pytest.mark.asyncio
async def test_m01_rejects_video_without_audio(tmp_path: Path) -> None:
    """Ensure silent videos without audio tracks raise NoAudioStreamError."""
    silent_mp4 = _make_sample_mp4(tmp_path / "silent.mp4", with_audio=False, duration_sec=1.5)
    ingestor = FFmpegMediaIngestor()
    req = IngestRequestDTO(
        project_id="proj_silent",
        source_type=SourceType.LOCAL_FILE,
        path_or_url=str(silent_mp4),
    )
    with pytest.raises(NoAudioStreamError):
        await ingestor.ingest(req, work_dir=tmp_path / "work")

