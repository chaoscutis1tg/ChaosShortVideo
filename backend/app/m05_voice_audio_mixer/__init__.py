"""Module M05 (`m05_voice_audio_mixer`): Expressive Narration, Audio Ducking & ASS Subtitles."""

from .ass_subtitle_builder import ASSSubtitleBuilder, TimedSubtitleEvent
from .audio_mixer import MovieAudioAndSubMixer
from .bgm_library import StudioBGMLibrary
from .prosody_and_mastering import DramaticProsodyEnhancer, StudioVoiceMasteringDSP
from .tts_providers import (
    CloudAPITTSProvider,
    EdgeTTSProvider,
    F5VoiceCloneGPUProvider,
    GeminiEmotionalTTSProvider,
    LocalPiperVITSProvider,
    TTSProviderFactory,
)

__all__ = [
    "ASSSubtitleBuilder",
    "TimedSubtitleEvent",
    "MovieAudioAndSubMixer",
    "StudioBGMLibrary",
    "DramaticProsodyEnhancer",
    "StudioVoiceMasteringDSP",
    "EdgeTTSProvider",
    "LocalPiperVITSProvider",
    "GeminiEmotionalTTSProvider",
    "F5VoiceCloneGPUProvider",
    "CloudAPITTSProvider",
    "TTSProviderFactory",
]
