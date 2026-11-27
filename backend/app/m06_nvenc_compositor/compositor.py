"""FFmpeg & Sub-Pixel OpenCV CapCut-Grade Compositor implementing `IVideoCompositor` (M06)."""

import asyncio
import json
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


def _detect_visual_focal_point(img_bgr: np.ndarray) -> tuple[float, float]:
    """Locate human-eye focal point `(fx, fy) in [0.28..0.72, 0.24..0.68]` using face detection
    first, falling back to center-biased Sobel gradient saliency. Runs in <1ms on 180px thumbnail.
    """
    h, w = img_bgr.shape[:2]
    if w < 32 or h < 32:
        return (0.5, 0.46)
    small_w = 180
    small_h = max(32, int(round(h * (small_w / float(w)))))
    gray = cv2.cvtColor(
        cv2.resize(img_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA),
        cv2.COLOR_BGR2GRAY,
    )
    try:
        cascade_file = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if Path(cascade_file).exists():
            faces = cv2.CascadeClassifier(cascade_file).detectMultiScale(
                gray, scaleFactor=1.18, minNeighbors=4
            )
            if len(faces) > 0:
                fx_b, fy_b, fw_b, fh_b = max(faces, key=lambda b: b[2] * b[3])
                cx_r = (fx_b + fw_b * 0.5) / float(small_w)
                cy_r = (fy_b + fh_b * 0.48) / float(small_h)
                return (
                    float(np.clip(cx_r, 0.28, 0.72)),
                    float(np.clip(cy_r, 0.22, 0.66)),
                )
    except Exception:
        pass

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.abs(gx) + np.abs(gy)

    # Smooth central Gaussian prior so edge borders / vignettes never pull the camera off-center
    yy, xx = np.mgrid[0:small_h, 0:small_w].astype(np.float32)
    nx = (xx / float(max(small_w - 1, 1)) - 0.5) / 0.34
    ny = (yy / float(max(small_h - 1, 1)) - 0.45) / 0.34
    prior = np.exp(-0.5 * (nx * nx + ny * ny))
    sal = mag * prior
    total = float(sal.sum())
    if total <= 1e-3:
        return (0.5, 0.46)
    cx_r = float((sal * xx).sum() / total) / float(max(small_w - 1, 1))
    cy_r = float((sal * yy).sum() / total) / float(max(small_h - 1, 1))
    return (
        float(np.clip(cx_r, 0.30, 0.70)),
        float(np.clip(cy_r, 0.25, 0.68)),
    )


def _subpixel_camera_transform(
    img_bgr: np.ndarray,
    scale: float,
    focus_x: float = 0.5,
    focus_y: float = 0.48,
    pan_dx_px: float = 0.0,
    pan_dy_px: float = 0.0,
) -> np.ndarray:
    """Sub-pixel 5-axis focal-point camera warp (`0.0px` integer stepping jitter)."""
    if abs(scale - 1.0) < 1e-4 and abs(pan_dx_px) < 0.05 and abs(pan_dy_px) < 0.05:
        return img_bgr
    h, w = img_bgr.shape[:2]
    eff_scale = max(1.0, float(scale))
    ax = float(np.clip(focus_x, 0.15, 0.85)) * w
    ay = float(np.clip(focus_y, 0.15, 0.85)) * h
    tx = ax * (1.0 - eff_scale) + pan_dx_px
    ty = ay * (1.0 - eff_scale) + pan_dy_px

    # Keep viewport safely inside scaled canvas bounds so border reflections rarely show
    min_tx = w * (1.0 - eff_scale)
    min_ty = h * (1.0 - eff_scale)
    tx = float(np.clip(tx, min_tx, 0.0))
    ty = float(np.clip(ty, min_ty, 0.0))

    mat = np.array(
        [
            [eff_scale, 0.0, tx],
            [0.0, eff_scale, ty],
        ],
        dtype=np.float32,
    )
    return cv2.warpAffine(
        img_bgr, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
    )


def _resolve_scene_transition_style(
    requested: TransitionStyle, idx: int, n_items: int
) -> TransitionStyle:
    """Context-aware Auto Director transition choreography matching human editor rhythm."""
    if requested != TransitionStyle.AUTO_DIRECTOR:
        return requested
    if idx == 0:
        # Crisp, engaging opening hook transition
        return TransitionStyle.CAPCUT_ZOOM_FLOW
    if idx >= max(1, n_items - 2):
        # Calm, smooth landing into final scene / outro
        return TransitionStyle.CAPCUT_DISSOLVE
    body_cycle = (
        TransitionStyle.CAPCUT_DISSOLVE,
        TransitionStyle.CAPCUT_SMOOTH_SLIDE,
        TransitionStyle.CAPCUT_DISSOLVE,
        TransitionStyle.CAPCUT_ZOOM_FLOW,
    )
    return body_cycle[(idx - 1) % len(body_cycle)]


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


def _probe_true_video_fps(video_path: Path, cap: cv2.VideoCapture) -> float:
    """Resolve accurate real-world playback FPS of an uploaded/downloaded video (CFR & VFR safe)."""
    cv_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate,r_frame_rate,nb_frames,duration",
            "-of",
            "json",
            str(video_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        if proc.returncode == 0 and proc.stdout:
            streams = (json.loads(proc.stdout) or {}).get("streams") or []
            if streams:
                st = streams[0]
                nb_f = float(st.get("nb_frames") or 0)
                dur_s = float(st.get("duration") or 0)
                if nb_f > 5 and dur_s > 0.2:
                    computed = nb_f / dur_s
                    if 5.0 <= computed <= 240.0:
                        return computed
                for key in ("avg_frame_rate", "r_frame_rate"):
                    raw_rate = str(st.get(key) or "")
                    if "/" in raw_rate:
                        num_s, den_s = raw_rate.split("/", 1)
                        num_v, den_v = float(num_s or 0), float(den_s or 0)
                        if den_v > 0 and 5.0 <= (num_v / den_v) <= 240.0:
                            return num_v / den_v
    except Exception:
        pass
    if 5.0 <= cv_fps <= 240.0:
        return cv_fps
    return float(TARGET_FPS)


class _RealtimeVideoStepper:
    """Real-time `1.0x` wall-clock video frame sampler preventing slow-motion on 60fps/120fps videos
    and fast-forward on 24fps/25fps videos. Optionally skips pitch-black opening frames (1-3s) while
    preserving 100% original video colors.
    """

    def __init__(
        self,
        video_path: Path,
        target_fps: float = float(TARGET_FPS),
        auto_skip_black_intro: bool = False,
    ) -> None:
        self.cap = cv2.VideoCapture(str(video_path))
        self.target_fps = max(1.0, float(target_fps))
        self.out_dt_ms = 1000.0 / self.target_fps
        self.src_fps = _probe_true_video_fps(video_path, self.cap)
        self.src_dt_ms = 1000.0 / max(5.0, self.src_fps)
        self.half_src_dt_ms = 0.48 * self.src_dt_ms
        self.max_grabs_per_step = max(8, int(math.ceil(self.src_fps / self.target_fps)) + 4)

        self._start_frame_idx = (
            self._detect_black_intro_skip_frame() if auto_skip_black_intro else 0
        )
        self._start_offset_ms = self._start_frame_idx * self.src_dt_ms
        if self._start_frame_idx == 0 and auto_skip_black_intro:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        self._started = False
        self._pts_reliable: Optional[bool] = None
        self._loop_target_ms = 0.0
        self._cur_frame_ms = 0.0
        self._src_idx_in_loop = 0
        self._last_raw_bgr: Optional[np.ndarray] = None

    @staticmethod
    def _is_frame_pitch_black(frm_bgr: np.ndarray) -> bool:
        h, w = frm_bgr.shape[:2]
        if w <= 0 or h <= 0:
            return True
        sub = frm_bgr[:: max(1, h // 48), :: max(1, w // 48)]
        luma = sub.mean(axis=2)
        return float(luma.mean()) < 15.0 and float(luma.std()) < 9.5

    def _detect_black_intro_skip_frame(self) -> int:
        """If frame 0 is pitch-black, scan up to 3.6s (<=45% of clip) to start at first visible frame."""
        if not self.cap.isOpened():
            return 0
        ok0, frm0 = self.cap.read()
        if not ok0 or frm0 is None or not self._is_frame_pitch_black(frm0):
            return 0

        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        max_skip_sec = 3.6
        if total_frames > 10:
            total_sec = total_frames / max(5.0, self.src_fps)
            if total_sec < 2.2:
                return 0
            max_skip_sec = min(3.6, max(0.5, total_sec * 0.45))

        step_frames = max(1, int(round(0.18 * self.src_fps)))
        max_frame_probe = max(2, int(round(max_skip_sec * self.src_fps)))
        for cand_f in range(step_frames, max_frame_probe + 1, step_frames):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, cand_f)
            ok, frm = self.cap.read()
            if not ok or frm is None:
                break
            if not self._is_frame_pitch_black(frm):
                return cand_f
        return 0

    def _rewind_and_read_first(self) -> Optional[np.ndarray]:
        if self._started or self._start_frame_idx > 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._start_frame_idx)
        ok = self.cap.grab()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._start_frame_idx = 0
            self._start_offset_ms = 0.0
            ok = self.cap.grab()
        if not ok:
            return self._last_raw_bgr
        ok_ret, frm = self.cap.retrieve()
        if ok_ret and frm is not None:
            self._last_raw_bgr = frm
        self._started = True
        self._loop_target_ms = 0.0
        self._cur_frame_ms = 0.0
        self._src_idx_in_loop = 0
        return self._last_raw_bgr

    def next_raw_frame(self) -> tuple[Optional[np.ndarray], bool]:
        """Advance by `1 / target_fps` real-time seconds and return `(bgr_frame, is_new_decode)`."""
        if not self._started:
            first = self._rewind_and_read_first()
            return first, True

        self._loop_target_ms += self.out_dt_ms
        threshold_ms = self._loop_target_ms - self.half_src_dt_ms

        # Hold current frame when source FPS < target FPS (e.g. 24fps / 25fps -> 30fps)
        if self._cur_frame_ms >= threshold_ms and self._last_raw_bgr is not None:
            return self._last_raw_bgr, False

        grabs = 0
        while self._cur_frame_ms < threshold_ms and grabs < self.max_grabs_per_step:
            ok = self.cap.grab()
            if not ok:
                # Reached EOF -> loop seamlessly back to clean start frame at real-time pace
                first = self._rewind_and_read_first()
                return first, True
            grabs += 1
            self._src_idx_in_loop += 1
            raw_pos_ms = float(self.cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
            rel_pos_ms = max(0.0, raw_pos_ms - self._start_offset_ms)
            if self._pts_reliable is None and self._src_idx_in_loop == 1:
                self._pts_reliable = 1.0 < rel_pos_ms < 500.0
            if self._pts_reliable and rel_pos_ms > self._cur_frame_ms:
                self._cur_frame_ms = rel_pos_ms
            else:
                self._cur_frame_ms += self.src_dt_ms

        if grabs > 0:
            ok_ret, frm = self.cap.retrieve()
            if ok_ret and frm is not None:
                self._last_raw_bgr = frm
                return self._last_raw_bgr, True
        return self._last_raw_bgr, False

    def release(self) -> None:
        self.cap.release()


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
                auto_skip_black_intro=bool(cfg_l.auto_skip_black_intro),
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
                smart_camera_motion=bool(cfg_l.smart_camera_motion),
                smart_micro_punch_in=bool(cfg_l.smart_micro_punch_in),
                auto_skip_black_intro=bool(cfg_l.auto_skip_black_intro),
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
            safe_zone_guard=bool(spec.layout_config.safe_zone_guard),
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
        smart_camera_motion: bool = True,
        smart_micro_punch_in: bool = True,
        auto_skip_black_intro: bool = True,
    ) -> Path:
        """Stream sub-pixel Saliency Camera frames, Micro Punch-ins & CapCut transitions to FFmpeg."""
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

        # Non-repeating camera sequencer so consecutive image scenes never share identical camera move
        motion_pool = (
            MotionEffect.ZOOM_IN,
            MotionEffect.PAN_RIGHT,
            MotionEffect.ZOOM_OUT,
            MotionEffect.PAN_LEFT,
            MotionEffect.PAN_UP,
        )
        resolved_motions: List[MotionEffect] = []
        prev_m: Optional[MotionEffect] = None
        for s_i, it in enumerate(items):
            if is_static or it.motion_effect == MotionEffect.NONE or it.asset_type != AssetType.IMAGE:
                resolved_motions.append(it.motion_effect)
                prev_m = None
                continue
            cand = it.motion_effect
            if smart_camera_motion and cand == prev_m:
                for alt in motion_pool:
                    if alt != prev_m:
                        cand = alt
                        break
                if cand == prev_m:
                    cand = motion_pool[s_i % len(motion_pool)]
            resolved_motions.append(cand)
            prev_m = cand

        def _compute_micro_punch_bonus(f_idx: int, total_f: int) -> float:
            """Subtle +5.8% mid-sentence focal close-up on long scenes (>6.0s / >180 frames)."""
            if is_static or not smart_micro_punch_in or total_f <= int(6.0 * TARGET_FPS):
                return 0.0
            trigger_f = int(total_f * 0.52)
            if f_idx < trigger_f:
                return 0.0
            ramp_len = max(8, int(0.32 * TARGET_FPS))
            t_p = min(1.0, (f_idx - trigger_f + 1) / float(ramp_len))
            s_p = t_p * t_p * (3.0 - 2.0 * t_p)
            return 0.058 * s_p

        def _make_item_frame_sampler(it: SceneVisualItemDTO, eff_motion: MotionEffect, total_f: int):
            wave_bars = (
                _compute_soundwave_bars(it.soundwave_audio_path, total_f)
                if it.show_soundwave and it.soundwave_audio_path
                else None
            )

            if it.asset_type == AssetType.IMAGE:
                base_bgr = _load_unicode_image_bgr(it.asset_path, canvas_w, canvas_h)
                fx, fy = (
                    _detect_visual_focal_point(base_bgr)
                    if (smart_camera_motion and not is_static)
                    else (0.5, 0.48)
                )

                def _sample_img(f_idx: int) -> np.ndarray:
                    if is_static or eff_motion == MotionEffect.NONE or total_f <= 1:
                        frm = base_bgr
                    else:
                        prog = min(1.0, max(0.0, f_idx / float(max(total_f - 1, 1))))
                        eased = 0.5 * (1.0 - math.cos(math.pi * prog))
                        punch = _compute_micro_punch_bonus(f_idx, total_f)

                        if not smart_camera_motion:
                            frm = _subpixel_scale_center(base_bgr, 1.0 + 0.035 * eased + punch)
                        elif eff_motion == MotionEffect.ZOOM_OUT:
                            sc = 1.074 - 0.068 * eased + punch
                            frm = _subpixel_camera_transform(base_bgr, sc, fx, fy)
                        elif eff_motion == MotionEffect.PAN_RIGHT:
                            sc = 1.068 + punch
                            dx = (eased - 0.5) * (canvas_w * 0.048)
                            frm = _subpixel_camera_transform(base_bgr, sc, fx, fy, pan_dx_px=-dx)
                        elif eff_motion == MotionEffect.PAN_LEFT:
                            sc = 1.068 + punch
                            dx = (eased - 0.5) * (canvas_w * 0.048)
                            frm = _subpixel_camera_transform(base_bgr, sc, fx, fy, pan_dx_px=dx)
                        elif eff_motion in (MotionEffect.PAN_UP, MotionEffect.PAN_DOWN):
                            sc = 1.066 + punch
                            sign = 1.0 if eff_motion == MotionEffect.PAN_UP else -1.0
                            dy = sign * (eased - 0.5) * (canvas_h * 0.036)
                            frm = _subpixel_camera_transform(base_bgr, sc, fx, fy, pan_dy_px=dy)
                        else:
                            # ZOOM_IN toward detected focal subject
                            sc = 1.0 + 0.068 * eased + punch
                            frm = _subpixel_camera_transform(base_bgr, sc, fx, fy)

                    if wave_bars is not None:
                        frm = _draw_acoustic_soundwave_bgr(
                            frm, wave_bars[min(f_idx, len(wave_bars) - 1)]
                        )
                    return frm

                return _sample_img, lambda: None

            stepper = _RealtimeVideoStepper(
                it.asset_path,
                target_fps=float(TARGET_FPS),
                auto_skip_black_intro=auto_skip_black_intro,
            )
            last_valid = [np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)]
            vid_focal: List[Optional[tuple[float, float]]] = [None]

            def _sample_vid(f_idx: int) -> np.ndarray:
                frm, is_new = stepper.next_raw_frame()
                if is_new and frm is not None:
                    if frm.shape[1] != canvas_w or frm.shape[0] != canvas_h:
                        # Smart aspect-fill center crop so landscape stock clips never stretch
                        fh, fw = frm.shape[:2]
                        sc_fill = max(canvas_w / float(max(fw, 1)), canvas_h / float(max(fh, 1)))
                        nw = max(canvas_w, int(round(fw * sc_fill)))
                        nh = max(canvas_h, int(round(fh * sc_fill)))
                        rsz = cv2.resize(frm, (nw, nh), interpolation=cv2.INTER_LINEAR)
                        x0 = (nw - canvas_w) // 2
                        y0 = (nh - canvas_h) // 2
                        frm = rsz[y0 : y0 + canvas_h, x0 : x0 + canvas_w]
                    last_valid[0] = frm
                    if vid_focal[0] is None and smart_camera_motion:
                        vid_focal[0] = _detect_visual_focal_point(frm)

                out_f = last_valid[0]
                punch = _compute_micro_punch_bonus(f_idx, total_f)
                if punch > 1e-4:
                    v_fx, v_fy = vid_focal[0] or (0.5, 0.46)
                    out_f = _subpixel_camera_transform(out_f, 1.0 + punch, v_fx, v_fy)
                if wave_bars is not None:
                    out_f = _draw_acoustic_soundwave_bgr(
                        out_f, wave_bars[min(f_idx, len(wave_bars) - 1)]
                    )
                return out_f

            return _sample_vid, stepper.release

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
            smp, cln = _make_item_frame_sampler(it, resolved_motions[idx], life_frames)
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

                # Smooth CapCut / Auto-Director transition into clip `idx + 1`
                if tr_out > 0 and (idx + 1) < n_items:
                    scene_tr_style = _resolve_scene_transition_style(transition_style, idx, n_items)
                    for k in range(tr_out):
                        t_frac = (k + 1) / float(tr_out + 1)
                        frm_a = samplers[idx](tr_prev + body_len + k)
                        frm_b = samplers[idx + 1](k)
                        blended = _blend_capcut_transition(frm_a, frm_b, t_frac, scene_tr_style)
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
                    items,
                    work_dir,
                    transition_style,
                    canvas_w,
                    canvas_h,
                    use_nvenc=False,
                    smart_camera_motion=smart_camera_motion,
                    smart_micro_punch_in=smart_micro_punch_in,
                    auto_skip_black_intro=auto_skip_black_intro,
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
        auto_skip_black_intro: bool = True,
    ) -> Path:
        """Loop background video at 1.0x real-time (100% original color fidelity) while animating
        floating RGBA Threads cards with Slide-up Spring entry, smooth eye-guide sentence crossfades,
        and gentle Smooth Exit.
        """
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

        stepper = _RealtimeVideoStepper(
            bg_video_path,
            target_fps=float(TARGET_FPS),
            auto_skip_black_intro=auto_skip_black_intro,
        )
        last_bg = np.full((canvas_h, canvas_w, 3), (18, 22, 30), dtype=np.uint8)
        bright_keep = max(0.22, min(1.0, 1.0 - float(bg_dim)))

        def _next_bg_frame() -> np.ndarray:
            nonlocal last_bg
            frm, is_new = stepper.next_raw_frame()
            if is_new and frm is not None:
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
            """Load RGBA card and precompute non-zero alpha bounding box + uint16 premultiplied planes."""
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
            bg_bgr: np.ndarray,
            card_info,
            pop_scale: float,
            opacity: float,
            dy_px: float = 0.0,
        ) -> np.ndarray:
            if card_info is None:
                return bg_bgr
            x0, y0, x1, y1, roi_bgra, inv_a_u16, premult_fg_u16 = card_info
            out = bg_bgr.copy()

            if abs(pop_scale - 1.0) <= 1e-3 and opacity >= 0.995 and abs(dy_px) < 0.4:
                bg_roi = out[y0:y1, x0:x1].astype(np.uint16)
                out[y0:y1, x0:x1] = ((bg_roi * inv_a_u16 + premult_fg_u16 + 127) // 255).astype(
                    np.uint8
                )
                return out

            # Expand destination ROI slightly to accommodate Slide-Up (+dy) and Exit (-dy) without clipping
            pad_y = int(math.ceil(abs(dy_px))) + 14
            dy0 = max(0, y0 - pad_y)
            dy1 = min(canvas_h, y1 + pad_y)
            rw, rh = x1 - x0, dy1 - dy0
            if rw <= 2 or rh <= 2:
                return out

            padded_rgba = np.zeros((rh, rw, 4), dtype=np.uint8)
            ins_y0 = y0 - dy0
            ins_y1 = ins_y0 + (y1 - y0)
            padded_rgba[ins_y0:ins_y1, :] = roi_bgra

            cx, cy = rw * 0.5, ins_y0 + (y1 - y0) * 0.5
            mat = np.array(
                [
                    [pop_scale, 0.0, cx * (1.0 - pop_scale)],
                    [0.0, pop_scale, cy * (1.0 - pop_scale) + float(dy_px)],
                ],
                dtype=np.float32,
            )
            warped_roi = cv2.warpAffine(
                padded_rgba,
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
            bg_roi = out[dy0:dy1, x0:x1].astype(np.uint16)
            out[dy0:dy1, x0:x1] = ((bg_roi * inv_dyn + fg_dyn + 127) // 255).astype(np.uint8)
            return out

        entry_frames = 8  # ~0.27s Slide-up + soft spring entry
        exit_frames = 5  # ~0.16s gentle float-out exit
        hl_fade_frames = 5  # ~0.16s smooth eye-guide sentence highlight glide
        prev_card_info = None
        try:
            n_cards = len(card_items)
            for idx, it in enumerate(card_items):
                is_first_in_group = (
                    idx == 0
                    or it.card_group_id is None
                    or it.card_group_id != card_items[idx - 1].card_group_id
                )
                is_last_in_group = (
                    idx == n_cards - 1
                    or it.card_group_id is None
                    or it.card_group_id != card_items[idx + 1].card_group_id
                )
                min_f = 18 if (is_first_in_group and is_last_in_group) else 10
                n_frames = max(min_f, int(round((it.duration_ms / 1000.0) * TARGET_FPS)))
                card_info = _load_card_roi(it.asset_path)

                for f_i in range(n_frames):
                    bg_f = _next_bg_frame()
                    if is_first_in_group and f_i < entry_frames:
                        p = (f_i + 1) / float(entry_frames)
                        inv = 1.0 - p
                        # Slide up +28px -> 0px with subtle spring settle (0.935 -> 1.008 -> 1.00)
                        scale = 1.0 - 0.065 * (inv**3) + 0.012 * math.sin(math.pi * p)
                        dy_px = 28.0 * (inv**2.5)
                        opac = min(1.0, 0.22 + p * 1.15)
                        composed = _blend_card_fast(bg_f, card_info, scale, opac, dy_px=dy_px)
                    elif (
                        not is_first_in_group
                        and prev_card_info is not None
                        and f_i < hl_fade_frames
                    ):
                        # Same comment card: keep geometry 100% locked while cross-fading active sentence
                        alpha = (f_i + 1) / float(hl_fade_frames + 1)
                        frm_prev = _blend_card_fast(bg_f, prev_card_info, 1.0, 1.0, dy_px=0.0)
                        frm_curr = _blend_card_fast(bg_f, card_info, 1.0, 1.0, dy_px=0.0)
                        composed = cv2.addWeighted(frm_prev, 1.0 - alpha, frm_curr, alpha, 0.0)
                    elif is_last_in_group and n_frames >= 16 and f_i >= (n_frames - exit_frames):
                        q = (f_i - (n_frames - exit_frames) + 1) / float(exit_frames + 1)
                        scale = 1.0 - 0.026 * q
                        dy_px = -14.0 * (q**1.5)
                        opac = max(0.16, 1.0 - 0.78 * (q**1.25))
                        composed = _blend_card_fast(bg_f, card_info, scale, opac, dy_px=dy_px)
                    else:
                        composed = _blend_card_fast(bg_f, card_info, 1.0, 1.0, dy_px=0.0)

                    proc.stdin.write(memoryview(np.ascontiguousarray(composed)))

                prev_card_info = card_info

            if outro_png is not None and outro_extra_ms > 0:
                outro_bgr = _load_unicode_image_bgr(outro_png, canvas_w, canvas_h)
                outro_frames = max(15, int(round((outro_extra_ms / 1000.0) * TARGET_FPS)))
                for _ in range(outro_frames):
                    proc.stdin.write(memoryview(np.ascontiguousarray(outro_bgr)))
        finally:
            stepper.release()
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
                    auto_skip_black_intro=auto_skip_black_intro,
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
