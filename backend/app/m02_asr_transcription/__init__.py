"""Module M02 (`m02_asr_transcription`): GPU Faster-Whisper ASR & SRT parser."""

from .srt_parser import SRTSubtitleParser, detect_text_language, interpolate_words
from .whisper_transcriber import FasterWhisperTranscriber

__all__ = [
    "FasterWhisperTranscriber",
    "SRTSubtitleParser",
    "detect_text_language",
    "interpolate_words",
]

