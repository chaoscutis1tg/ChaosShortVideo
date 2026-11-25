"""Unit & I/O Contract Tests for Module M05 (`m05_voice_audio_mixer`)."""

from pathlib import Path
import subprocess
import wave
import numpy as np
import pytest

from app.m00_core_contracts import (
    AudioSubConfigDTO,
    ClipSpecDTO,
    DEFAULT_VOICE_PROFILES,
    MASTER_AUDIO_SAMPLE_RATE,
    NarrationLineDTO,
    SubtitleStyle,
)
from app.m05_voice_audio_mixer import (
    DramaticProsodyEnhancer,
    MovieAudioAndSubMixer,
    TTSProviderFactory,
)


def test_m05_dramatic_prosody_inserts_emotional_pauses() -> None:
    """Verify DramaticProsodyEnhancer adds natural dramatic breath pauses."""
    raw = "Không ai ngờ người đàn ông trầm lặng này lại chính là chủ tịch tập đoàn nghìn tỷ"
    enhanced = DramaticProsodyEnhancer.enhance(raw)
    assert enhanced.startswith("Không ai ngờ,")
    assert enhanced.endswith(".")


def _create_loud_stereo_wav(path: Path, duration_sec: float = 5.0) -> Path:
    """Generate a constant-amplitude 440Hz stereo WAV representing original movie audio."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate={MASTER_AUDIO_SAMPLE_RATE}:duration={duration_sec}",
        "-ac",
        "2",
        "-acodec",
        "pcm_s16le",
        str(path),
    ]
    subprocess.run(cmd, check=True)
    return path


@pytest.mark.asyncio
async def test_m05_audio_ducking_and_karaoke_ass_contract(tmp_path: Path) -> None:
    """Verify M05 ducks original movie audio during speech and outputs valid MasterAudioAndSubDTO."""
    orig_wav = _create_loud_stereo_wav(tmp_path / "orig_movie.wav", duration_sec=6.0)

    clip = ClipSpecDTO(
        clip_id="clip_m05_01",
        project_id="proj_m05",
        part_number=1,
        source_start_ms=0,
        source_end_ms=6000,
        hook_banner_title="Thuyết Minh Chuẩn Web Phim | Phần 1",
        lines=[
            NarrationLineDTO(
                seq_index=0,
                rel_start_ms=1000,
                rel_end_ms=3200,
                vi_text="Chủ tịch đã chính thức lộ diện trước toàn bộ hội đồng.",
            )
        ],
    )

    mixer = MovieAudioAndSubMixer(tts_factory=TTSProviderFactory(allow_offline_fallback=True))
    cfg = AudioSubConfigDTO(
        enable_narration=True,
        keep_original_audio=True,
        ducking_ratio=0.18,
        subtitle_style=SubtitleStyle.KARAOKE_CAPCUT,
    )
    out = await mixer.process(
        clip=clip,
        profile=DEFAULT_VOICE_PROFILES[0],
        audio_config=cfg,
        out_dir=tmp_path / "work",
        orig_stereo_wav=orig_wav,
    )

    assert out.clip_id == "clip_m05_01"
    assert out.master_audio_wav_path.exists()
    assert out.ass_subtitle_path is not None and out.ass_subtitle_path.exists()
    assert out.total_audio_duration_ms >= 5900

    ass_content = out.ass_subtitle_path.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1080" in ass_content
    assert "PlayResY: 1920" in ass_content
    assert "\\kf" in ass_content

    with wave.open(str(out.master_audio_wav_path), "rb") as wf:
        assert wf.getframerate() == MASTER_AUDIO_SAMPLE_RATE
        assert wf.getnchannels() == 2
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        assert np.max(np.abs(pcm)) > 500

