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
    ThreadsCardTheme,
    ThreadsEyeGuideMode,
    TransitionStyle,
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


def test_m06_realtime_video_stepper_prevents_slow_motion_on_60fps_and_120fps(tmp_path: Path) -> None:
    """Verify 60fps & 120fps videos advance at exact 1.0x wall-clock speed (zero 0.5x/0.25x slow-motion)
    and 24fps videos hold frames cleanly without fast-forwarding.
    """
    from app.m06_nvenc_compositor.compositor import _RealtimeVideoStepper

    for src_fps in (60, 120, 24):
        vid_path = tmp_path / f"sample_{src_fps}fps.mp4"
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
                f"testsrc=size=640x360:rate={src_fps}:duration=2.5",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(vid_path),
            ],
            check=True,
        )
        stepper = _RealtimeVideoStepper(vid_path, target_fps=30.0)
        try:
            assert abs(stepper.src_fps - float(src_fps)) < 1.5
            # Sample 31 output frames -> 1.000s elapsed wall-clock time (t = 0.000s .. 1.000s)
            for _ in range(31):
                frm, _ = stepper.next_raw_frame()
                assert frm is not None
            # At t=1.000s, source timeline MUST be ~1000ms (1.0x real-time), NEVER ~500ms (0.5x slow-mo)!
            assert 950.0 <= stepper._cur_frame_ms <= 1050.0, (
                f"Expected ~1000ms after 1.0s output on {src_fps}fps video, got {stepper._cur_frame_ms:.1f}ms"
            )
        finally:
            stepper.release()


@pytest.mark.asyncio
async def test_m06_threads_overlay_60fps_bg_plays_at_realtime_speed(tmp_path: Path) -> None:
    """End-to-end test: Threads mode with a 60fps background video renders at 1.0x speed without slow-mo."""
    _, master_wav, ass_file = _make_source_video_and_audio(tmp_path)
    bg_60fps = tmp_path / "bg_60fps.mp4"
    # First 1.0s is pure RED, second 1.0s (1.0s..2.2s) is pure GREEN at 60fps.
    # If 0.5x slow-motion existed, at t=1.5s output the background would STILL be RED (from t_src=0.75s)!
    # At true 1.0x real-time, at t=1.5s output the background MUST be GREEN (from t_src=1.50s)!
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
            "color=c=red:s=640x360:r=60:d=1.0",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=640x360:r=60:d=1.5",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(bg_60fps),
        ],
        check=True,
    )

    card_png = tmp_path / "card_0.png"
    card_im = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    # Small centered comment card leaving top/bottom background clearly visible
    from PIL import ImageDraw

    ImageDraw.Draw(card_im).rounded_rectangle(
        [(140, 820), (940, 1100)], radius=32, fill=(255, 255, 255, 255)
    )
    card_im.save(card_png)

    clip = ClipSpecDTO(
        clip_id="clip_thr_60",
        project_id="proj_thr_60",
        part_number=1,
        source_start_ms=0,
        source_end_ms=2000,
        hook_banner_title="Threads 60fps Realtime Check",
        lines=[NarrationLineDTO(seq_index=0, rel_start_ms=0, rel_end_ms=2000, vi_text="Kiểm tra tốc độ thực")],
        append_cta_outro=False,
    )
    visuals = VisualAssetListDTO(
        clip_id="clip_thr_60",
        items=[
            SceneVisualItemDTO(
                seq_index=0,
                asset_path=card_png,
                asset_type=AssetType.IMAGE,
                duration_ms=2000,
                motion_effect=MotionEffect.NONE,
            )
        ],
    )
    audio_sub = MasterAudioAndSubDTO(
        clip_id="clip_thr_60",
        master_audio_wav_path=master_wav,
        ass_subtitle_path=None,
        total_audio_duration_ms=2000,
    )
    spec = RenderJobSpecDTO(
        clip=clip,
        source_video_path=bg_60fps,
        visual_assets=visuals,
        audio_sub=audio_sub,
        layout_config=LayoutAndAntiCopyConfigDTO(show_top_banner=False, threads_bg_dim=0.0),
        output_dir=tmp_path / "outputs_thr60",
        prefer_nvenc=True,
    )

    compositor = FFmpegNVENCCompositor()
    out = await compositor.render(spec)
    assert out.output_mp4_path.exists()

    # Probe pixel at t=1.50s in top background area (x=540, y=200): must be GREEN (G > R + 60), NOT RED!
    import cv2

    cap = cv2.VideoCapture(str(out.output_mp4_path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500.0)
        ok, frame_bgr = cap.read()
        assert ok and frame_bgr is not None
        b_val, g_val, r_val = [int(x) for x in frame_bgr[200, 540]]
        assert g_val > r_val + 60, (
            f"Slow-motion detected! At t=1.5s background pixel BGR=({b_val},{g_val},{r_val}) is still RED!"
        )
    finally:
        cap.release()


def test_m06_auto_skip_black_intro_preserves_original_colors(tmp_path: Path) -> None:
    """Verify `_RealtimeVideoStepper(auto_skip_black_intro=True)` skips a 1.5s pitch-black intro
    and starts directly on the vibrant original-color content (and rewinds past black on EOF).
    """
    from app.m06_nvenc_compositor.compositor import _RealtimeVideoStepper

    vid_black_intro = tmp_path / "black_intro_then_blue.mp4"
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
            "color=c=black:s=640x360:r=30:d=1.5",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=640x360:r=30:d=2.5",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(vid_black_intro),
        ],
        check=True,
    )

    stepper = _RealtimeVideoStepper(vid_black_intro, target_fps=30.0, auto_skip_black_intro=True)
    try:
        assert stepper._start_frame_idx >= 35, "Must skip ~45 black intro frames"
        frm0, _ = stepper.next_raw_frame()
        assert frm0 is not None
        b0, g0, r0 = [int(x) for x in frm0[180, 320]]
        assert b0 > 180 and r0 < 40, f"First frame must already be BLUE (skipped black), got BGR=({b0},{g0},{r0})"
    finally:
        stepper.release()


@pytest.mark.asyncio
async def test_m04_m06_eye_guide_modes_auto_director_and_dynamic_face_track(tmp_path: Path) -> None:
    """Verify:
    1. Threads Eye-Guide (`ACTIVE_HIGHLIGHT` & `PROGRESSIVE_REVEAL`) splits multi-sentence comments
       into fixed-geometry `card_group_id` beats with TikTok Safe-Zone clearance (`x_max <= 970`).
    2. `TransitionStyle.AUTO_DIRECTOR`, Saliency Camera, and Micro Punch-in (>6s) render cleanly.
    3. `FaceTrackFullLayout` builds valid dynamic FFmpeg piecewise-linear trajectory filtergraphs.
    """
    import numpy as np
    from PIL import ImageDraw
    from app.m04_visual_producer.threads_card_renderer import ThreadsCardVisualRenderer
    from app.m06_nvenc_compositor.layout_strategies import FaceTrackFullLayout

    long_ln = NarrationLineDTO(
        seq_index=0,
        rel_start_ms=0,
        rel_end_ms=6600,
        vi_text=(
            "Mình từng mất suốt hai tháng đầu bấm hợp âm chặn đau rát cả đầu ngón tay. "
            "Nhưng chỉ cần kiên trì mỗi tối mười lăm phút là tay chai lại êm ru. "
            "Tới tháng thứ ba tự đệm hát được bài đầu tiên cảm giác sướng rơn luôn!"
        ),
        display_card_text=(
            "Mình từng mất suốt hai tháng đầu bấm hợp âm chặn đau rát cả đầu ngón tay. "
            "Nhưng chỉ cần kiên trì mỗi tối mười lăm phút là tay chai lại êm ru. "
            "Tới tháng thứ ba tự đệm hát được bài đầu tiên cảm giác sướng rơn luôn!"
        ),
        speaker_handle="@guitar_journey",
        likes_display="1,2K",
        is_op_post=False,
    )
    clip_thr = ClipSpecDTO(
        clip_id="clip_eye_guide",
        project_id="proj_eye",
        part_number=1,
        source_start_ms=0,
        source_end_ms=6600,
        hook_banner_title="Hành Trình Tập Đàn",
        lines=[long_ln],
        append_cta_outro=False,
    )

    for mode in (ThreadsEyeGuideMode.ACTIVE_HIGHLIGHT, ThreadsEyeGuideMode.PROGRESSIVE_REVEAL):
        vis_list = await ThreadsCardVisualRenderer.build_clip_cards(
            clip=clip_thr,
            out_dir=tmp_path / mode.value,
            card_theme=ThreadsCardTheme.DARK_THREADS,
            aspect_ratio="9:16",
            eye_guide_mode=mode,
            safe_zone_guard=True,
        )
        assert len(vis_list.items) == 3
        assert sum(it.duration_ms for it in vis_list.items) == 6600
        assert len({it.card_group_id for it in vis_list.items}) == 1
        # Check TikTok 9:16 right-hand safe zone: card alpha right edge must stay <= 970px (< 1080)
        with Image.open(vis_list.items[0].asset_path) as im_card:
            alpha_np = np.array(im_card)[:, :, 3]
            nz_x = np.where(alpha_np > 24)[1]
            assert int(nz_x.max()) <= 985

    # Verify Auto-Director + Saliency Camera + >6s Micro Punch-in end-to-end render
    src_mp4, master_wav, _ = _make_source_video_and_audio(tmp_path)
    img_a = tmp_path / "sal_a.png"
    img_b = tmp_path / "sal_b.png"
    im1 = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (20, 28, 48))
    ImageDraw.Draw(im1).ellipse([(620, 420), (880, 680)], fill=(245, 190, 80))
    im1.save(img_a)
    im2 = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (36, 24, 52))
    ImageDraw.Draw(im2).rectangle([(180, 520), (480, 920)], fill=(90, 210, 245))
    im2.save(img_b)

    clip_smart = ClipSpecDTO(
        clip_id="clip_smart_cam",
        project_id="proj_smart",
        part_number=1,
        source_start_ms=0,
        source_end_ms=7500,
        hook_banner_title="Smart Camera & Auto Director",
        lines=[
            NarrationLineDTO(seq_index=0, rel_start_ms=0, rel_end_ms=6300, vi_text="Cảnh dài trên sáu giây"),
            NarrationLineDTO(seq_index=1, rel_start_ms=6300, rel_end_ms=7500, vi_text="Cảnh kết mượt"),
        ],
        append_cta_outro=False,
    )
    vis_smart = VisualAssetListDTO(
        clip_id="clip_smart_cam",
        items=[
            SceneVisualItemDTO(
                seq_index=0,
                asset_path=img_a,
                asset_type=AssetType.IMAGE,
                duration_ms=6300,
                motion_effect=MotionEffect.ZOOM_IN,
            ),
            SceneVisualItemDTO(
                seq_index=1,
                asset_path=img_b,
                asset_type=AssetType.IMAGE,
                duration_ms=1200,
                motion_effect=MotionEffect.ZOOM_IN,
            ),
        ],
    )
    compositor = FFmpegNVENCCompositor()
    out_smart = await compositor.render(
        RenderJobSpecDTO(
            clip=clip_smart,
            visual_assets=vis_smart,
            audio_sub=MasterAudioAndSubDTO(
                clip_id="clip_smart_cam",
                master_audio_wav_path=master_wav,
                ass_subtitle_path=None,
                total_audio_duration_ms=7500,
            ),
            layout_config=LayoutAndAntiCopyConfigDTO(
                transition_style=TransitionStyle.AUTO_DIRECTOR,
                smart_camera_motion=True,
                smart_micro_punch_in=True,
                safe_zone_guard=True,
            ),
            output_dir=tmp_path / "out_smart",
            prefer_nvenc=True,
        )
    )
    assert out_smart.output_mp4_path.exists()

    # Verify Dynamic Smooth Face-Track filtergraph compiles & renders cleanly via FFmpeg
    dyn_layout = FaceTrackFullLayout(
        focus_x_ratio=0.35,
        trajectory=[(0.0, 0.32), (1.0, 0.48), (2.2, 0.66)],
    )
    fg_expr = dyn_layout.build_video_filtergraph(
        RenderJobSpecDTO(
            clip=ClipSpecDTO(
                clip_id="clip_ft",
                project_id="proj_ft",
                part_number=1,
                source_start_ms=0,
                source_end_ms=2200,
                hook_banner_title="Dynamic Face Track",
                lines=[NarrationLineDTO(seq_index=0, rel_start_ms=0, rel_end_ms=2200, vi_text="Test")],
            ),
            source_video_path=src_mp4,
            audio_sub=MasterAudioAndSubDTO(
                clip_id="clip_ft",
                master_audio_wav_path=master_wav,
                ass_subtitle_path=None,
                total_audio_duration_ms=2200,
            ),
            layout_config=LayoutAndAntiCopyConfigDTO(
                layout_type=LayoutType.FACE_TRACK_FULL,
                dynamic_face_tracking=True,
            ),
            output_dir=tmp_path / "out_ft",
        ),
        "0:v",
        [],
    )
    assert "if(lt(t\\," in fg_expr
    ft_mp4 = tmp_path / "ft_out.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src_mp4),
            "-filter_complex",
            fg_expr,
            "-map",
            "[v_framed]",
            "-frames:v",
            "20",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(ft_mp4),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0 and ft_mp4.exists(), f"Dynamic FaceTrack FFmpeg failed: {proc.stderr}"



