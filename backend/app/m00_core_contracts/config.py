"""Centralized configuration and domain constants (Zero Magic Numbers)."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(WORKSPACE_ROOT / ".env")

# Domain Constants (Shared across M01..M07)
CANVAS_WIDTH: int = 1080
CANVAS_HEIGHT: int = 1920
TARGET_FPS: int = 30

DEFAULT_MIN_CLIP_SEC: int = 65
DEFAULT_MAX_CLIP_SEC: int = 120
MIN_ALLOWED_CLIP_SEC: int = 15
MAX_ALLOWED_CLIP_SEC: int = 180
SILENCE_GAP_SNAP_MS: int = 400
MAX_NARRATION_CPS: float = 22.0

WHISPER_SAMPLE_RATE: int = 16000
MASTER_AUDIO_SAMPLE_RATE: int = 44100
DEFAULT_DUCKING_RATIO: float = 0.18
DUCKING_FADE_MS: int = 200
DEFAULT_ANTI_COPY_BGM_VOL: float = 0.06
MIN_TTS_TEMPO_STRETCH: float = 0.92
MAX_TTS_TEMPO_STRETCH: float = 1.28
VOICE_CLONE_MIN_MS: int = 5000
VOICE_CLONE_MAX_MS: int = 25000

DEFAULT_ANTI_COPY_SPEED: float = 1.05
DEFAULT_ANTI_COPY_ZOOM: float = 1.04
NVENC_PRESET: str = "p4"
NVENC_CQ: int = 21

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts"}
SUPPORTED_SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass"}


@dataclass
class StudioSettings:
    """Runtime settings resolved from environment variables and workspace layout."""

    workspace_root: Path = field(default_factory=lambda: WORKSPACE_ROOT)
    assets_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "assets")
    work_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "work_temp")
    outputs_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "outputs")
    sqlite_db_path: Path = field(default_factory=lambda: WORKSPACE_ROOT / "work_temp" / "studio.db")

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip())
    pexels_api_key: str = field(default_factory=lambda: os.getenv("PEXELS_API_KEY", "").strip())
    pixabay_api_key: str = field(default_factory=lambda: os.getenv("PIXABAY_API_KEY", "").strip())
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", "").strip())
    vbee_api_key: str = field(default_factory=lambda: os.getenv("VBEE_API_KEY", "").strip())
    vbee_app_id: str = field(default_factory=lambda: os.getenv("VBEE_APP_ID", "").strip())
    fpt_ai_api_key: str = field(default_factory=lambda: os.getenv("FPT_AI_API_KEY", "").strip())

    prefer_nvenc_gpu: bool = field(
        default_factory=lambda: os.getenv("PREFER_NVENC_GPU", "true").lower() in ("1", "true", "yes")
    )
    whisper_model_size: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL_SIZE", "medium").strip())
    whisper_compute_type: str = field(default_factory=lambda: os.getenv("WHISPER_COMPUTE_TYPE", "float16").strip())

    def ensure_directories(self) -> None:
        """Create all required runtime and asset folders if they do not exist."""
        for folder in (
            self.assets_dir / "fonts",
            self.assets_dir / "bgm",
            self.assets_dir / "retention_videos",
            self.assets_dir / "voice_samples",
            self.assets_dir / "logos",
            self.work_dir,
            self.outputs_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)


def get_settings() -> StudioSettings:
    """Return initialized StudioSettings with directories guaranteed."""
    settings = StudioSettings()
    settings.ensure_directories()
    return settings

