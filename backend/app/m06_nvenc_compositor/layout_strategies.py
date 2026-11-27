"""Three vertical 9:16 layout strategies inheriting from `BaseLayoutStrategy` (SOLID)."""

from pathlib import Path
from typing import List
import cv2
import numpy as np

from app.m00_core_contracts import (
    BaseLayoutStrategy,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    LayoutType,
    RenderJobSpecDTO,
    TARGET_FPS,
)


class FaceTrajectoryAnalyzer:
    """OpenCV frontal-face focus & gimbal-smooth dynamic trajectory estimator for `FACE_TRACK_FULL`."""

    @staticmethod
    def _sample_raw_face_points(
        video_path: Path, start_ms: int, end_ms: int, max_samples: int = 36
    ) -> List[tuple[float, float]]:
        """Sample `(rel_sec, focus_x_ratio)` pairs across `[start_ms, end_ms]`."""
        if not video_path.exists():
            return []
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)
            pts: List[tuple[float, float]] = []
            span_ms = max(end_ms - start_ms, 500)
            step_ms = max(350, span_ms // max(max_samples, 4))

            for i in range(max_samples + 1):
                ts = start_ms + i * step_ms
                if ts > end_ms:
                    break
                cap.set(cv2.CAP_PROP_POS_MSEC, float(ts))
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                h, w = frame.shape[:2]
                if w <= 0 or h <= 0:
                    continue
                small_w = 360
                small_h = max(1, int(h * (small_w / float(w))))
                gray = cv2.cvtColor(cv2.resize(frame, (small_w, small_h)), cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4)
                if len(faces) > 0:
                    fx, _, fw, _ = max(faces, key=lambda b: b[2] * b[3])
                    cx = (fx + fw / 2.0) / float(small_w)
                    pts.append((round((ts - start_ms) / 1000.0, 3), float(np.clip(cx, 0.16, 0.84))))
            return pts
        except Exception:
            return []
        finally:
            cap.release()

    @classmethod
    def estimate_focus_x_ratio(
        cls, video_path: Path, start_ms: int, end_ms: int, max_samples: int = 16
    ) -> float:
        """Sample frames in `[start_ms, end_ms]` and return smoothed horizontal center in `[0.16, 0.84]`."""
        pts = cls._sample_raw_face_points(video_path, start_ms, end_ms, max_samples=max_samples)
        if not pts:
            return 0.5
        return round(float(np.median([p[1] for p in pts])), 4)

    @classmethod
    def estimate_smooth_trajectory(
        cls, video_path: Path, start_ms: int, end_ms: int, max_keyframes: int = 10
    ) -> List[tuple[float, float]]:
        """Build a gimbal-smooth `(rel_sec, focus_x_ratio)` trajectory with deadzone anti-jitter
        and velocity clamping so `9:16` full-screen movie cuts glide smoothly between speakers.
        """
        raw = cls._sample_raw_face_points(video_path, start_ms, end_ms, max_samples=40)
        if not raw:
            return [(0.0, 0.5)]
        if len(raw) == 1:
            return [(0.0, round(raw[0][1], 4))]

        # 1. Deadzone + velocity-clamped forward EMA
        times = [p[0] for p in raw]
        vals = [p[1] for p in raw]
        fwd: List[float] = [vals[0]]
        max_speed_per_sec = 0.16  # gentle gimbal pan speed
        deadzone = 0.035
        for i in range(1, len(vals)):
            prev = fwd[-1]
            dt = max(0.15, times[i] - times[i - 1])
            diff = vals[i] - prev
            if abs(diff) < deadzone:
                fwd.append(prev)
                continue
            blended = prev + 0.34 * diff
            step_cap = max_speed_per_sec * dt
            clamped = prev + float(np.clip(blended - prev, -step_cap, step_cap))
            fwd.append(clamped)

        # 2. Backward pass for zero phase lag
        smooth = list(fwd)
        for i in range(len(smooth) - 2, -1, -1):
            smooth[i] = 0.65 * smooth[i] + 0.35 * smooth[i + 1]

        # 3. Downsample into at most `max_keyframes` clean control points
        paired = [(round(t, 2), round(float(np.clip(x, 0.16, 0.84)), 4)) for t, x in zip(times, smooth)]
        if max(x for _, x in paired) - min(x for _, x in paired) < 0.03:
            med = round(float(np.median([x for _, x in paired])), 4)
            return [(0.0, med)]

        if len(paired) > max_keyframes:
            idxs = np.linspace(0, len(paired) - 1, max_keyframes).round().astype(int)
            dedup_idxs: List[int] = []
            for k in idxs:
                if not dedup_idxs or dedup_idxs[-1] != int(k):
                    dedup_idxs.append(int(k))
            paired = [paired[k] for k in dedup_idxs]

        if paired[0][0] > 0.0:
            paired[0] = (0.0, paired[0][1])
        return paired


class BlurCenterLayout(BaseLayoutStrategy):
    """Layout 1: Movie centered (with slight zoom) over blurred 9:16 backdrop."""

    def build_video_filtergraph(
        self,
        spec: RenderJobSpecDTO,
        input_video_label: str,
        extra_inputs: List[str],
    ) -> str:
        zoom = max(1.0, float(spec.layout_config.center_zoom_scale))
        scaled_w = int(round(CANVAS_WIDTH * zoom))
        if scaled_w % 2 != 0:
            scaled_w += 1

        return (
            f"[{input_video_label}]split=2[v_bg_in][v_fg_in];"
            f"[v_bg_in]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},gblur=sigma=24,"
            f"eq=brightness=-0.14:saturation=1.10[v_bg];"
            f"[v_fg_in]scale={scaled_w}:-2,crop={CANVAS_WIDTH}:ih:(iw-{CANVAS_WIDTH})/2:0[v_fg];"
            f"[v_bg][v_fg]overlay=(W-w)/2:(H-h)/2[v_framed]"
        )


class FaceTrackFullLayout(BaseLayoutStrategy):
    """Layout 2: Full-screen 9:16 vertical crop locked onto smooth dynamic face trajectory."""

    def __init__(
        self,
        focus_x_ratio: float = 0.5,
        trajectory: List[tuple[float, float]] | None = None,
    ) -> None:
        self.focus_x_ratio = float(np.clip(focus_x_ratio, 0.0, 1.0))
        self.trajectory = trajectory or []

    def _build_focus_ratio_expr(self) -> str:
        pts = self.trajectory
        if len(pts) <= 1:
            r = pts[0][1] if pts else self.focus_x_ratio
            return f"{r:.4f}"
        # Nested piecewise-linear FFmpeg expression `if(lt(t,t1), r0+(r1-r0)*(t-t0)/dt, ...)`
        expr = f"{pts[-1][1]:.4f}"
        for i in range(len(pts) - 2, -1, -1):
            t0, r0 = pts[i]
            t1, r1 = pts[i + 1]
            dt = max(0.05, t1 - t0)
            slope = (r1 - r0) / dt
            seg_expr = f"({r0:.4f}+{slope:.5f}*(t-{t0:.2f}))"
            expr = f"if(lt(t\\,{t1:.2f})\\,{seg_expr}\\,{expr})"
        return expr

    def build_video_filtergraph(
        self,
        spec: RenderJobSpecDTO,
        input_video_label: str,
        extra_inputs: List[str],
    ) -> str:
        r_expr = self._build_focus_ratio_expr()
        crop_x_expr = f"max(0\\,min(iw-{CANVAS_WIDTH}\\,iw*({r_expr})-{CANVAS_WIDTH // 2}))"
        return (
            f"[{input_video_label}]scale=-2:{CANVAS_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT}:{crop_x_expr}:(ih-{CANVAS_HEIGHT})/2[v_framed]"
        )


class SplitRetentionLayout(BaseLayoutStrategy):
    """Layout 3: Split-screen (Top 1080x1040 movie, Bottom 1080x880 retention ASMR/gameplay)."""

    TOP_H = 1040
    BOT_H = CANVAS_HEIGHT - TOP_H  # 880

    def build_video_filtergraph(
        self,
        spec: RenderJobSpecDTO,
        input_video_label: str,
        extra_inputs: List[str],
    ) -> str:
        ret_label = extra_inputs[0] if extra_inputs else input_video_label
        return (
            f"[{input_video_label}]scale={CANVAS_WIDTH}:{self.TOP_H}:"
            f"force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{self.TOP_H}[v_top];"
            f"[{ret_label}]fps={TARGET_FPS},scale={CANVAS_WIDTH}:{self.BOT_H}:"
            f"force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{self.BOT_H}[v_bot];"
            f"[v_top][v_bot]vstack=inputs=2[v_framed]"
        )


class LayoutStrategyFactory:
    """Resolves `BaseLayoutStrategy` from `LayoutType` without modifying caller code."""

    @staticmethod
    def create(spec: RenderJobSpecDTO) -> BaseLayoutStrategy:
        ltype = spec.layout_config.layout_type
        if ltype == LayoutType.FACE_TRACK_FULL:
            if spec.source_video_path is not None:
                if getattr(spec.layout_config, "dynamic_face_tracking", True):
                    traj = FaceTrajectoryAnalyzer.estimate_smooth_trajectory(
                        spec.source_video_path,
                        spec.clip.source_start_ms,
                        spec.clip.source_end_ms,
                    )
                    fx = traj[0][1] if traj else 0.5
                    return FaceTrackFullLayout(focus_x_ratio=fx, trajectory=traj)
                fx = FaceTrajectoryAnalyzer.estimate_focus_x_ratio(
                    spec.source_video_path,
                    spec.clip.source_start_ms,
                    spec.clip.source_end_ms,
                )
                return FaceTrackFullLayout(focus_x_ratio=fx)
            return FaceTrackFullLayout(focus_x_ratio=0.5)
        if ltype == LayoutType.SPLIT_RETENTION:
            return SplitRetentionLayout()
        return BlurCenterLayout()

