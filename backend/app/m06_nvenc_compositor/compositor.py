"""FFmpeg & Sub-Pixel OpenCV CapCut-Grade Compositor implementing `IVideoCompositor` (M06)."""

import asyncio
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import List, Optional
import wave
import cv2
import numpy as np

from app.m00_core_contracts import (
    AssetType,
    CoverTemplateStyle,
    GPUResourceManager,
    HardsubMaskMode,
    IVideoCompositor,
    LayoutType,
    MotionEffect,
    NVENC_CQ,
    NVENC_PRESET,
    ProgressCallback,
    RenderJobSpecDTO,
    RenderOutputDTO,
    SceneVisualItemDTO,
    TARGET_FPS,
    TransitionStyle,
    VideoCompositorError,
    resolve_aspect_dimensions,
)

from .layout_strategies import LayoutStrategyFactory
from .overlay_artist import StudioOverlayArtist

FFMPEG_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
TRANSITION_FRAMES = 12  # 0.40s silky CapCut transition at 30fps


def _parse_ffmpeg_progress_ms(line: str) -> Optional[int]:
    m = FFMPEG_TIME_RE.search(line)
    if not m:
        return None
    h, m_val, s_val = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return int(round(((h * 3600) + (m_val * 60) + s_val) * 1000.0))


def _subpixel_scale_center(img_bgr: np.ndarray, scale: float) -> np.ndarray:
    """True floating-point sub-pixel center zoom using C++ bilinear warp (0.0px jitter)."""
    if abs(scale - 1.0) < 1e-4:
        return img_bgr
    h, w = img_bgr.shape[:2]
    cx, cy = w * 0.5, h * 0.5
    mat = np.array(
        [
            [scale, 0.0, cx * (1.0 - scale)],
            [0.0, scale, cy * (1.0 - scale)],
        ],
        dtype=np.float32,
    )
    return cv2.warpAffine(
        img_bgr, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
    )


def _blend_capcut_transition(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    t: float,
    style: TransitionStyle,
) -> np.ndarray:
    """Render a single transition frame `t in (0.0, 1.0)` between outgoing `frame_a` and incoming `frame_b`."""
    # Smooth S-curve easing
    s = t * t * (3.0 - 2.0 * t)
    h, w = frame_a.shape[:2]

    if style == TransitionStyle.CAPCUT_SMOOTH_SLIDE:
        # Cubic whip ease-out slide with subtle horizontal motion softening at mid-whip
        ease = 1.0 - (1.0 - t) ** 3
        shift = int(round(ease * w))
        if shift <= 0:
            return frame_a
        if shift >= w:
            return frame_b
        out = np.empty_like(frame_a)
        out[:, : w - shift] = frame_a[:, shift:]
        out[:, w - shift :] = frame_b[:, :shift]
        # Subtle motion blur during peak velocity (0.2 < t < 0.75)
        if 0.18 < t < 0.72:
            out = cv2.blur(out, (9, 1))
        return out

    if style == TransitionStyle.CAPCUT_ZOOM_FLOW:
        zoom_a = _subpixel_scale_center(frame_a, 1.0 + 0.09 * s)
        zoom_b = _subpixel_scale_center(frame_b, 0.94 + 0.06 * s)
        return cv2.addWeighted(zoom_a, 1.0 - s, zoom_b, s, 0.0)

    if style == TransitionStyle.CAPCUT_FLASH_BEAT:
        mixed = cv2.addWeighted(frame_a, 1.0 - s, frame_b, s, 0.0)
        bloom = float(math.sin(math.pi * t) * 34.0)
        return cv2.convertScaleAbs(mixed, alpha=1.0, beta=bloom)

    # CAPCUT_DISSOLVE & STATIC_LOOKBOOK: Silky S-curve cross-dissolve
    return cv2.addWeighted(frame_a, 1.0 - s, frame_b, s, 0.0)


def _load_unicode_image_bgr(path: Path, target_w: int, target_h: int) -> np.ndarray:
    """UTF-8 safe image reader on Windows returning `(target_h, target_w, 3)` BGR uint8."""
    raw_bytes = np.fromfile(str(path), dtype=np.uint8)
    decoded = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
    if decoded is None:
        raise VideoCompositorError(f"Không thể đọc tệp ảnh: {path.name}")
    if decoded.shape[1] != target_w or decoded.shape[0] != target_h:
        decoded = cv2.resize(decoded, (target_w, target_h), interpolation=cv2.INTER_AREA)
    return decoded


def _compute_soundwave_bars(wav_path: Optional[Path], total_frames: int, n_bars: int = 32) -> np.ndarray:
    """Compute smoothed `(total_frames, n_bars)` normalized heights `[0.08..1.0]` from a WAV file."""
    heights = np.full((max(total_frames, 1), n_bars), 0.12, dtype=np.float32)
    if wav_path is None or not wav_path.exists():
        return heights
    try:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            pcm = pcm.reshape(-1, ch).mean(axis=1)
        if pcm.size < 64:
            return heights

        samples_per_frame = max(64, int(round(sr / float(TARGET_FPS))))
        half = n_bars // 2
        prev_row = np.full(n_bars, 0.12, dtype=np.float32)

        for f_i in range(total_frames):
            s0 = (f_i * samples_per_frame) % max(1, pcm.size - samples_per_frame)
            seg = pcm[s0 : s0 + samples_per_frame]
            if seg.size < 32:
                heights[f_i] = prev_row
                continue
            spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size)))
            useful = spec[1 : min(spec.size, 180)]
            if useful.size < half:
                useful = np.pad(useful, (0, half - useful.size))
            splits = np.array_split(useful, half)
            band_vals = np.array([float(np.mean(b)) for b in splits], dtype=np.float32)
            peak = max(float(np.percentile(band_vals, 95)), 0.08)
            norm_half = np.clip((band_vals / max(peak * 1.15, 0.12)) ** 0.72, 0.08, 1.0)
            # Symmetrical acoustic mirror from center outward (classic violin spectrum look)
            sym = np.concatenate((norm_half[::-1], norm_half))
            smoothed = 0.58 * prev_row + 0.42 * sym[:n_bars]
            heights[f_i] = smoothed
            prev_row = smoothed
    except Exception:
        pass
    return heights


def _draw_acoustic_soundwave_bgr(frame_bgr: np.ndarray, bar_heights: np.ndarray) -> np.ndarray:
    """Overlay a refined Champagne-Gold acoustic waveform bar strip onto a copy of `frame_bgr`."""
    out = frame_bgr.copy()
    h, w = out.shape[:2]
    n_bars = len(bar_heights)
    strip_w = int(w * 0.62)
    max_bar_h = int(h * 0.075)
    center_y = int(h * 0.76)
    start_x = (w - strip_w) // 2
    step_x = strip_w / float(max(n_bars, 1))
    bar_thick = max(4, int(step_x * 0.46))

    # Subtle dark smoked capsule behind waveform so gold bars shimmer on bright wood too
    pad_x, pad_y = 24, max_bar_h // 2 + 16
    x0, y0 = max(0, start_x - pad_x), max(0, center_y - pad_y)
    x1, y1 = min(w, start_x + strip_w + pad_x), min(h, center_y + pad_y)
    roi = out[y0:y1, x0:x1]
    dark_box = np.full_like(roi, (18, 15, 12))
    out[y0:y1, x0:x1] = cv2.addWeighted(roi, 0.52, dark_box, 0.48, 0.0)

    for i, val in enumerate(bar_heights):
        cx = int(round(start_x + (i + 0.5) * step_x))
        half_bh = max(3, int(round(float(val) * (max_bar_h * 0.5))))
        cv2.line(
            out,
            (cx, center_y - half_bh),
            (cx, center_y + half_bh),
            (108, 196, 244),  # Warm Champagne Gold in BGR
            thickness=bar_thick,
            lineType=cv2.LINE_AA,
        )
    return out


class FFmpegNVENCCompositor(IVideoCompositor):
    """Composes 9:16, 4:5, or 1:1 MP4s with Sub-Pixel CapCut Transitions, Hardsub masking,
    ASS subtitles, and hardware/CPU encoding.
    """

    def __init__(self, gpu_manager: Optional[GPUResourceManager] = None) -> None:
        self._gpu_manager = gpu_manager or GPUResourceManager()

    async def render(
        self,
        spec: RenderJobSpecDTO,
        on_progress: Optional[ProgressCallback] = None,
    ) -> RenderOutputDTO:
        spec.output_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix=f"sv_render_{spec.clip.part_number:02d}_"))

        out_mp4 = spec.output_dir / f"Part_{spec.clip.part_number:02d}.mp4"
        cover_jpg = spec.output_dir / f"Part_{spec.clip.part_number:02d}_cover.jpg"

        try:
            return await asyncio.to_thread(
                self._render_sync, spec, work_dir, out_mp4, cover_jpg, on_progress
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _render_sync(
        self,
        spec: RenderJobSpecDTO,
        work_dir: Path,
        out_mp4: Path,
        cover_jpg: Path,
        on_progress: Optional[ProgressCallback],
    ) -> RenderOutputDTO:
        use_nvenc = spec.prefer_nvenc and self._gpu_manager.is_nvenc_available()
        canvas_w, canvas_h = resolve_aspect_dimensions(spec.layout_config.aspect_ratio)

        # 1. Prepare base video stream (Movie slice OR Sub-Pixel CapCut Visual Showcase)
        cfg_l = spec.layout_config
        has_luxury_outro = bool(
            cfg_l.outro_card_enabled
            and (
                cfg_l.outro_brand_title.strip()
                or cfg_l.outro_subtitle.strip()
                or cfg_l.outro_contact_line.strip()
                or cfg_l.logo_path
            )
        )
        outro_extra_ms = int(cfg_l.outro_duration_ms) if has_luxury_outro else 0

        is_threads_overlay_mode = (
            spec.source_video_path is not None and spec.visual_assets is not None
        )
        is_topic_mode = (
            is_threads_overlay_mode
            or (spec.source_video_path is None and spec.visual_assets is not None)
        )
        if is_threads_overlay_mode and spec.visual_assets is not None and spec.source_video_path is not None:
            base_video = self._assemble_threads_bg_and_cards(
                bg_video_path=spec.source_video_path,
                card_items=list(spec.visual_assets.items),
                outro_png=(
                    StudioOverlayArtist.create_luxury_outro_plate(
                        out_png=work_dir / "luxury_outro.png",
                        brand_title=cfg_l.outro_brand_title or spec.clip.hook_banner_title,
                        subtitle=cfg_l.outro_subtitle,
                        contact_line=cfg_l.outro_contact_line or cfg_l.sales_contact_info,
                        logo_path=cfg_l.logo_path,
                        qr_code_content=cfg_l.qr_code_content,
                        qr_code_label=cfg_l.qr_code_label,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                    )
                    if has_luxury_outro
                    else None
                ),
                outro_extra_ms=outro_extra_ms,
                bg_dim=float(cfg_l.threads_bg_dim),
                work_dir=work_dir,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                use_nvenc=use_nvenc,
            )
            clip_start_sec = 0.0
            raw_dur_ms = max(
                sum(it.duration_ms for it in spec.visual_assets.items) + outro_extra_ms,
                spec.audio_sub.total_audio_duration_ms,
            )
        elif is_topic_mode and spec.visual_assets is not None:
            eff_items = list(spec.visual_assets.items)
            if has_luxury_outro:
                outro_png = StudioOverlayArtist.create_luxury_outro_plate(
                    out_png=work_dir / "luxury_outro.png",
                    brand_title=cfg_l.outro_brand_title or spec.clip.hook_banner_title,
                    subtitle=cfg_l.outro_subtitle,
                    contact_line=cfg_l.outro_contact_line or cfg_l.sales_contact_info,
                    logo_path=cfg_l.logo_path,
                    qr_code_content=cfg_l.qr_code_content,
                    qr_code_label=cfg_l.qr_code_label,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                )
                eff_items.append(
                    SceneVisualItemDTO(
                        seq_index=len(eff_items),
                        asset_path=outro_png,
                        asset_type=AssetType.IMAGE,
                        duration_ms=outro_extra_ms,
                        motion_effect=MotionEffect.NONE,
                    )
                )

            base_video = self._assemble_capcut_visuals(
                items=eff_items,
                work_dir=work_dir,
                transition_style=spec.layout_config.transition_style,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                use_nvenc=use_nvenc,
            )
            clip_start_sec = 0.0
            raw_dur_ms = max(
                sum(it.duration_ms for it in eff_items),
                spec.audio_sub.total_audio_duration_ms,
            )
        else:
            assert spec.source_video_path is not None
            base_video = spec.source_video_path
            clip_start_sec = spec.clip.source_start_ms / 1000.0
            raw_dur_ms = max(spec.clip.duration_ms, spec.audio_sub.total_audio_duration_ms)

        # 2. Copy `.ass` subtitle into `work_dir/subs.ass`
        has_ass = False
        if spec.audio_sub.ass_subtitle_path and spec.audio_sub.ass_subtitle_path.exists():
            shutil.copyfile(spec.audio_sub.ass_subtitle_path, work_dir / "subs.ass")
            has_ass = True

        # 3. Render static overlay (respects `show_top_banner`!)
        banner_txt = (
            spec.layout_config.top_banner_template.replace(
                "{hook_banner_title}", spec.clip.hook_banner_title
            )
            .replace("{part_number}", str(spec.clip.part_number))
            .replace("{So_Phan}", str(spec.clip.part_number))
            .replace("{Ten_Phim}", spec.clip.hook_banner_title)
        )
        static_ovr = StudioOverlayArtist.create_static_overlay(
            out_png=work_dir / "static_ovr.png",
            banner_text=banner_txt,
            show_top_banner=spec.layout_config.show_top_banner,
            logo_path=spec.layout_config.logo_path,
            logo_pos_x=spec.layout_config.logo_pos_x,
            logo_pos_y=spec.layout_config.logo_pos_y,
            sales_badge_enabled=spec.layout_config.sales_badge_enabled,
            sales_price_or_offer=spec.layout_config.sales_price_or_offer,
            sales_contact_info=spec.layout_config.sales_contact_info,
            qr_code_content=spec.layout_config.qr_code_content,
            qr_code_label=spec.layout_config.qr_code_label,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        )

        cta_ovr: Optional[Path] = None
        if spec.clip.append_cta_outro:
            cta_ovr = StudioOverlayArtist.create_cta_outro_overlay(
                out_png=work_dir / "cta_ovr.png",
                next_part_number=spec.clip.part_number + 1,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
            )

        # 4. Compose final video + master audio + overlays + ASS subtitles
        encoders_to_try = ["h264_nvenc", "libx264"] if use_nvenc else ["libx264"]
        last_err = ""
        t0 = time.perf_counter()
        chosen_encoder = encoders_to_try[0]

        for enc in encoders_to_try:
            chosen_encoder = enc
            ok, err_msg = self._run_ffmpeg_compose(
                spec=spec,
                is_topic_mode=is_topic_mode,
                base_video=base_video,
                clip_start_sec=clip_start_sec,
                raw_dur_ms=raw_dur_ms,
                outro_extra_ms=outro_extra_ms,
                has_ass=has_ass,
                static_ovr=static_ovr,
                cta_ovr=cta_ovr,
                work_dir=work_dir,
                out_mp4=out_mp4,
                encoder=enc,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                on_progress=on_progress,
            )
            if ok and out_mp4.exists() and out_mp4.stat().st_size > 1024:
                break
            last_err = err_msg
        else:
            raise VideoCompositorError(f"Kết xuất video thất bại: {last_err[-400:]}")

        elapsed = max(time.perf_counter() - t0, 0.05)
        speed = (
            float(spec.layout_config.speed_factor)
            if spec.layout_config.anti_copyright_enabled
            else 1.0
        )
        final_dur_ms = max(500, int(round(raw_dur_ms / max(speed, 0.5))))
        est_frames = (final_dur_ms / 1000.0) * TARGET_FPS
        avg_fps = round(est_frames / elapsed, 1)

        # 5. Generate Cover Studio Poster (supports custom photo index + TikTok grid headline)
        eff_cover_head = cfg_l.cover_headline.strip()
        if not eff_cover_head and cfg_l.cover_style != CoverTemplateStyle.CLEAN_POSTER:
            eff_cover_head = spec.clip.hook_banner_title

        poster_done = False
        if (
            is_topic_mode
            and not is_threads_overlay_mode
            and spec.visual_assets is not None
            and spec.visual_assets.items
        ):
            img_items = [
                it for it in spec.visual_assets.items if it.asset_type == AssetType.IMAGE
            ]
            if img_items:
                chosen_cov_it = img_items[min(cfg_l.cover_photo_index, len(img_items) - 1)]
                poster_done = (
                    StudioOverlayArtist.create_product_poster_cover(
                        base_plate_png=chosen_cov_it.asset_path,
                        static_overlay_png=static_ovr,
                        out_cover_jpg=cover_jpg,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                        cover_style=cfg_l.cover_style,
                        cover_headline=eff_cover_head,
                        cover_badge_text=cfg_l.cover_badge_text,
                    )
                    is not None
                )
        if not poster_done:
            self._extract_cover_jpg(out_mp4, cover_jpg)
            StudioOverlayArtist.decorate_existing_cover_jpg(
                cover_jpg=cover_jpg,
                cover_style=cfg_l.cover_style,
                cover_headline=eff_cover_head,
                cover_badge_text=cfg_l.cover_badge_text,
            )

        if on_progress:
            on_progress(
                "RENDERING_NVENC",
                100.0,
                f"Đã xuất {out_mp4.name} ({chosen_encoder}, {avg_fps} fps)",
            )

        return RenderOutputDTO(
            clip_id=spec.clip.clip_id,
            part_number=spec.clip.part_number,
            output_mp4_path=out_mp4,
            cover_jpg_path=cover_jpg if cover_jpg.exists() else None,
            final_duration_ms=final_dur_ms,
            average_render_fps=avg_fps,
            encoder_used=chosen_encoder,
        )

    @classmethod
    def _assemble_capcut_visuals(
        cls,
        items: List[SceneVisualItemDTO],
        work_dir: Path,
        transition_style: TransitionStyle,
        canvas_w: int,
        canvas_h: int,
        use_nvenc: bool,
    ) -> Path:
        """Stream sub-pixel floating-point Ease-In-Out frames & CapCut transitions directly to FFmpeg."""
        assembled = work_dir / "assembled_visuals.mp4"
        v_enc = (
            ["-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-cq", str(NVENC_CQ)]
            if use_nvenc
            else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "16"]
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{canvas_w}x{canvas_h}",
            "-r",
            str(TARGET_FPS),
            "-i",
            "-",
            *v_enc,
            "-pix_fmt",
            "yuv420p",
            str(assembled),
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        is_static = transition_style == TransitionStyle.STATIC_LOOKBOOK

        def _make_item_frame_sampler(it: SceneVisualItemDTO, total_f: int):
            wave_bars = (
                _compute_soundwave_bars(it.soundwave_audio_path, total_f)
                if it.show_soundwave and it.soundwave_audio_path
                else None
            )

            if it.asset_type == AssetType.IMAGE:
                base_bgr = _load_unicode_image_bgr(it.asset_path, canvas_w, canvas_h)

                def _sample_img(f_idx: int) -> np.ndarray:
                    if is_static or it.motion_effect == MotionEffect.NONE or total_f <= 1:
                        frm = base_bgr
                    else:
                        prog = min(1.0, max(0.0, f_idx / float(max(total_f - 1, 1))))
                        eased = 0.5 * (1.0 - math.cos(math.pi * prog))
                        frm = _subpixel_scale_center(base_bgr, 1.0 + 0.028 * eased)
                    if wave_bars is not None:
                        frm = _draw_acoustic_soundwave_bgr(
                            frm, wave_bars[min(f_idx, len(wave_bars) - 1)]
                        )
                    return frm

                return _sample_img, lambda: None

            cap = cv2.VideoCapture(str(it.asset_path))
            last_valid = [np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)]

            def _sample_vid(f_idx: int) -> np.ndarray:
                ok, frm = cap.read()
                if not ok or frm is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frm = cap.read()
                if ok and frm is not None:
                    if frm.shape[1] != canvas_w or frm.shape[0] != canvas_h:
                        frm = cv2.resize(frm, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)
                    last_valid[0] = frm
                out_f = last_valid[0]
                if wave_bars is not None:
                    out_f = _draw_acoustic_soundwave_bgr(
                        out_f, wave_bars[min(f_idx, len(wave_bars) - 1)]
                    )
                return out_f

            return _sample_vid, cap.release

        counts = [max(18, int(round((it.duration_ms / 1000.0) * TARGET_FPS))) for it in items]
        n_items = len(items)
        transitions = [
            min(TRANSITION_FRAMES, counts[i] // 3, counts[i + 1] // 3)
            if (i + 1) < n_items
            else 0
            for i in range(n_items)
        ]

        samplers = []
        cleanups = []
        for idx, it in enumerate(items):
            tr_prev = transitions[idx - 1] if idx > 0 else 0
            life_frames = tr_prev + counts[idx]
            smp, cln = _make_item_frame_sampler(it, life_frames)
            samplers.append(smp)
            cleanups.append(cln)

        def _write_bgr(frame_arr: np.ndarray) -> None:
            contig = np.ascontiguousarray(frame_arr)
            proc.stdin.write(memoryview(contig))

        try:
            for idx in range(n_items):
                n_f = counts[idx]
                tr_prev = transitions[idx - 1] if idx > 0 else 0
                tr_out = transitions[idx]
                body_len = n_f - tr_out

                # Body frames of clip `idx` continuing seamlessly after incoming transition `tr_prev`
                for b_i in range(body_len):
                    frm = samplers[idx](tr_prev + b_i)
                    _write_bgr(frm)

                # Smooth CapCut transition into clip `idx + 1`
                if tr_out > 0 and (idx + 1) < n_items:
                    for k in range(tr_out):
                        t_frac = (k + 1) / float(tr_out + 1)
                        frm_a = samplers[idx](tr_prev + body_len + k)
                        frm_b = samplers[idx + 1](k)
                        blended = _blend_capcut_transition(frm_a, frm_b, t_frac, transition_style)
                        _write_bgr(blended)
        finally:
            for cln in cleanups:
                cln()
            proc.stdin.close()

        stderr_bytes = proc.stderr.read() if proc.stderr else b""
        proc.wait()
        if proc.returncode != 0 or not assembled.exists():
            if use_nvenc:
                return cls._assemble_capcut_visuals(
                    items, work_dir, transition_style, canvas_w, canvas_h, use_nvenc=False
                )
            raise VideoCompositorError(
                f"Ghép chuyển cảnh CapCut thất bại: {stderr_bytes.decode('utf-8', errors='replace')[-300:]}"
            )
        return assembled

    @classmethod
    def _assemble_threads_bg_and_cards(
        cls,
        bg_video_path: Path,
        card_items: List[SceneVisualItemDTO],
        outro_png: Optional[Path],
        outro_extra_ms: int,
        bg_dim: float,
        work_dir: Path,
        canvas_w: int,
        canvas_h: int,
        use_nvenc: bool,
    ) -> Path:
        """Loop background video seamlessly while popping floating RGBA Threads cards per comment."""
        assembled = work_dir / "assembled_threads.mp4"
        v_enc = (
            ["-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-cq", str(NVENC_CQ)]
            if use_nvenc
            else ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "17"]
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{canvas_w}x{canvas_h}",
            "-r",
            str(TARGET_FPS),
            "-i",
            "-",
            *v_enc,
            "-pix_fmt",
            "yuv420p",
            str(assembled),
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        cap = cv2.VideoCapture(str(bg_video_path))
        last_bg = np.full((canvas_h, canvas_w, 3), (18, 22, 30), dtype=np.uint8)
        bright_keep = max(0.22, min(1.0, 1.0 - float(bg_dim)))

        def _next_bg_frame() -> np.ndarray:
            nonlocal last_bg
            ok, frm = cap.read()
            if not ok or frm is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frm = cap.read()
            if ok and frm is not None:
                fh, fw = frm.shape[:2]
                sc = max(canvas_w / float(max(fw, 1)), canvas_h / float(max(fh, 1)))
                nw, nh = max(canvas_w, int(round(fw * sc))), max(canvas_h, int(round(fh * sc)))
                resized = cv2.resize(frm, (nw, nh), interpolation=cv2.INTER_LINEAR)
                x0 = (nw - canvas_w) // 2
                y0 = (nh - canvas_h) // 2
                cropped = resized[y0 : y0 + canvas_h, x0 : x0 + canvas_w]
                if bright_keep < 0.99:
                    cropped = cv2.convertScaleAbs(cropped, alpha=bright_keep, beta=0.0)
                last_bg = cropped
            return last_bg

        def _load_card_roi(path: Path):
            """Load RGBA card and precompute non-zero alpha bounding box + uint16 premultiplied planes (100x faster)."""
            raw_b = np.fromfile(str(path), dtype=np.uint8)
            bgra = cv2.imdecode(raw_b, cv2.IMREAD_UNCHANGED)
            if bgra is None:
                raise VideoCompositorError(f"Không thể đọc thẻ bình luận: {path.name}")
            if bgra.shape[1] != canvas_w or bgra.shape[0] != canvas_h:
                bgra = cv2.resize(bgra, (canvas_w, canvas_h), interpolation=cv2.INTER_AREA)
            if bgra.shape[2] == 3:
                alpha = np.full((canvas_h, canvas_w, 1), 255, dtype=np.uint8)
                bgra = np.concatenate((bgra, alpha), axis=2)

            nz_y, nz_x = np.where(bgra[:, :, 3] > 1)
            if nz_y.size == 0:
                return None
            y0, y1 = max(0, int(nz_y.min()) - 4), min(canvas_h, int(nz_y.max()) + 5)
            x0, x1 = max(0, int(nz_x.min()) - 4), min(canvas_w, int(nz_x.max()) + 5)
            roi_bgra = bgra[y0:y1, x0:x1]
            a_u16 = roi_bgra[:, :, 3:4].astype(np.uint16)
            inv_a_u16 = 255 - a_u16
            premult_fg_u16 = roi_bgra[:, :, :3].astype(np.uint16) * a_u16
            return (x0, y0, x1, y1, roi_bgra, inv_a_u16, premult_fg_u16)

        def _blend_card_fast(
            bg_bgr: np.ndarray, card_info, pop_scale: float, opacity: float
        ) -> np.ndarray:
            if card_info is None:
                return bg_bgr
            x0, y0, x1, y1, roi_bgra, inv_a_u16, premult_fg_u16 = card_info
            out = bg_bgr.copy()

            if abs(pop_scale - 1.0) <= 1e-3 and opacity >= 0.995:
                bg_roi = out[y0:y1, x0:x1].astype(np.uint16)
                out[y0:y1, x0:x1] = ((bg_roi * inv_a_u16 + premult_fg_u16 + 127) // 255).astype(
                    np.uint8
                )
                return out

            rw, rh = x1 - x0, y1 - y0
            cx, cy = rw * 0.5, rh * 0.5
            mat = np.array(
                [
                    [pop_scale, 0.0, cx * (1.0 - pop_scale)],
                    [0.0, pop_scale, cy * (1.0 - pop_scale)],
                ],
                dtype=np.float32,
            )
            warped_roi = cv2.warpAffine(
                roi_bgra,
                mat,
                (rw, rh),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0),
            )
            op_u16 = max(0, min(255, int(round(opacity * 255.0))))
            a_dyn = (warped_roi[:, :, 3:4].astype(np.uint16) * op_u16) // 255
            inv_dyn = 255 - a_dyn
            fg_dyn = warped_roi[:, :, :3].astype(np.uint16) * a_dyn
            bg_roi = out[y0:y1, x0:x1].astype(np.uint16)
            out[y0:y1, x0:x1] = ((bg_roi * inv_dyn + fg_dyn + 127) // 255).astype(np.uint8)
            return out

        pop_frames = 7  # ~0.23s crisp spring pop-in animation per comment card
        try:
            for it in card_items:
                n_frames = max(18, int(round((it.duration_ms / 1000.0) * TARGET_FPS)))
                card_info = _load_card_roi(it.asset_path)
                for f_i in range(n_frames):
                    bg_f = _next_bg_frame()
                    if f_i < pop_frames:
                        p = (f_i + 1) / float(pop_frames)
                        ease = 1.0 - (1.0 - p) ** 3
                        scale = 0.90 + 0.10 * ease
                        opac = min(1.0, p * 1.25)
                    else:
                        scale = 1.0
                        opac = 1.0
                    composed = _blend_card_fast(bg_f, card_info, scale, opac)
                    proc.stdin.write(memoryview(np.ascontiguousarray(composed)))

            if outro_png is not None and outro_extra_ms > 0:
                outro_bgr = _load_unicode_image_bgr(outro_png, canvas_w, canvas_h)
                outro_frames = max(15, int(round((outro_extra_ms / 1000.0) * TARGET_FPS)))
                for _ in range(outro_frames):
                    proc.stdin.write(memoryview(np.ascontiguousarray(outro_bgr)))
        finally:
            cap.release()
            proc.stdin.close()

        stderr_bytes = proc.stderr.read() if proc.stderr else b""
        proc.wait()
        if proc.returncode != 0 or not assembled.exists():
            if use_nvenc:
                return cls._assemble_threads_bg_and_cards(
                    bg_video_path=bg_video_path,
                    card_items=card_items,
                    outro_png=outro_png,
                    outro_extra_ms=outro_extra_ms,
                    bg_dim=bg_dim,
                    work_dir=work_dir,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    use_nvenc=False,
                )
            raise VideoCompositorError(
                f"Ghép thẻ bình luận Threads thất bại: {stderr_bytes.decode('utf-8', errors='replace')[-300:]}"
            )
        return assembled

    def _run_ffmpeg_compose(
        self,
        spec: RenderJobSpecDTO,
        is_topic_mode: bool,
        base_video: Path,
        clip_start_sec: float,
        raw_dur_ms: int,
        outro_extra_ms: int,
        has_ass: bool,
        static_ovr: Path,
        cta_ovr: Optional[Path],
        work_dir: Path,
        out_mp4: Path,
        encoder: str,
        canvas_w: int,
        canvas_h: int,
        on_progress: Optional[ProgressCallback],
    ) -> tuple[bool, str]:
        dur_sec = max(raw_dur_ms / 1000.0, 0.5)
        cfg = spec.layout_config

        cmd: List[str] = ["ffmpeg", "-y", "-hide_banner", "-nostdin"]
        if clip_start_sec > 0:
            cmd.extend(["-ss", f"{clip_start_sec:.3f}"])
        if is_topic_mode:
            # Pad last frame gracefully if audio slightly outlasts assembled visual track
            cmd.extend(["-i", str(base_video)])
        else:
            cmd.extend(["-t", f"{dur_sec:.3f}", "-i", str(base_video)])

        cmd.extend(["-t", f"{dur_sec:.3f}", "-i", str(spec.audio_sub.master_audio_wav_path)])
        cmd.extend(["-i", str(static_ovr)])
        next_input_idx = 3

        extra_layout_labels: List[str] = []
        if not is_topic_mode and cfg.layout_type == LayoutType.SPLIT_RETENTION:
            if cfg.retention_video_path and cfg.retention_video_path.exists():
                cmd.extend(
                    ["-stream_loop", "-1", "-t", f"{dur_sec:.3f}", "-i", str(cfg.retention_video_path)]
                )
            else:
                cmd.extend(
                    [
                        "-f",
                        "lavfi",
                        "-t",
                        f"{dur_sec:.3f}",
                        "-i",
                        f"gradients=s=1080x880:r={TARGET_FPS}:speed=0.02",
                    ]
                )
            extra_layout_labels.append(f"{next_input_idx}:v")
            next_input_idx += 1

        cta_idx: Optional[int] = None
        if cta_ovr is not None:
            cmd.extend(["-i", str(cta_ovr)])
            cta_idx = next_input_idx
            next_input_idx += 1

        fg_parts: List[str] = [
            f"[0:v]tpad=stop_mode=clone:stop_duration=3.0,trim=duration={dur_sec:.3f},"
            f"fps={TARGET_FPS},format=yuv420p[v_in0]"
            if is_topic_mode
            else f"[0:v]fps={TARGET_FPS},format=yuv420p[v_in0]"
        ]
        cur_v = "v_in0"

        if cfg.anti_copyright_enabled and cfg.mirror_flip and not is_topic_mode:
            fg_parts.append(f"[{cur_v}]hflip[v_mir]")
            cur_v = "v_mir"

        if not is_topic_mode and cfg.hardsub_mask_enabled:
            r = cfg.hardsub_rect
            if r.mode == HardsubMaskMode.DARK_BOX:
                fg_parts.append(
                    f"[{cur_v}]drawbox=x=iw*{r.x:.4f}:y=ih*{r.y:.4f}:"
                    f"w=iw*{r.w:.4f}:h=ih*{r.h:.4f}:color=black@0.82:t=fill[v_masked]"
                )
            else:
                fg_parts.append(
                    f"[{cur_v}]split=2[v_mbase][v_mcrop];"
                    f"[v_mcrop]crop=max(4\\,iw*{r.w:.4f}):max(4\\,ih*{r.h:.4f}):"
                    f"iw*{r.x:.4f}:ih*{r.y:.4f},gblur=sigma=20,eq=brightness=-0.10[v_mblur];"
                    f"[v_mbase][v_mblur]overlay=W*{r.x:.4f}:H*{r.y:.4f}[v_masked]"
                )
            cur_v = "v_masked"

        if is_topic_mode:
            fg_parts.append(f"[{cur_v}]scale={canvas_w}:{canvas_h}[v_framed]")
        else:
            strategy = LayoutStrategyFactory.create(spec)
            fg_parts.append(strategy.build_video_filtergraph(spec, cur_v, extra_layout_labels))
            if (canvas_w, canvas_h) != (1080, 1920):
                fg_parts[-1] = fg_parts[-1].replace("[v_framed]", "[v_fr916]")
                fg_parts.append(
                    f"[v_fr916]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
                    f"crop={canvas_w}:{canvas_h}[v_framed]"
                )
        cur_v = "v_framed"

        if cfg.anti_copyright_enabled:
            fg_parts.append(
                f"[{cur_v}]eq=contrast={cfg.color_contrast:.3f}:"
                f"saturation={cfg.color_saturation:.3f}[v_col]"
            )
            cur_v = "v_col"

        if outro_extra_ms > 0:
            main_end_sec = max(0.3, (raw_dur_ms - outro_extra_ms) / 1000.0)
            fg_parts.append(f"[{cur_v}][2:v]overlay=0:0:enable='lt(t,{main_end_sec:.2f})'[v_ban]")
        else:
            fg_parts.append(f"[{cur_v}][2:v]overlay=0:0[v_ban]")
        cur_v = "v_ban"

        if cta_idx is not None:
            cta_start = max(0.0, dur_sec - 3.2)
            fg_parts.append(
                f"[{cur_v}][{cta_idx}:v]overlay=0:0:enable='gte(t,{cta_start:.2f})'[v_cta]"
            )
            cur_v = "v_cta"

        if has_ass:
            fg_parts.append(f"[{cur_v}]ass=subs.ass[v_sub]")
            cur_v = "v_sub"

        speed = float(cfg.speed_factor) if cfg.anti_copyright_enabled else 1.0
        if abs(speed - 1.0) >= 0.015:
            fg_parts.append(f"[{cur_v}]setpts=PTS/{speed:.4f}[v_out]")
            fg_parts.append(f"[1:a]apad=whole_dur={dur_sec:.3f},atempo={speed:.4f}[a_out]")
        else:
            fg_parts.append(f"[{cur_v}]null[v_out]")
            fg_parts.append(f"[1:a]apad=whole_dur={dur_sec:.3f}[a_out]")

        cmd.extend(["-filter_complex", ";".join(fg_parts)])
        cmd.extend(["-map", "[v_out]", "-map", "[a_out]"])

        if encoder == "h264_nvenc":
            cmd.extend(
                [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    NVENC_PRESET,
                    "-cq",
                    str(NVENC_CQ),
                    "-b:v",
                    "0",
                ]
            )
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"])

        cmd.extend(
            [
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(TARGET_FPS),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-shortest",
                str(out_mp4),
            ]
        )

        proc = subprocess.Popen(
            cmd,
            cwd=str(work_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stderr_lines: List[str] = []
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line)
            if on_progress:
                cur_ms = _parse_ffmpeg_progress_ms(line)
                if cur_ms is not None:
                    pct = min(98.0, round((cur_ms / max(raw_dur_ms, 1)) * 100.0, 1))
                    on_progress(
                        "RENDERING_NVENC",
                        pct,
                        f"Đang xuất Phần {spec.clip.part_number} ({encoder})...",
                    )
        proc.wait()
        return proc.returncode == 0, "".join(stderr_lines[-25:])

    @staticmethod
    def _extract_cover_jpg(mp4_path: Path, cover_jpg: Path) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.5",
            "-i",
            str(mp4_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(cover_jpg),
        ]
        subprocess.run(cmd, capture_output=True, check=False)
