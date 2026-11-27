"""Strict Pydantic v2 Data Transfer Objects (DTOs) enforcing module I/O contracts.

All durations and timestamps use integer milliseconds (`_ms`).
All file paths use `pathlib.Path`.
All frame coordinates are normalized floats in `[0.0, 1.0]`.
"""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import (
    DEFAULT_ANTI_COPY_BGM_VOL,
    DEFAULT_ANTI_COPY_SPEED,
    DEFAULT_ANTI_COPY_ZOOM,
    DEFAULT_DUCKING_RATIO,
    DEFAULT_MAX_CLIP_SEC,
    DEFAULT_MIN_CLIP_SEC,
    MAX_ALLOWED_CLIP_SEC,
    MIN_ALLOWED_CLIP_SEC,
)
from .enums import (
    AssetType,
    CopywritingTone,
    CoverTemplateStyle,
    CutStrategy,
    ExportAspectRatio,
    HardsubMaskMode,
    LayoutType,
    MotionEffect,
    ProductCategory,
    ProductFramingStyle,
    ProjectMode,
    SalesScriptAngle,
    SourceType,
    SubtitleStyle,
    TransitionStyle,
    VisualMode,
    VoiceTier,
    VoiceUseCaseCategory,
)


def resolve_aspect_dimensions(ratio: ExportAspectRatio) -> tuple[int, int]:
    """Return `(width, height)` even-pixel dimensions for the requested social aspect ratio."""
    if ratio == ExportAspectRatio.RATIO_4_5:
        return (1080, 1350)
    if ratio == ExportAspectRatio.RATIO_1_1:
        return (1080, 1080)
    return (1080, 1920)


class BaseContractDTO(BaseModel):
    """Base DTO enforcing strict attribute checks and Path serialization."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ============================================================================
# MODULE M01 CONTRACTS: Media Ingestion & URL Downloader
# ============================================================================


class IngestRequestDTO(BaseContractDTO):
    """Input contract for Module M01 (`IMediaIngestor.ingest`)."""

    project_id: str = Field(min_length=1)
    source_type: SourceType
    path_or_url: str = Field(min_length=1)
    external_srt_path: Optional[Path] = None


class MediaAssetDTO(BaseContractDTO):
    """Output contract of Module M01 -> Matches Input of M02, M05, and M06."""

    media_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    video_path: Path
    audio_16k_wav_path: Path
    original_stereo_wav_path: Optional[Path] = None
    duration_ms: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0.0)
    preview_frames: List[Path] = Field(default_factory=list)
    external_srt_path: Optional[Path] = None
    title_hint: str = ""


# ============================================================================
# MODULE M02 CONTRACTS: GPU ASR Transcription & Subtitle Parsing
# ============================================================================


class WordTimestampDTO(BaseContractDTO):
    """Word-level timing unit in milliseconds."""

    word: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_word_bounds(self) -> "WordTimestampDTO":
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be >= start_ms")
        return self


class RawTranscriptSegmentDTO(BaseContractDTO):
    """Sentence/phrase segment produced by Faster-Whisper or external SRT."""

    seq_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    raw_text: str = Field(min_length=1)
    words: List[WordTimestampDTO] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_segment_bounds(self) -> "RawTranscriptSegmentDTO":
        if self.end_ms <= self.start_ms:
            raise ValueError("segment end_ms must be > start_ms")
        return self


class TranscriptResultDTO(BaseContractDTO):
    """Output contract of Module M02 -> Matches Input of Module M03."""

    media_id: str = Field(min_length=1)
    detected_language: str = Field(min_length=2)
    segments: List[RawTranscriptSegmentDTO] = Field(default_factory=list)


# ============================================================================
# MODULE M03 CONTRACTS: AI Content Brain (Topic Script, Translation, Cut & SEO)
# ============================================================================


class TopicPromptDTO(BaseContractDTO):
    """Input contract for Mode 1 (Topic-to-Video script generation)."""

    project_id: str = Field(min_length=1)
    topic_title: str = Field(min_length=3, max_length=200)
    key_points: str = Field(default="", max_length=6000)
    visual_mode: VisualMode = VisualMode.AI_IMAGE
    target_duration_sec: int = Field(
        default=90, ge=MIN_ALLOWED_CLIP_SEC, le=MAX_ALLOWED_CLIP_SEC
    )
    part_count: int = Field(default=1, ge=1, le=20)
    narrative_tone: str = Field(default="cuốn hút, kịch tính kiểu kể chuyện Shorts/TikTok")


class BriefExpandRequestDTO(BaseContractDTO):
    """Input contract for AI short-idea analysis & detailed brief expansion (`ILLMService.expand_short_brief`)."""

    mode: ProjectMode = ProjectMode.TOPIC_VIDEO
    raw_title: str = Field(default="", max_length=250)
    short_brief: str = Field(default="", max_length=4000)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    target_duration_sec: int = Field(
        default=75, ge=MIN_ALLOWED_CLIP_SEC, le=MAX_ALLOWED_CLIP_SEC
    )
    part_count: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="after")
    def _validate_non_empty_seed(self) -> "BriefExpandRequestDTO":
        if len(self.raw_title.strip()) + len(self.short_brief.strip()) < 3:
            raise ValueError("Vui lòng nhập tiêu đề hoặc mô tả ngắn ít nhất 3 ký tự.")
        return self


class BriefExpandResultDTO(BaseContractDTO):
    """Output contract of AI brief analyzer: refined title, structured detailed outline & optimal settings."""

    refined_title: str = Field(min_length=3, max_length=200)
    alternative_titles: List[str] = Field(default_factory=list)
    hook_opening: str = ""
    expanded_description: str = Field(min_length=10, max_length=6000)
    visual_direction: str = ""
    recommended_tone: str = ""
    recommended_sales_angle: Optional[SalesScriptAngle] = None
    recommended_cta: str = ""
    recommended_duration_sec: int = Field(
        default=75, ge=MIN_ALLOWED_CLIP_SEC, le=MAX_ALLOWED_CLIP_SEC
    )
    recommended_part_count: int = Field(default=1, ge=1, le=20)
    recommended_voice_id: str = ""
    recommended_bgm_id: str = ""
    recommended_visual_mode: VisualMode = VisualMode.AI_IMAGE
    used_api_key: bool = False
    analysis_summary: str = ""


class ProductReviewPromptDTO(BaseContractDTO):
    """Input contract for Mode 3 (E-Commerce Product Showcase from real photos & demo clip)."""

    project_id: str = Field(min_length=1)
    product_name: str = Field(min_length=2, max_length=200)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    sales_angle: SalesScriptAngle = SalesScriptAngle.EXPERT_SPEC_REVIEW
    copywriting_tone: CopywritingTone = CopywritingTone.ARTISAN_STORYTELLER
    variant_count: int = Field(default=1, ge=1, le=4)
    raw_description: str = Field(default="", max_length=6000)
    image_paths: List[Path] = Field(min_length=1)
    photo_notes: List[str] = Field(default_factory=list)
    feedback_image_paths: List[Path] = Field(default_factory=list)
    comparison_enabled: bool = False
    comparison_left_label: str = Field(default="Phiên bản A", max_length=60)
    comparison_right_label: str = Field(default="Phiên bản B", max_length=60)
    demo_clip_path: Optional[Path] = None
    target_duration_sec: int = Field(
        default=55, ge=MIN_ALLOWED_CLIP_SEC, le=MAX_ALLOWED_CLIP_SEC
    )
    call_to_action: str = Field(
        default="Nhắn trực tiếp cho shop hoặc để lại bình luận để nhận video test thực tế và ưu đãi hôm nay!"
    )


class CutConfigDTO(BaseContractDTO):
    """Input configuration for Mode 2 smart episode splitting / highlight extraction."""

    cut_strategy: CutStrategy = CutStrategy.SEQUENTIAL_PARTS
    min_clip_sec: int = Field(default=DEFAULT_MIN_CLIP_SEC, ge=MIN_ALLOWED_CLIP_SEC)
    max_clip_sec: int = Field(default=DEFAULT_MAX_CLIP_SEC, le=MAX_ALLOWED_CLIP_SEC)
    max_highlights: int = Field(default=5, ge=1, le=30)
    drama_genre: str = Field(default="Phim bộ hiện đại / Tổng tài")
    series_title: str = Field(default="Tập Phim Đặc Sắc")
    append_cta_outro: bool = True

    @model_validator(mode="after")
    def _validate_window(self) -> "CutConfigDTO":
        if self.min_clip_sec >= self.max_clip_sec:
            raise ValueError("min_clip_sec must be strictly less than max_clip_sec")
        return self


class NarrationLineDTO(BaseContractDTO):
    """Unified timed narration/subtitle line shared by Topic, Movie, and Product workflows."""

    seq_index: int = Field(ge=0)
    rel_start_ms: int = Field(ge=0)
    rel_end_ms: int = Field(gt=0)
    original_text: str = ""
    vi_text: str = Field(min_length=1)
    image_prompt: str = ""
    stock_keywords: List[str] = Field(default_factory=list)
    matched_image_index: Optional[int] = Field(default=None, ge=0)
    is_real_demo_slot: bool = False
    callout_label: str = Field(default="", max_length=90)
    voice_speed_override: Optional[float] = Field(default=None, ge=0.70, le=1.50)
    voice_pitch_override: Optional[float] = Field(default=None, ge=-12.0, le=12.0)
    words: List[WordTimestampDTO] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_rel_times(self) -> "NarrationLineDTO":
        if self.rel_end_ms <= self.rel_start_ms:
            raise ValueError("rel_end_ms must be > rel_start_ms")
        return self


class ClipSpecDTO(BaseContractDTO):
    """Normalized specification of a single short video part (Part 1..N)."""

    clip_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    part_number: int = Field(ge=1)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(gt=0)
    hook_banner_title: str = Field(min_length=1)
    highlight_score: float = Field(default=80.0, ge=0.0, le=100.0)
    lines: List[NarrationLineDTO] = Field(min_length=1)
    append_cta_outro: bool = True

    @property
    def duration_ms(self) -> int:
        """Clip duration in integer milliseconds."""
        return self.source_end_ms - self.source_start_ms

    @model_validator(mode="after")
    def _validate_clip_bounds(self) -> "ClipSpecDTO":
        if self.source_end_ms <= self.source_start_ms:
            raise ValueError("source_end_ms must be > source_start_ms")
        return self


class CutPlanDTO(BaseContractDTO):
    """Output contract of Module M03 -> Unified input for M04 and M05."""

    project_id: str = Field(min_length=1)
    mode: ProjectMode
    clips: List[ClipSpecDTO] = Field(min_length=1)


class SEOPackageDTO(BaseContractDTO):
    """Output SEO metadata tailored for YouTube Shorts and TikTok 1-click copy."""

    clip_id: str = Field(min_length=1)
    part_number: int = Field(ge=1)
    yt_shorts_title: str = Field(min_length=1, max_length=100)
    yt_shorts_description: str = Field(min_length=1)
    yt_shorts_tags: List[str] = Field(default_factory=list)
    tiktok_caption: str = Field(min_length=1)
    tiktok_hashtags: List[str] = Field(default_factory=list)
    pinned_comment: str = Field(default="")


# ============================================================================
# MODULE M04 CONTRACTS: Visual Producer (AI Images & Free Stock Videos)
# ============================================================================


class SceneVisualItemDTO(BaseContractDTO):
    """Single visual asset aligned to a scene in Topic or Product Showcase mode."""

    seq_index: int = Field(ge=0)
    asset_path: Path
    asset_type: AssetType
    duration_ms: int = Field(gt=0)
    motion_effect: MotionEffect = MotionEffect.ZOOM_IN
    show_soundwave: bool = False
    soundwave_audio_path: Optional[Path] = None


class VisualAssetListDTO(BaseContractDTO):
    """Output contract of Module M04 -> Matches visual input of Module M06."""

    clip_id: str = Field(min_length=1)
    items: List[SceneVisualItemDTO] = Field(min_length=1)


# ============================================================================
# MODULE M05 CONTRACTS: 3-Tier TTS Narration, Audio Ducking & ASS Subtitles
# ============================================================================


class VoiceProfileDTO(BaseContractDTO):
    """Configuration of a selectable narrator voice with emotional prosody & studio DSP."""

    profile_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tier: VoiceTier = VoiceTier.EDGE_TTS
    category: VoiceUseCaseCategory = VoiceUseCaseCategory.MOVIE_DUB
    tags: List[str] = Field(default_factory=list)
    voice_id_or_sample_path: str = Field(default="en-US-BrianMultilingualNeural")
    sample_ref_text: str = ""
    speed_rate: float = Field(default=1.08, ge=0.7, le=1.6)
    pitch_hz: float = Field(default=-1.0, ge=-20.0, le=20.0)
    emotion_prompt: str = Field(
        default="Thuyết minh phim bộ trầm ấm, nhấn nhá kịch tính và giàu cảm xúc"
    )
    dsp_preset: str = Field(default="movie_male_deep")
    cloud_vendor: Optional[str] = None


class AudioChunkDTO(BaseContractDTO):
    """Synthesized single narration line returned by an `ITTSProvider`."""

    audio_path: Path
    duration_ms: int = Field(gt=0)
    word_timestamps: List[WordTimestampDTO] = Field(default_factory=list)


class AudioSubConfigDTO(BaseContractDTO):
    """Mixing and subtitle rendering preferences passed to Module M05."""

    enable_narration: bool = True
    keep_original_audio: bool = True
    ducking_ratio: float = Field(default=DEFAULT_DUCKING_RATIO, ge=0.0, le=1.0)
    dynamic_cinema_ducking: bool = True
    bgm_path: Optional[Path] = None
    bgm_volume: float = Field(default=DEFAULT_ANTI_COPY_BGM_VOL, ge=0.0, le=1.0)
    subtitle_style: SubtitleStyle = SubtitleStyle.CINEMA
    subtitle_pos_y: float = Field(default=0.84, ge=0.15, le=0.95)
    subtitle_font_size: int = Field(default=52, ge=28, le=88)
    voice_speed_global: Optional[float] = Field(default=None, ge=0.70, le=1.50)
    voice_pitch_global: Optional[float] = Field(default=None, ge=-12.0, le=12.0)
    outro_tail_ms: int = Field(default=0, ge=0, le=6000)


class MasterAudioAndSubDTO(BaseContractDTO):
    """Output contract of Module M05 -> Matches audio/subtitle input of Module M06."""

    clip_id: str = Field(min_length=1)
    master_audio_wav_path: Path
    ass_subtitle_path: Optional[Path] = None
    total_audio_duration_ms: int = Field(gt=0)
    line_spans_ms: List[tuple[int, int]] = Field(default_factory=list)


# ============================================================================
# MODULE M06 CONTRACTS: Vertical 9:16 Compositor, Hardsub Mask & NVENC Render
# ============================================================================


class NormalizedRectDTO(BaseContractDTO):
    """Normalized frame rectangle `[0.0 .. 1.0]` for resolution-independent masking."""

    x: float = Field(default=0.0, ge=0.0, le=1.0)
    y: float = Field(default=0.78, ge=0.0, le=1.0)
    w: float = Field(default=1.0, gt=0.0, le=1.0)
    h: float = Field(default=0.11, gt=0.0, le=1.0)
    mode: HardsubMaskMode = HardsubMaskMode.BLUR

    @model_validator(mode="after")
    def _check_normalized_sum(self) -> "NormalizedRectDTO":
        if round(self.x + self.w, 5) > 1.0 or round(self.y + self.h, 5) > 1.0:
            raise ValueError("Normalized rectangle (x+w, y+h) must not exceed 1.0")
        return self


class LayoutAndAntiCopyConfigDTO(BaseContractDTO):
    """Visual framing, transitions, overlay toggles, branding, and anti-copyright settings."""

    layout_type: LayoutType = LayoutType.BLUR_CENTER
    aspect_ratio: ExportAspectRatio = ExportAspectRatio.RATIO_9_16
    transition_style: TransitionStyle = TransitionStyle.CAPCUT_DISSOLVE
    product_framing: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD
    show_top_banner: bool = True
    show_photo_callouts: bool = False
    top_banner_template: str = "{hook_banner_title}"
    center_zoom_scale: float = Field(default=DEFAULT_ANTI_COPY_ZOOM, ge=1.0, le=1.5)
    hardsub_mask_enabled: bool = True
    hardsub_rect: NormalizedRectDTO = Field(default_factory=NormalizedRectDTO)

    anti_copyright_enabled: bool = True
    speed_factor: float = Field(default=DEFAULT_ANTI_COPY_SPEED, ge=0.90, le=1.20)
    mirror_flip: bool = False
    color_contrast: float = Field(default=1.04, ge=0.85, le=1.25)
    color_saturation: float = Field(default=1.05, ge=0.85, le=1.30)

    logo_path: Optional[Path] = None
    logo_pos_x: float = Field(default=0.04, ge=0.0, le=0.95)
    logo_pos_y: float = Field(default=0.04, ge=0.0, le=0.95)
    retention_video_path: Optional[Path] = None

    # Optional E-Commerce Sales Overlay Badges & Scannable QR Code
    sales_badge_enabled: bool = False
    sales_price_or_offer: str = Field(default="", max_length=120)
    sales_contact_info: str = Field(default="", max_length=140)
    qr_code_content: str = Field(default="", max_length=300)
    qr_code_label: str = Field(default="Quét xem mẫu", max_length=40)

    # UC-14: Studio Cutout, Acoustic Soundwave, A/B Split, Feedback Proof, Draggable Subtitles & Luxury Outro
    studio_cutout_enabled: bool = False
    soundwave_enabled: bool = True
    comparison_split_enabled: bool = False
    comparison_label_a: str = Field(default="", max_length=60)
    comparison_label_b: str = Field(default="", max_length=60)
    feedback_image_paths: List[Path] = Field(default_factory=list)
    subtitle_pos_y: float = Field(default=0.84, ge=0.15, le=0.95)
    subtitle_font_size: int = Field(default=52, ge=28, le=88)
    outro_card_enabled: bool = False
    outro_brand_title: str = Field(default="", max_length=90)
    outro_subtitle: str = Field(default="", max_length=140)
    outro_contact_line: str = Field(default="", max_length=140)
    outro_duration_ms: int = Field(default=2500, ge=1500, le=5000)

    # UC-15: Cover Thumbnail Studio (TikTok / Shorts / Reels 3-column grid optimization)
    cover_style: CoverTemplateStyle = CoverTemplateStyle.CLEAN_POSTER
    cover_headline: str = Field(default="", max_length=90)
    cover_badge_text: str = Field(default="", max_length=50)
    cover_photo_index: int = Field(default=0, ge=0, le=50)

    @field_validator("top_banner_template")
    @classmethod
    def _clean_banner(cls, val: str) -> str:
        return val.strip()


class RenderJobSpecDTO(BaseContractDTO):
    """Complete input contract of Module M06 (`IVideoCompositor.render`)."""

    clip: ClipSpecDTO
    source_video_path: Optional[Path] = None
    visual_assets: Optional[VisualAssetListDTO] = None
    audio_sub: MasterAudioAndSubDTO
    layout_config: LayoutAndAntiCopyConfigDTO = Field(
        default_factory=LayoutAndAntiCopyConfigDTO
    )
    output_dir: Path
    prefer_nvenc: bool = True

    @model_validator(mode="after")
    def _ensure_visual_source(self) -> "RenderJobSpecDTO":
        if self.source_video_path is None and self.visual_assets is None:
            raise ValueError(
                "RenderJobSpecDTO requires either source_video_path (Movie mode) "
                "or visual_assets (Topic mode)."
            )
        if self.audio_sub.clip_id != self.clip.clip_id:
            raise ValueError("audio_sub.clip_id must match clip.clip_id")
        if self.visual_assets is not None and self.visual_assets.clip_id != self.clip.clip_id:
            raise ValueError("visual_assets.clip_id must match clip.clip_id")
        return self


class RenderOutputDTO(BaseContractDTO):
    """Output contract of Module M06 -> Delivered to Module M07 & SQLite DB."""

    clip_id: str = Field(min_length=1)
    part_number: int = Field(ge=1)
    output_mp4_path: Path
    cover_jpg_path: Optional[Path] = None
    final_duration_ms: int = Field(gt=0)
    average_render_fps: float = Field(ge=0.0)
    encoder_used: str = Field(min_length=1)


# ============================================================================
# SYSTEM HARDWARE & STUDIO LIBRARY CONTRACTS
# ============================================================================


class GPUAdapterInfoDTO(BaseContractDTO):
    """Detected graphics card telemetry and capability descriptor."""

    device_id: str = Field(min_length=1)
    index: int = Field(ge=0)
    name: str = Field(min_length=1)
    vendor: str = Field(default="UNKNOWN")
    vram_total_mb: int = Field(default=0, ge=0)
    vram_used_mb: int = Field(default=0, ge=0)
    utilization_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    temperature_c: Optional[int] = None
    driver_version: str = ""
    supports_cuda: bool = False
    supports_hw_encode: bool = False
    hw_encoder_name: str = "libx264"


class BGMPresetDTO(BaseContractDTO):
    """Built-in copyright-free studio background music track."""

    preset_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    mood_category: str = Field(min_length=1)
    description: str = ""
    wav_path: Path


class ComplianceIssueDTO(BaseContractDTO):
    """Detected TikTok Shop / Advertising policy risk phrase and safe replacement."""

    phrase: str = Field(min_length=1)
    category: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class ComplianceReportDTO(BaseContractDTO):
    """Audit result returned by TikTokShopComplianceChecker."""

    safety_score: int = Field(ge=0, le=100)
    is_safe: bool
    issues: List[ComplianceIssueDTO] = Field(default_factory=list)
    sanitized_text: str = ""


class SavedProductTemplateDTO(BaseContractDTO):
    """Reusable shop catalog product preset stored in SQLite."""

    template_id: str = Field(min_length=1)
    product_name: str = Field(min_length=2, max_length=200)
    product_category: ProductCategory = ProductCategory.MUSICAL_INSTRUMENT
    raw_description: str = Field(default="", max_length=6000)
    call_to_action: str = ""
    offer_badge: str = ""
    contact_badge: str = ""
    qr_code_content: str = ""


class BrandKitDTO(BaseContractDTO):
    """Persistent store branding, subtitle positioning, and luxury end-card preset."""

    kit_id: str = Field(default="default_brand_kit", min_length=1)
    brand_name: str = Field(default="", max_length=90)
    logo_path: Optional[Path] = None
    logo_pos_x: float = Field(default=0.04, ge=0.0, le=0.95)
    logo_pos_y: float = Field(default=0.04, ge=0.0, le=0.95)
    showroom_address: str = Field(default="", max_length=140)
    hotline_or_web: str = Field(default="", max_length=140)
    qr_code_content: str = Field(default="", max_length=300)
    qr_code_label: str = Field(default="Quét xem chi tiết", max_length=40)
    subtitle_pos_y: float = Field(default=0.84, ge=0.15, le=0.95)
    subtitle_font_size: int = Field(default=52, ge=28, le=88)
    outro_card_enabled: bool = False
    preferred_framing: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD
    preferred_transition: TransitionStyle = TransitionStyle.CAPCUT_DISSOLVE
    preferred_voice_id: str = "edge_nam_nghe_nhan"
    preferred_bgm_id: Optional[str] = "bgm_luxury_acoustic"


class ScrapedProductInfoDTO(BaseContractDTO):
    """Extracted product metadata and downloaded high-resolution images from a store URL."""

    source_url: str = Field(min_length=4)
    product_name: str = ""
    raw_description: str = ""
    price_hint: str = ""
    downloaded_image_paths: List[Path] = Field(default_factory=list)


class MediaTrimResultDTO(BaseContractDTO):
    """Output contract of interactive clip/audio highlight trimmer (`UC-15`)."""

    output_path: Path
    duration_ms: int = Field(gt=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class ProjectGroupDTO(BaseContractDTO):
    """Parent project container / campaign folder managing multiple child video projects."""

    group_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)
    color_tag: str = Field(default="#0ea5e9", max_length=24)
    created_at: str = ""
    updated_at: str = ""
    project_count: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)


