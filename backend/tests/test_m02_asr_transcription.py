"""Unit & I/O Contract Tests for Module M02 (`m02_asr_transcription`)."""

from pathlib import Path
import pytest

from app.m00_core_contracts import MediaAssetDTO, TranscriptionError
from app.m02_asr_transcription import FasterWhisperTranscriber, SRTSubtitleParser


def test_m02_srt_parser_detects_chinese_and_word_timings(tmp_path: Path) -> None:
    """Verify SRT parsing produces valid TranscriptResultDTO in milliseconds."""
    srt_file = tmp_path / "drama_ep1.srt"
    srt_file.write_text(
        "1\n00:00:01,200 --> 00:00:04,500\n<i>总裁，夫人已经签了离婚协议书！</i>\n\n"
        "2\n00:00:05,000 --> 00:00:08,100\n什么？立刻封锁机场！\n",
        encoding="utf-8",
    )

    res = SRTSubtitleParser.parse(srt_file, media_id="med_zh_01")
    assert res.media_id == "med_zh_01"
    assert res.detected_language == "zh"
    assert len(res.segments) == 2
    assert res.segments[0].start_ms == 1200
    assert res.segments[0].end_ms == 4500
    assert "<i>" not in res.segments[0].raw_text
    assert len(res.segments[0].words) >= 1


@pytest.mark.asyncio
async def test_m02_transcriber_consumes_m01_media_asset_with_srt(tmp_path: Path) -> None:
    """Prove M01 MediaAssetDTO seamlessly feeds M02 FasterWhisperTranscriber."""
    srt_file = tmp_path / "vi_sub.srt"
    srt_file.write_text(
        "1\n00:00:00,500 --> 00:00:03,000\nChào mừng các bạn đến với tập phim mới nhất.\n",
        encoding="utf-8",
    )
    dummy_vid = tmp_path / "vid.mp4"
    dummy_wav = tmp_path / "aud.wav"
    dummy_vid.write_bytes(b"00")
    dummy_wav.write_bytes(b"00")

    media_dto = MediaAssetDTO(
        media_id="med_vi_01",
        project_id="proj_1",
        video_path=dummy_vid,
        audio_16k_wav_path=dummy_wav,
        duration_ms=10000,
        width=1920,
        height=1080,
        fps=30.0,
        external_srt_path=srt_file,
    )

    transcriber = FasterWhisperTranscriber()
    result = await transcriber.transcribe(media_dto)
    assert result.detected_language == "vi"
    assert result.segments[0].start_ms == 500
    assert result.segments[0].end_ms == 3000


def test_m02_empty_srt_raises_transcription_error(tmp_path: Path) -> None:
    """Verify invalid/empty SRT raises explicit TranscriptionError."""
    bad_srt = tmp_path / "empty.srt"
    bad_srt.write_text("   \n", encoding="utf-8")
    with pytest.raises(TranscriptionError):
        SRTSubtitleParser.parse(bad_srt, media_id="med_err")

