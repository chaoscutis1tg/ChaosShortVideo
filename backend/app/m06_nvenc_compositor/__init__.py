"""Module M06 (`m06_nvenc_compositor`): 9:16 Layouts, Hardsub Mask, Anti-Copyright & NVENC."""

from .compositor import FFmpegNVENCCompositor
from .layout_strategies import (
    BlurCenterLayout,
    FaceTrackFullLayout,
    FaceTrajectoryAnalyzer,
    LayoutStrategyFactory,
    SplitRetentionLayout,
)
from .overlay_artist import StudioOverlayArtist

__all__ = [
    "FFmpegNVENCCompositor",
    "BlurCenterLayout",
    "FaceTrackFullLayout",
    "SplitRetentionLayout",
    "FaceTrajectoryAnalyzer",
    "LayoutStrategyFactory",
    "StudioOverlayArtist",
]

