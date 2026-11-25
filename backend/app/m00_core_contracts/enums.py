"""Centralized domain enumerations for ShortVideo Studio AI."""

from enum import Enum


class ProjectMode(str, Enum):
    """Supported production workflows."""

    TOPIC_VIDEO = "TOPIC_VIDEO"
    MOVIE_CLIPPER = "MOVIE_CLIPPER"
    PRODUCT_SHOWCASE = "PRODUCT_SHOWCASE"


class ProductCategory(str, Enum):
    """E-commerce product verticals optimizing script structure and pacing."""

    MUSICAL_INSTRUMENT = "MUSICAL_INSTRUMENT"
    FASHION_APPAREL = "FASHION_APPAREL"
    GENERAL_PRODUCT = "GENERAL_PRODUCT"


class SalesScriptAngle(str, Enum):
    """Conversion copywriting angles for single or multi-variant A/B product videos."""

    EXPERT_SPEC_REVIEW = "EXPERT_SPEC_REVIEW"
    BEGINNER_CONSULT = "BEGINNER_CONSULT"
    UNBOXING_AND_GIFT = "UNBOXING_AND_GIFT"
    PRICE_COMPARISON_DEAL = "PRICE_COMPARISON_DEAL"


class CopywritingTone(str, Enum):
    """Natural human voiceover styles avoiding stiff bullet-point catalog reading."""

    ARTISAN_STORYTELLER = "ARTISAN_STORYTELLER"
    MODERN_CONSULTANT = "MODERN_CONSULTANT"
    LUXURY_MINIMAL = "LUXURY_MINIMAL"


class TransitionStyle(str, Enum):
    """CapCut-inspired sub-pixel smooth transitions for product & topic showcases."""

    CAPCUT_DISSOLVE = "CAPCUT_DISSOLVE"
    CAPCUT_SMOOTH_SLIDE = "CAPCUT_SMOOTH_SLIDE"
    CAPCUT_ZOOM_FLOW = "CAPCUT_ZOOM_FLOW"
    CAPCUT_FLASH_BEAT = "CAPCUT_FLASH_BEAT"
    STATIC_LOOKBOOK = "STATIC_LOOKBOOK"


class ProductFramingStyle(str, Enum):
    """Visual card framing modes for product photography."""

    BLURRED_STUDIO_CARD = "BLURRED_STUDIO_CARD"
    VELVET_DARK_LUXURY = "VELVET_DARK_LUXURY"
    FULL_BLEED_LUXURY = "FULL_BLEED_LUXURY"


class ExportAspectRatio(str, Enum):
    """Supported social video aspect ratios (9:16 TikTok/Shorts, 4:5 FB Ads, 1:1 Zalo)."""

    RATIO_9_16 = "9:16"
    RATIO_4_5 = "4:5"
    RATIO_1_1 = "1:1"


class JobState(str, Enum):
    """Lifecycle states of a video generation/clipping job."""

    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    TRANSCRIBING_GPU = "TRANSCRIBING_GPU"
    AI_ANALYZING = "AI_ANALYZING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    GENERATING_ASSETS = "GENERATING_ASSETS"
    RENDERING_NVENC = "RENDERING_NVENC"
    PACKAGING_SEO = "PACKAGING_SEO"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SourceType(str, Enum):
    """Input source origin for long movie/video ingestion."""

    LOCAL_FILE = "LOCAL_FILE"
    VIDEO_URL = "VIDEO_URL"


class VisualMode(str, Enum):
    """Visual generation mode for Topic-to-Video workflow."""

    AI_IMAGE = "AI_IMAGE"
    STOCK_VIDEO = "STOCK_VIDEO"
    HYBRID = "HYBRID"


class CutStrategy(str, Enum):
    """Splitting strategy for long movie episodes."""

    SEQUENTIAL_PARTS = "SEQUENTIAL_PARTS"
    VIRAL_HIGHLIGHTS = "VIRAL_HIGHLIGHTS"


class VoiceTier(str, Enum):
    """Multi-tier emotional movie narration & voice synthesis architecture."""

    EDGE_TTS = "EDGE_TTS"
    LOCAL_ONNX_VITS = "LOCAL_ONNX_VITS"
    GEMINI_EMOTIONAL = "GEMINI_EMOTIONAL"
    LOCAL_F5_CLONE = "LOCAL_F5_CLONE"
    CLOUD_API = "CLOUD_API"


class LayoutType(str, Enum):
    """Vertical 9:16 framing templates."""

    BLUR_CENTER = "BLUR_CENTER"
    FACE_TRACK_FULL = "FACE_TRACK_FULL"
    SPLIT_RETENTION = "SPLIT_RETENTION"


class SubtitleStyle(str, Enum):
    """On-screen ASS subtitle presentation modes."""

    KARAOKE_CAPCUT = "KARAOKE_CAPCUT"
    CINEMA = "CINEMA"
    NONE = "NONE"


class HardsubMaskMode(str, Enum):
    """Method used to cover foreign hardcoded subtitles on source video."""

    BLUR = "BLUR"
    DARK_BOX = "DARK_BOX"


class MotionEffect(str, Enum):
    """Ken Burns camera animation presets for static AI images."""

    ZOOM_IN = "ZOOM_IN"
    ZOOM_OUT = "ZOOM_OUT"
    PAN_UP = "PAN_UP"
    PAN_DOWN = "PAN_DOWN"
    NONE = "NONE"


class AssetType(str, Enum):
    """Media type of a generated or fetched scene visual."""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"

