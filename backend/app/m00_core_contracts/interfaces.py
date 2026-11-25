"""Abstract Base Classes (SOLID Interfaces) decoupling modules M01 through M06."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional

from .dtos import (
    AudioChunkDTO,
    AudioSubConfigDTO,
    ClipSpecDTO,
    CutConfigDTO,
    CutPlanDTO,
    IngestRequestDTO,
    MasterAudioAndSubDTO,
    MediaAssetDTO,
    NarrationLineDTO,
    ProductReviewPromptDTO,
    RenderJobSpecDTO,
    RenderOutputDTO,
    SceneVisualItemDTO,
    SEOPackageDTO,
    TopicPromptDTO,
    TranscriptResultDTO,
    VisualAssetListDTO,
    VoiceProfileDTO,
)
from .enums import ExportAspectRatio, ProductFramingStyle, VisualMode

# Callback signature: (stage_name, progress_percent_0_to_100, status_message)
ProgressCallback = Callable[[str, float, str], None]


class IMediaIngestor(ABC):
    """Interface for Module M01: Local video validation, yt-dlp downloading & WAV extraction."""

    @abstractmethod
    async def ingest(
        self,
        req: IngestRequestDTO,
        work_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> MediaAssetDTO:
        """Ingest local file or remote URL and return standardized MediaAssetDTO."""


class ITranscriber(ABC):
    """Interface for Module M02: GPU speech-to-text (Faster-Whisper) and SRT parsing."""

    @abstractmethod
    async def transcribe(
        self,
        media: MediaAssetDTO,
        lang_hint: str = "auto",
        on_progress: Optional[ProgressCallback] = None,
    ) -> TranscriptResultDTO:
        """Extract word/sentence-timed transcript from MediaAssetDTO."""


class ILLMService(ABC):
    """Interface for Module M03: Scriptwriting, context-aware drama translation, cutting & SEO."""

    @abstractmethod
    async def build_topic_clips(self, req: TopicPromptDTO) -> CutPlanDTO:
        """Generate structured multi-scene vertical video script from topic & notes."""

    @abstractmethod
    async def build_product_review_clips(
        self, req: ProductReviewPromptDTO, demo_duration_ms: int = 0
    ) -> CutPlanDTO:
        """Analyze product photos & specs to build high-converting sales CutPlanDTO."""

    @abstractmethod
    async def translate_and_split_movie(
        self,
        transcript: TranscriptResultDTO,
        config: CutConfigDTO,
        project_id: str,
        total_duration_ms: int,
    ) -> CutPlanDTO:
        """Translate foreign dialogue in drama context and split into 65-120s parts/highlights."""

    @abstractmethod
    async def build_seo(self, clip: ClipSpecDTO, mode_label: str = "") -> SEOPackageDTO:
        """Generate YouTube Shorts & TikTok titles, descriptions, and hashtags."""


class IVisualProvider(ABC):
    """Strategy interface for pluggable visual sources inside Module M04."""

    @abstractmethod
    async def fetch_scene_visual(
        self,
        line: NarrationLineDTO,
        target_duration_ms: int,
        out_dir: Path,
    ) -> SceneVisualItemDTO:
        """Create or download a single scene visual matching target_duration_ms."""


class IVisualProducer(ABC):
    """Facade interface for Module M04: Scene visual assembly for Topic & Product Showcase."""

    @abstractmethod
    async def produce(
        self,
        clip: ClipSpecDTO,
        visual_mode: VisualMode,
        out_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> VisualAssetListDTO:
        """Produce VisualAssetListDTO covering all lines in ClipSpecDTO."""

    @abstractmethod
    async def produce_product_showcase(
        self,
        clip: ClipSpecDTO,
        image_paths: List[Path],
        out_dir: Path,
        demo_clip_path: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        framing_style: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD,
        aspect_ratio: ExportAspectRatio = ExportAspectRatio.RATIO_9_16,
        show_photo_callouts: bool = False,
        studio_cutout_enabled: bool = False,
        comparison_split_enabled: bool = False,
        comparison_label_a: str = "",
        comparison_label_b: str = "",
        feedback_image_paths: Optional[List[Path]] = None,
        demo_audio_wav: Optional[Path] = None,
        soundwave_enabled: bool = True,
    ) -> VisualAssetListDTO:
        """Produce uncropped product photo/video plates, optional cutout, A/B split, feedback & soundwave."""


class ITTSProvider(ABC):
    """Strategy interface for 3-tier TTS synthesis (Edge-TTS, Local F5 Clone, Cloud API)."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        """Synthesize Vietnamese speech into out_wav_path and return AudioChunkDTO."""


class IVoiceAudioMixer(ABC):
    """Facade interface for Module M05: TTS synthesis, Audio Ducking & ASS subtitles."""

    @abstractmethod
    async def process(
        self,
        clip: ClipSpecDTO,
        profile: VoiceProfileDTO,
        audio_config: AudioSubConfigDTO,
        out_dir: Path,
        orig_stereo_wav: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        demo_audio_wav: Optional[Path] = None,
    ) -> MasterAudioAndSubDTO:
        """Synthesize narration, duck original movie audio, and generate .ass subtitles."""


class BaseLayoutStrategy(ABC):
    """Strategy base class for 9:16 vertical FFmpeg filtergraph layouts in Module M06."""

    @abstractmethod
    def build_video_filtergraph(
        self,
        spec: RenderJobSpecDTO,
        input_video_label: str,
        extra_inputs: List[str],
    ) -> str:
        """Construct the FFmpeg complex filtergraph string producing `[v_framed]` (1080x1920)."""


class IVideoCompositor(ABC):
    """Facade interface for Module M06: 9:16 framing, Hardsub mask, Anti-Copyright & NVENC."""

    @abstractmethod
    async def render(
        self,
        spec: RenderJobSpecDTO,
        on_progress: Optional[ProgressCallback] = None,
    ) -> RenderOutputDTO:
        """Render final 1080x1920 MP4 using h264_nvenc (with automatic CPU x264 fallback)."""

