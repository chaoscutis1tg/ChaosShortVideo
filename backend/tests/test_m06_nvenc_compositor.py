"""Unit & I/O Contract Tests for Module M06 (`m06_nvenc_compositor`) on RTX 3060 NVENC."""

from pathlib import Path
import subprocess
from PIL import Image
import pytest

from app.m00_core_contracts import (
    AssetType,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    ClipSpecDTO,
    HardsubMaskMode,
    LayoutAndAntiCopyConfigDTO,
    LayoutType,
    MasterAudioAndSubDTO,
    MotionEffect,
    NarrationLineDTO,
    NormalizedRectDTO,
    RenderJobSpecDTO,
    SceneVisualItemDTO,
    VisualAssetListDTO,
)
from app.m06_nvenc_compositor import FFmpegNVENCCompositor


def _make_source_video_and_audio(tmp_path: Path) -> tuple[Path, Path, Path]:
    src_mp4 = tmp_path / "raw_movie.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=1280x720:rate=30:duration=2.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(src_mp4),
        ],
        check=True,
    )
    master_wav = tmp_path / "master.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:sample_rate=44100:duration=2.5",
            "-ac",
            "2",
            "-acodec",
            "pcm_s16le",
            str(master_wav),
        ],
        check=True,
    )
    ass_file = tmp_path / "subs.ass"
    ass_file.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, "
        "Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: S,Segoe UI,52,&H0000EAFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,280,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.20,0:00:02.20,S,,0,0,0,,{\\kf80}Phụ {\\kf80}đề {\\kf80}kiểm {\\kf80}thử\n",
        encoding="utf-8-sig",
    )
    return src_mp4, master_wav, ass_file


@pytest.mark.asyncio
async def test_m06_render_movie_clip_916_hardsub_blur_and_nvenc(tmp_path: Path) -> None:
    """Verify M06 renders 1080x1920 MP4 with Hardsub Gaussian blur, ASS subtitles & anti-copyright."""
    src_mp4, master_wav, ass_file = _make_source_video_and_audio(tmp_path)

    clip = ClipSpecDTO(
        clip_id="clip_m06_movie",
        project_id="proj_m06",
        part_number=1,
        source_start_ms=0,
        source_end_ms=2200,
        hook_banner_title="Tổng Tài Báo Thù | Phần 1",
        lines=[NarrationLineDTO(seq_index=0, rel_start_ms=100, rel_end_ms=2000, vi_text="Thử nghiệm")],
        append_cta_outro=True,
    )
    audio_sub = MasterAudioAndSubDTO(
        clip_id="clip_m06_movie",
        master_audio_wav_path=master_wav,
        ass_subtitle_path=ass_file,
        total_audio_duration_ms=2200,
    )
    layout_cfg = LayoutAndAntiCopyConfigDTO(
        layout_type=LayoutType.BLUR_CENTER,
        hardsub_mask_enabled=True,
        hardsub_rect=NormalizedRectDTO(x=0.05, y=0.78, w=0.90, h=0.12, mode=HardsubMaskMode.BLUR),
        anti_copyright_enabled=True,
        speed_factor=1.05,
        mirror_flip=True,
    )
    spec = RenderJobSpecDTO(
        clip=clip,
        source_video_path=src_mp4,
        audio_sub=audio_sub,
        layout_config=layout_cfg,
        output_dir=tmp_path / "outputs",
        prefer_nvenc=True,
    )

    compositor = FFmpegNVENCCompositor()
    out = await compositor.render(spec)

    assert out.output_mp4_path.exists()
    assert out.cover_jpg_path is not None and out.cover_jpg_path.exists()
    assert out.encoder_used in ("h264_nvenc", "libx264")
    with Image.open(out.cover_jpg_path) as cov:
        assert cov.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


@pytest.mark.asyncio
async def test_m06_render_topic_ken_burns_visuals(tmp_path: Path) -> None:
    """Verify M06 renders Topic-to-Video AI Images with Ken Burns motion into 1080x1920 MP4."""
    _, master_wav, ass_file = _make_source_video_and_audio(tmp_path)
    img1 = tmp_path / "s1.png"
    Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (30, 58, 138)).save(img1)

    clip = ClipSpecDTO(
        clip_id="clip_m06_topic",
        project_id="proj_m06_t",
        part_number=1,
        source_start_ms=0,
        source_end_ms=2000,
        hook_banner_title="Bí Mật Vũ Trụ",
        lines=[NarrationLineDTO(seq_index=0, rel_start_ms=0, rel_end_ms=2000, vi_text="Khám phá sao Hỏa")],
        append_cta_outro=False,
    )
    visuals = VisualAssetListDTO(
        clip_id="clip_m06_topic",
        items=[
            SceneVisualItemDTO(
                seq_index=0,
                asset_path=img1,
                asset_type=AssetType.IMAGE,
                duration_ms=2000,
                motion_effect=MotionEffect.ZOOM_IN,
            )
        ],
    )
    audio_sub = MasterAudioAndSubDTO(
        clip_id="clip_m06_topic",
        master_audio_wav_path=master_wav,
        ass_subtitle_path=ass_file,
        total_audio_duration_ms=2000,
    )
    spec = RenderJobSpecDTO(
        clip=clip,
        visual_assets=visuals,
        audio_sub=audio_sub,
        output_dir=tmp_path / "outputs_topic",
        prefer_nvenc=True,
    )

    compositor = FFmpegNVENCCompositor()
    out = await compositor.render(spec)
    assert out.output_mp4_path.exists()
    assert out.output_mp4_path.stat().st_size > 4096

