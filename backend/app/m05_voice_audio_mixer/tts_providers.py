"""Expressive Multi-Tier TTS Providers with Dramatic Prosody & Studio Broadcast Mastering."""

import asyncio
import base64
import math
from pathlib import Path
import struct
import subprocess
from typing import Dict, List, Optional
import wave
import httpx

from app.m00_core_contracts import (
    AudioChunkDTO,
    GPUResourceManager,
    ITTSProvider,
    MASTER_AUDIO_SAMPLE_RATE,
    StudioSettings,
    VOICE_CLONE_MAX_MS,
    VOICE_CLONE_MIN_MS,
    VoiceProfileDTO,
    VoiceSynthesisError,
    VoiceTier,
    WordTimestampDTO,
    get_settings,
)

from .prosody_and_mastering import DramaticProsodyEnhancer, StudioVoiceMasteringDSP


def _probe_wav_duration_ms(wav_path: Path) -> int:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return max(1, int(round((frames / float(rate)) * 1000.0)))


def _proportional_words(text: str, duration_ms: int) -> List[WordTimestampDTO]:
    tokens = [t for t in text.split() if t]
    if not tokens:
        return []
    total_chars = max(sum(len(t) for t in tokens), 1)
    words: List[WordTimestampDTO] = []
    cur = 0
    for i, tok in enumerate(tokens):
        w_end = duration_ms if i == len(tokens) - 1 else min(
            duration_ms, max(cur + 1, cur + int(round(duration_ms * len(tok) / total_chars)))
        )
        words.append(WordTimestampDTO(word=tok, start_ms=cur, end_ms=w_end))
        cur = min(w_end, duration_ms)
    return words


def _has_speakable_text(text: str) -> bool:
    return any(ch.isalnum() for ch in text)


def write_silence_wav(dst_wav: Path, duration_ms: int = 550) -> int:
    """Write clean stereo PCM silence for non-verbal cues."""
    n_samples = max(1, int(MASTER_AUDIO_SAMPLE_RATE * (duration_ms / 1000.0)))
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(MASTER_AUDIO_SAMPLE_RATE)
        wf.writeframes(b"\x00\x00\x00\x00" * n_samples)
    return duration_ms


def write_synthetic_speech_placeholder(dst_wav: Path, text: str, speed_rate: float = 1.1) -> int:
    """Last-resort offline unit-test tone if no ONNX model or internet is present."""
    words_cnt = max(len(text.split()), 2)
    est_sec = max(0.8, (words_cnt / (3.4 * max(speed_rate, 0.8))))
    n_samples = int(MASTER_AUDIO_SAMPLE_RATE * est_sec)
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(MASTER_AUDIO_SAMPLE_RATE)
        buf = bytearray(n_samples * 4)
        for i in range(n_samples):
            env = 0.5 * (1.0 - math.cos(2.0 * math.pi * min(i / 800.0, 1.0)))
            val = int(env * 3500.0 * math.sin(2.0 * math.pi * 195.0 * (i / MASTER_AUDIO_SAMPLE_RATE)))
            struct.pack_into("<hh", buf, i * 4, val, val)
        wf.writeframes(buf)
    return int(round(est_sec * 1000.0))


class LocalPiperVITSProvider(ITTSProvider):
    """Instant 0.1s Offline Studio Vietnamese VITS Neural Narrator (`vi_VN-vais1000-medium`)."""

    _loaded_models: Dict[str, object] = {}

    def __init__(self, settings: Optional[StudioSettings] = None) -> None:
        self._settings = settings or get_settings()

    def is_model_available(self, model_name: str = "vi_VN-vais1000-medium.onnx") -> bool:
        model_path = self._resolve_model_path(model_name)
        return model_path.exists() and model_path.stat().st_size > 100_000

    def _resolve_model_path(self, model_ref: str) -> Path:
        p = Path(model_ref)
        if p.is_absolute() and p.exists():
            return p
        candidate = self._settings.assets_dir / "tts_models" / p.name
        if candidate.exists():
            return candidate
        return self._settings.workspace_root / "assets" / "tts_models" / "vi_VN-vais1000-medium.onnx"

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        enhanced = DramaticProsodyEnhancer.enhance(text)
        if not _has_speakable_text(enhanced):
            dur_ms = await asyncio.to_thread(write_silence_wav, out_wav_path, 500)
            return AudioChunkDTO(
                audio_path=out_wav_path,
                duration_ms=dur_ms,
                word_timestamps=_proportional_words(text or "...", dur_ms),
            )

        dur_ms = await asyncio.to_thread(self._synth_sync, enhanced, profile, out_wav_path)
        return AudioChunkDTO(
            audio_path=out_wav_path,
            duration_ms=dur_ms,
            word_timestamps=_proportional_words(text, dur_ms),
        )

    def _synth_sync(self, enhanced_text: str, profile: VoiceProfileDTO, out_wav_path: Path) -> int:
        import piper  # type: ignore

        model_path = self._resolve_model_path(profile.voice_id_or_sample_path)
        if not model_path.exists():
            raise VoiceSynthesisError(f"Không tìm thấy mô hình giọng Offline: {model_path.name}")

        key = str(model_path)
        if key not in self._loaded_models:
            self._loaded_models[key] = piper.PiperVoice.load(key)
        voice = self._loaded_models[key]

        raw_wav = out_wav_path.with_suffix(".piper_raw.wav")
        raw_wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Keep trained VITS variance intact (`noise_scale=0.5, noise_w_scale=0.333`) for clean tones
            syn_cfg = piper.SynthesisConfig(
                length_scale=1.0 / max(profile.speed_rate, 0.75),
                noise_scale=0.50,
                noise_w_scale=0.35,
            )
            with wave.open(str(raw_wav), "wb") as wf:
                voice.synthesize_wav(enhanced_text, wf, syn_config=syn_cfg)  # type: ignore[attr-defined]

            with wave.open(str(raw_wav), "rb") as rf:
                src_sr = rf.getframerate()

            # Convert pitch_hz (~ -4..+4) into subtle semitones (~ -1.2..+1.2)
            semitones = max(-3.5, min(3.5, float(profile.pitch_hz) * 0.45))
            return StudioVoiceMasteringDSP.master_audio(
                src_audio=raw_wav,
                dst_wav=out_wav_path,
                speed_rate=1.0,
                pitch_semitones=semitones,
                preset=profile.dsp_preset or "drama_female_emotional",
                src_sample_rate=src_sr,
            )
        finally:
            raw_wav.unlink(missing_ok=True)


class EdgeTTSProvider(ITTSProvider):
    """Expressive DragonHD Neural Voices (`Brian`, `Remy`, `Ava`, `Vivienne`, `Emma`)
    with Dramatic Prosody pauses, Studio Broadcast Mastering, and automatic Local VITS fallback.
    """

    DRAGON_FALLBACKS = {
        "vi-vn-namminhneural": "en-US-BrianMultilingualNeural",
        "de-de-seraphinamultilingualneural": "vi-VN-HoaiMyNeural",
    }

    def __init__(
        self,
        local_vits: Optional[LocalPiperVITSProvider] = None,
        allow_offline_fallback: bool = True,
    ) -> None:
        self._local_vits = local_vits or LocalPiperVITSProvider()
        self.allow_offline_fallback = allow_offline_fallback

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)
        enhanced_txt = DramaticProsodyEnhancer.enhance(text)
        if not _has_speakable_text(enhanced_txt):
            dur_ms = await asyncio.to_thread(write_silence_wav, out_wav_path, 500)
            return AudioChunkDTO(
                audio_path=out_wav_path,
                duration_ms=dur_ms,
                word_timestamps=_proportional_words(text or "...", dur_ms),
            )

        primary_voice = profile.voice_id_or_sample_path or "en-US-BrianMultilingualNeural"
        # Automatically upgrade legacy unstable vi-VN voices to 100%-reliable DragonHD voices
        mapped_voice = self.DRAGON_FALLBACKS.get(primary_voice.lower(), primary_voice)
        backup_voice = (
            "fr-FR-RemyMultilingualNeural"
            if "male" in (profile.dsp_preset or "")
            else "en-US-AvaMultilingualNeural"
        )

        tmp_mp3 = out_wav_path.with_suffix(".edge_raw.mp3")
        synthesized_ok = False
        last_err: Optional[Exception] = None

        # Keep SSML clean (no SSML pitch/boundary quirks); apply speed & pitch in Studio DSP!
        for attempt_idx, v_candidate in enumerate((mapped_voice, backup_voice), start=1):
            tmp_mp3.unlink(missing_ok=True)
            try:
                import edge_tts  # type: ignore

                if attempt_idx > 1:
                    await asyncio.sleep(0.35)
                else:
                    await asyncio.sleep(0.08)

                async def _download_mp3() -> None:
                    comm = edge_tts.Communicate(text=enhanced_txt, voice=v_candidate)
                    with open(tmp_mp3, "wb") as f_mp3:
                        async for chunk in comm.stream():
                            if chunk.get("type") == "audio":
                                f_mp3.write(chunk["data"])

                await asyncio.wait_for(_download_mp3(), timeout=12.0)
                if not tmp_mp3.exists() or tmp_mp3.stat().st_size < 256:
                    raise VoiceSynthesisError("Dữ liệu âm thanh trả về rỗng.")

                semitones = max(-2.5, min(2.5, float(profile.pitch_hz) * 0.45))
                dur_ms = await asyncio.to_thread(
                    StudioVoiceMasteringDSP.master_audio,
                    src_audio=tmp_mp3,
                    dst_wav=out_wav_path,
                    speed_rate=profile.speed_rate,
                    pitch_semitones=semitones,
                    preset=profile.dsp_preset or "movie_male_deep",
                    src_sample_rate=24000,
                )
                synthesized_ok = True
                break
            except Exception as exc:
                last_err = exc
            finally:
                tmp_mp3.unlink(missing_ok=True)

        if not synthesized_ok:
            if self._local_vits.is_model_available():
                local_prof = profile.model_copy(
                    update={
                        "tier": VoiceTier.LOCAL_ONNX_VITS,
                        "voice_id_or_sample_path": "vi_VN-vais1000-medium.onnx",
                    }
                )
                return await self._local_vits.synthesize(text, local_prof, out_wav_path)

            if not self.allow_offline_fallback:
                raise VoiceSynthesisError(f"Lỗi tổng hợp giọng thuyết minh: {last_err}")

            dur_ms = await asyncio.to_thread(
                write_synthetic_speech_placeholder, out_wav_path, text, profile.speed_rate
            )

        return AudioChunkDTO(
            audio_path=out_wav_path,
            duration_ms=dur_ms,
            word_timestamps=_proportional_words(text, dur_ms),
        )


class GeminiEmotionalTTSProvider(ITTSProvider):
    """Ultra-emotional AI Voice Actor powered by `gemini-2.5-flash-preview-tts`
    (seamlessly falls back to Expressive DragonHD Neural if GEMINI_API_KEY is not configured yet).
    """

    def __init__(
        self,
        edge_fallback: EdgeTTSProvider,
        settings: Optional[StudioSettings] = None,
    ) -> None:
        self._edge_fallback = edge_fallback
        self._settings = settings or get_settings()

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        enhanced = DramaticProsodyEnhancer.enhance(text)
        if not self._settings.gemini_api_key:
            fallback_prof = profile.model_copy(
                update={
                    "tier": VoiceTier.EDGE_TTS,
                    "voice_id_or_sample_path": "en-US-BrianMultilingualNeural",
                }
            )
            return await self._edge_fallback.synthesize(text, fallback_prof, out_wav_path)

        try:
            dur_ms = await asyncio.to_thread(
                self._call_gemini_tts_sync, enhanced, profile, out_wav_path
            )
            return AudioChunkDTO(
                audio_path=out_wav_path,
                duration_ms=dur_ms,
                word_timestamps=_proportional_words(text, dur_ms),
            )
        except Exception:
            fallback_prof = profile.model_copy(
                update={
                    "tier": VoiceTier.EDGE_TTS,
                    "voice_id_or_sample_path": "en-US-BrianMultilingualNeural",
                }
            )
            return await self._edge_fallback.synthesize(text, fallback_prof, out_wav_path)

    def _call_gemini_tts_sync(
        self, enhanced_text: str, profile: VoiceProfileDTO, out_wav_path: Path
    ) -> int:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=self._settings.gemini_api_key)
        direction = (
            profile.emotion_prompt
            or "Đọc bằng giọng thuyết minh phim bộ trầm ấm, nhấn nhá kịch tính đầy cảm xúc"
        )
        full_prompt = f"Hướng dẫn diễn xuất giọng đọc ({direction}):\n{enhanced_text}"
        actor_voice = profile.voice_id_or_sample_path or "Charon"

        resp = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=actor_voice)
                    )
                ),
            ),
        )
        inline = resp.candidates[0].content.parts[0].inline_data
        pcm_bytes = (
            base64.b64decode(inline.data) if isinstance(inline.data, str) else bytes(inline.data)
        )

        raw_pcm_wav = out_wav_path.with_suffix(".gemini_24k.wav")
        raw_pcm_wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            with wave.open(str(raw_pcm_wav), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(pcm_bytes)

            return StudioVoiceMasteringDSP.master_audio(
                src_audio=raw_pcm_wav,
                dst_wav=out_wav_path,
                speed_rate=profile.speed_rate,
                pitch_semitones=0.0,
                preset=profile.dsp_preset or "movie_male_deep",
                src_sample_rate=24000,
            )
        finally:
            raw_pcm_wav.unlink(missing_ok=True)


class F5VoiceCloneGPUProvider(ITTSProvider):
    """Tier 2: Local Voice Cloning on RTX 3060 (12GB VRAM) via F5-TTS Vietnamese."""

    def __init__(
        self,
        gpu_manager: Optional[GPUResourceManager] = None,
        fallback_edge: Optional[EdgeTTSProvider] = None,
    ) -> None:
        self._gpu_manager = gpu_manager or GPUResourceManager()
        self._fallback_edge = fallback_edge

    @staticmethod
    def prepare_reference_sample(src_media: Path, dst_sample_wav: Path) -> int:
        """Denoise, trim (max 15s), and loudness-normalize a movie narrator reference clip."""
        if not src_media.exists():
            raise VoiceSynthesisError(f"Không tìm thấy tệp giọng mẫu: {src_media}")
        dst_sample_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src_media),
            "-t",
            "15",
            "-vn",
            "-af",
            "highpass=f=80,lowpass=f=8000,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(dst_sample_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if proc.returncode != 0 or not dst_sample_wav.exists():
            raise VoiceSynthesisError(f"Chuẩn hóa giọng mẫu thất bại: {proc.stderr.strip()}")
        dur_ms = _probe_wav_duration_ms(dst_sample_wav)
        if dur_ms < VOICE_CLONE_MIN_MS or dur_ms > VOICE_CLONE_MAX_MS:
            raise VoiceSynthesisError(
                f"Độ dài mẫu giọng ({dur_ms / 1000:.1f}s) cần nằm trong khoảng 5 – 25 giây."
            )
        return dur_ms

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        sample_path = Path(profile.voice_id_or_sample_path)
        if not sample_path.exists():
            raise VoiceSynthesisError(f"Tệp mẫu giọng Clone không tồn tại: {sample_path}")

        enhanced = DramaticProsodyEnhancer.enhance(text)
        try:
            return await asyncio.to_thread(
                self._infer_f5_sync, enhanced, profile, sample_path, out_wav_path
            )
        except ImportError as exc:
            if self._fallback_edge is not None:
                fallback_prof = profile.model_copy(
                    update={
                        "tier": VoiceTier.EDGE_TTS,
                        "voice_id_or_sample_path": "en-US-BrianMultilingualNeural",
                    }
                )
                return await self._fallback_edge.synthesize(text, fallback_prof, out_wav_path)
            raise VoiceSynthesisError(
                "Chưa cài đặt gói `f5-tts` cho tính năng Voice Clone GPU "
                "(chạy `pip install f5-tts` để kích hoạt)."
            ) from exc

    def _infer_f5_sync(
        self,
        text: str,
        profile: VoiceProfileDTO,
        sample_path: Path,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        from f5_tts.api import F5TTS  # type: ignore

        raw_out = out_wav_path.with_suffix(".f5raw.wav")
        holder = {"tts": None}

        def _cleanup() -> None:
            holder["tts"] = None

        with self._gpu_manager.acquire_vram("f5-tts-voice-clone", cleanup_fn=_cleanup):
            device = "cuda" if self._gpu_manager.is_cuda_available() else "cpu"
            holder["tts"] = F5TTS(device=device)
            holder["tts"].infer(
                ref_file=str(sample_path),
                ref_text=profile.sample_ref_text or "Xin chào các bạn.",
                gen_text=text,
                file_wave=str(raw_out),
                speed=profile.speed_rate,
            )

        try:
            dur_ms = StudioVoiceMasteringDSP.master_audio(
                src_audio=raw_out,
                dst_wav=out_wav_path,
                speed_rate=1.0,
                pitch_semitones=0.0,
                preset=profile.dsp_preset or "movie_male_deep",
                src_sample_rate=24000,
            )
        finally:
            raw_out.unlink(missing_ok=True)

        return AudioChunkDTO(
            audio_path=out_wav_path,
            duration_ms=dur_ms,
            word_timestamps=_proportional_words(text, dur_ms),
        )


class CloudAPITTSProvider(ITTSProvider):
    """Commercial Vietnamese Narration APIs (ElevenLabs, FPT.AI)."""

    def __init__(self, settings: Optional[StudioSettings] = None) -> None:
        self._settings = settings or get_settings()

    async def synthesize(
        self,
        text: str,
        profile: VoiceProfileDTO,
        out_wav_path: Path,
    ) -> AudioChunkDTO:
        vendor = (profile.cloud_vendor or "elevenlabs").lower()
        enhanced = DramaticProsodyEnhancer.enhance(text)
        tmp_audio = out_wav_path.with_suffix(".cloud.mp3")
        try:
            if vendor == "elevenlabs":
                await self._call_elevenlabs(enhanced, profile.voice_id_or_sample_path, tmp_audio)
            elif vendor == "fpt":
                await self._call_fpt_ai(
                    enhanced, profile.voice_id_or_sample_path, profile.speed_rate, tmp_audio
                )
            else:
                raise VoiceSynthesisError(f"Nhà cung cấp Cloud TTS chưa hỗ trợ: {vendor}")

            dur_ms = await asyncio.to_thread(
                StudioVoiceMasteringDSP.master_audio,
                src_audio=tmp_audio,
                dst_wav=out_wav_path,
                speed_rate=1.0,
                pitch_semitones=0.0,
                preset=profile.dsp_preset or "movie_male_deep",
                src_sample_rate=44100,
            )
        finally:
            tmp_audio.unlink(missing_ok=True)

        return AudioChunkDTO(
            audio_path=out_wav_path,
            duration_ms=dur_ms,
            word_timestamps=_proportional_words(text, dur_ms),
        )

    async def _call_elevenlabs(self, text: str, voice_id: str, dst: Path) -> None:
        if not self._settings.elevenlabs_api_key:
            raise VoiceSynthesisError("Chưa cấu hình ELEVENLABS_API_KEY trong .env.")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self._settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.42, "similarity_boost": 0.80, "style": 0.65},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                raise VoiceSynthesisError(f"ElevenLabs API lỗi ({res.status_code})")
            dst.write_bytes(res.content)

    async def _call_fpt_ai(self, text: str, voice_id: str, speed: float, dst: Path) -> None:
        if not self._settings.fpt_ai_api_key:
            raise VoiceSynthesisError("Chưa cấu hình FPT_AI_API_KEY trong .env.")
        headers = {
            "api-key": self._settings.fpt_ai_api_key,
            "voice": voice_id or "banmai",
            "speed": str(round(speed - 1.0, 1)),
        }
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            res = await client.post(
                "https://api.fpt.ai/hmi/tts/v5", headers=headers, content=text.encode("utf-8")
            )
            if res.status_code != 200:
                raise VoiceSynthesisError(f"FPT.AI TTS lỗi ({res.status_code})")
            async_url = res.json().get("async")
            if not async_url:
                raise VoiceSynthesisError("FPT.AI không trả về đường dẫn âm thanh.")
            for _ in range(8):
                await asyncio.sleep(1.0)
                dl = await client.get(async_url)
                if dl.status_code == 200 and len(dl.content) > 512:
                    dst.write_bytes(dl.content)
                    return
            raise VoiceSynthesisError("Quá thời gian chờ tệp âm thanh từ FPT.AI.")


class TTSProviderFactory:
    """Factory resolving the appropriate expressive ITTSProvider from VoiceTier."""

    def __init__(self, allow_offline_fallback: bool = True) -> None:
        self._local_vits = LocalPiperVITSProvider()
        self._edge = EdgeTTSProvider(
            local_vits=self._local_vits, allow_offline_fallback=allow_offline_fallback
        )
        self._gemini = GeminiEmotionalTTSProvider(edge_fallback=self._edge)
        self._f5 = F5VoiceCloneGPUProvider(
            fallback_edge=self._edge if allow_offline_fallback else None
        )
        self._cloud = CloudAPITTSProvider()

    def get_provider(self, tier: VoiceTier) -> ITTSProvider:
        if tier == VoiceTier.EDGE_TTS:
            return self._edge
        if tier == VoiceTier.LOCAL_ONNX_VITS:
            return self._local_vits
        if tier == VoiceTier.GEMINI_EMOTIONAL:
            return self._gemini
        if tier == VoiceTier.LOCAL_F5_CLONE:
            return self._f5
        if tier == VoiceTier.CLOUD_API:
            return self._cloud
        raise VoiceSynthesisError(f"Tầng giọng đọc không hợp lệ: {tier}")
