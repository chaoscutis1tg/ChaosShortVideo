"""Standardized domain exceptions across all ShortVideo Studio AI modules."""


class StudioBaseError(Exception):
    """Root exception for all predictable domain and pipeline errors."""

    def __init__(self, message: str, error_code: str = "STUDIO_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class ContractValidationError(StudioBaseError):
    """Raised when module input/output data violates DTO invariants."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="CONTRACT_VALIDATION_ERROR")


class MediaIngestError(StudioBaseError):
    """Base error for Module M01 (media ingestion & downloading)."""

    def __init__(self, message: str, error_code: str = "MEDIA_INGEST_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class UnsupportedMediaFormatError(MediaIngestError):
    """Raised when an input file extension or codec is not supported."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="UNSUPPORTED_MEDIA_FORMAT")


class DownloadFailedError(MediaIngestError):
    """Raised when yt-dlp or stream fetching fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="DOWNLOAD_FAILED")


class NoAudioStreamError(MediaIngestError):
    """Raised when an ingested video contains no usable audio stream."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="NO_AUDIO_STREAM")


class TranscriptionError(StudioBaseError):
    """Raised by Module M02 when ASR or SRT parsing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="TRANSCRIPTION_ERROR")


class AIContentBrainError(StudioBaseError):
    """Raised by Module M03 during scriptwriting, translation, splitting, or SEO generation."""

    def __init__(self, message: str, error_code: str = "AI_BRAIN_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class LLMQuotaExceededError(AIContentBrainError):
    """Raised when the configured LLM provider rejects requests due to quota/rate limits."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="LLM_QUOTA_EXCEEDED")


class VisualProducerError(StudioBaseError):
    """Raised by Module M04 when both primary and fallback visual providers fail."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="VISUAL_PRODUCER_ERROR")


class VoiceSynthesisError(StudioBaseError):
    """Raised by Module M05 during TTS synthesis, voice cloning, or audio ducking."""

    def __init__(self, message: str, error_code: str = "VOICE_SYNTHESIS_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class VideoCompositorError(StudioBaseError):
    """Raised by Module M06 during FFmpeg filtergraph composition or NVENC encoding."""

    def __init__(self, message: str, error_code: str = "VIDEO_COMPOSITOR_ERROR") -> None:
        super().__init__(message, error_code=error_code)


class GPUResourceError(StudioBaseError):
    """Raised when CUDA/VRAM allocation fails or times out."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="GPU_RESOURCE_ERROR")

