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
)


class FaceTrajectoryAnalyzer:
    """Lightweight OpenCV frontal-face focus estimator for `FACE_TRACK_FULL` auto-reframe."""

    @staticmethod
    def estimate_focus_x_ratio(
        video_path: Path, start_ms: int, end_ms: int, max_samples: int = 16
    ) -> float:
        """Sample frames in `[start_ms, end_ms]` and return smoothed horizontal center in `[0.15, 0.85]`."""
        if not video_path.exists():
            return 0.5
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 0.5
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)
            centers: List[float] = []
            span_ms = max(end_ms - start_ms, 500)
            step_ms = max(250, span_ms // max_samples)

            for i in range(max_samples):
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
                    # Choose largest prominent face
                    fx, _, fw, fh = max(faces, key=lambda b: b[2] * b[3])
                    cx = (fx + fw / 2.0) / float(small_w)
                    centers.append(float(np.clip(cx, 0.15, 0.85)))

            if not centers:
                return 0.5
            return round(float(np.median(centers)), 4)
        except Exception:
            return 0.5
        finally:
            cap.release()


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
    """Layout 2: Full-screen 9:16 vertical crop locked onto detected character face trajectory."""

    def __init__(self, focus_x_ratio: float = 0.5) -> None:
        self.focus_x_ratio = float(np.clip(focus_x_ratio, 0.0, 1.0))

    def build_video_filtergraph(
        self,
        spec: RenderJobSpecDTO,
        input_video_label: str,
        extra_inputs: List[str],
    ) -> str:
        r = self.focus_x_ratio
        crop_x_expr = f"max(0\\,min(iw-{CANVAS_WIDTH}\\,iw*{r:.4f}-{CANVAS_WIDTH // 2}))"
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
            f"[{ret_label}]scale={CANVAS_WIDTH}:{self.BOT_H}:"
            f"force_original_aspect_ratio=increase,crop={CANVAS_WIDTH}:{self.BOT_H}[v_bot];"
            f"[v_top][v_bot]vstack=inputs=2[v_framed]"
        )


class LayoutStrategyFactory:
    """Resolves `BaseLayoutStrategy` from `LayoutType` without modifying caller code."""

    @staticmethod
    def create(spec: RenderJobSpecDTO) -> BaseLayoutStrategy:
        ltype = spec.layout_config.layout_type
        if ltype == LayoutType.FACE_TRACK_FULL:
            fx = 0.5
            if spec.source_video_path is not None:
                fx = FaceTrajectoryAnalyzer.estimate_focus_x_ratio(
                    spec.source_video_path,
                    spec.clip.source_start_ms,
                    spec.clip.source_end_ms,
                )
            return FaceTrackFullLayout(focus_x_ratio=fx)
        if ltype == LayoutType.SPLIT_RETENTION:
            return SplitRetentionLayout()
        return BlurCenterLayout()

