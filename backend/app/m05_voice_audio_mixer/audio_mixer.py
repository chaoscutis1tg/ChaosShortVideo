"""Sample-accurate Movie Audio Ducking & 3-Tier TTS Narration Mixer (`IVoiceAudioMixer`)."""

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import wave
import numpy as np

from app.m00_core_contracts import (
    AudioChunkDTO,
    AudioSubConfigDTO,
    ClipSpecDTO,
    DUCKING_FADE_MS,
    ITTSProvider,
    IVoiceAudioMixer,
    MASTER_AUDIO_SAMPLE_RATE,
    MasterAudioAndSubDTO,
    MAX_TTS_TEMPO_STRETCH,
    MIN_TTS_TEMPO_STRETCH,
    ProgressCallback,
    VoiceProfileDTO,
    VoiceSynthesisError,
    VoiceTier,
    WordTimestampDTO,
)

from .ass_subtitle_builder import ASSSubtitleBuilder, TimedSubtitleEvent
from .tts_providers import TTSProviderFactory


def _read_wav_float32_stereo(wav_path: Path) -> np.ndarray:
    """Read a 44.1kHz stereo 16-bit PCM WAV into shape `(N, 2)` float32 in `[-1.0, 1.0]`."""
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels == 1:
        return np.column_stack((pcm, pcm))
    return pcm.reshape(-1, n_channels)[:, :2]


def _write_wav_float32_stereo(dst_wav: Path, audio: np.ndarray) -> int:
    """Soft-limit and save `(N, 2)` float32 array as 44.1kHz stereo 16-bit PCM WAV."""
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
    if peak > 0.98:
        audio = audio * (0.96 / peak)
    pcm16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(dst_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(MASTER_AUDIO_SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    return max(1, int(round((audio.shape[0] / float(MASTER_AUDIO_SAMPLE_RATE)) * 1000.0)))


def _build_ui_pop_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a crisp 62ms Threads/iOS-style bubble pop sound effect in pure NumPy."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.062
    n_samples = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_samples, endpoint=False, dtype=np.float32)
    # Rapid pitch sweep 520Hz -> 880Hz with smooth exponential decay & 4ms attack
    freq_inst = 520.0 + (880.0 - 520.0) * (t / dur_sec) ** 0.65
    phase = 2.0 * np.pi * np.cumsum(freq_inst) / float(MASTER_AUDIO_SAMPLE_RATE)
    env = np.exp(-t * 48.0) * np.minimum(1.0, t / 0.004)
    sig = (np.sin(phase) * env * 0.19).astype(np.float32)
    stereo = np.column_stack((sig, sig))
    _write_wav_float32_stereo(dst_wav, stereo)
    return dst_wav


def _build_hook_shimmer_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a warm 360ms harmonic studio opening chime (D5+A5+D6) for 3s Hook emphasis."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.36
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    attack = np.minimum(1.0, t / 0.014)
    env = attack * np.exp(-t * 9.5)
    left = (
        0.55 * np.sin(2.0 * np.pi * 587.33 * t)
        + 0.30 * np.sin(2.0 * np.pi * 880.00 * t)
        + 0.15 * np.sin(2.0 * np.pi * 1174.66 * t)
    ) * env * 0.13
    right = (
        0.55 * np.sin(2.0 * np.pi * 588.6 * t)
        + 0.30 * np.sin(2.0 * np.pi * 881.4 * t)
        + 0.15 * np.sin(2.0 * np.pi * 1176.2 * t)
    ) * env * 0.13
    stereo = np.column_stack((left.astype(np.float32), right.astype(np.float32)))
    _write_wav_float32_stereo(dst_wav, stereo)
    return dst_wav


def _build_soft_whoosh_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a silky 240ms low-passed air transition whoosh (zero harsh treble hiss)."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.24
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    rng = np.random.default_rng(202611)
    raw_noise = rng.standard_normal(n_s + 64).astype(np.float32)
    # Multi-pass moving-average low-pass filter (~1.4kHz warm air body)
    kernel = np.hanning(33).astype(np.float32)
    kernel /= float(kernel.sum())
    warm_air = np.convolve(raw_noise, kernel, mode="same")[:n_s]
    warm_air = np.convolve(warm_air, kernel[:17] / float(kernel[:17].sum()), mode="same")
    peak = max(float(np.max(np.abs(warm_air))), 1e-4)
    warm_air /= peak

    prog = np.linspace(0.0, 1.0, n_s, endpoint=False, dtype=np.float32)
    bell_env = (np.sin(np.pi * prog) ** 1.8) * 0.115
    pan_r = 0.35 + 0.30 * prog
    pan_l = 1.0 - pan_r
    stereo = np.column_stack((warm_air * bell_env * pan_l * 1.4, warm_air * bell_env * pan_r * 1.4))
    _write_wav_float32_stereo(dst_wav, stereo.astype(np.float32))
    return dst_wav


def _build_photo_click_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a subtle 75ms soft camera leaf-shutter click for attached photos/proof cards."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.075
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    imp1 = np.sin(2.0 * np.pi * (1350.0 - 8000.0 * t) * t) * np.exp(-t * 130.0)
    t2 = np.maximum(0.0, t - 0.028)
    imp2 = np.where(t >= 0.028, np.sin(2.0 * np.pi * 920.0 * t2) * np.exp(-t2 * 150.0), 0.0)
    sig = ((imp1 * 0.65 + imp2 * 0.45) * 0.11).astype(np.float32)
    stereo = np.column_stack((sig, sig))
    _write_wav_float32_stereo(dst_wav, stereo)
    return dst_wav


def _build_chat_send_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a crisp 72ms Messenger/iMessage outgoing right-bubble swoosh-pop."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.072
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    freq = 560.0 + (1040.0 - 560.0) * (t / dur_sec) ** 0.58
    phase = 2.0 * np.pi * np.cumsum(freq) / float(MASTER_AUDIO_SAMPLE_RATE)
    env = np.minimum(1.0, t / 0.004) * np.exp(-t * 44.0)
    sig = (np.sin(phase) * env * 0.18).astype(np.float32)
    stereo = np.column_stack((sig * 0.90, sig * 1.06))
    _write_wav_float32_stereo(dst_wav, stereo)
    return dst_wav


def _build_chat_receive_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a warm 125ms 2-note incoming chat message chime (G5 -> C6)."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.125
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    note1 = np.sin(2.0 * np.pi * 783.99 * t) * np.exp(-t * 36.0) * np.minimum(1.0, t / 0.004)
    t2 = np.maximum(0.0, t - 0.042)
    note2 = np.where(
        t >= 0.042,
        np.sin(2.0 * np.pi * 1046.50 * t2) * np.exp(-t2 * 30.0) * np.minimum(1.0, t2 / 0.004),
        0.0,
    )
    sig = ((note1 * 0.52 + note2 * 0.68) * 0.16).astype(np.float32)
    stereo = np.column_stack((sig * 1.06, sig * 0.90))
    _write_wav_float32_stereo(dst_wav, stereo)
    return dst_wav


def _build_quiz_tick_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a crisp 65ms studio woodblock countdown tick for 3-2-1 Quiz timers."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.065
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    env = np.minimum(1.0, t / 0.002) * np.exp(-t * 72.0)
    sig = ((0.72 * np.sin(2.0 * np.pi * 980.0 * t) + 0.28 * np.sin(2.0 * np.pi * 1960.0 * t)) * env * 0.22).astype(
        np.float32
    )
    _write_wav_float32_stereo(dst_wav, np.column_stack((sig, sig)))
    return dst_wav


def _build_quiz_ding_sfx_wav(dst_wav: Path) -> Path:
    """Synthesize a bright 340ms C6+E6+G6 answer-reveal bell ding."""
    if dst_wav.exists() and dst_wav.stat().st_size > 200:
        return dst_wav
    dur_sec = 0.34
    n_s = int(MASTER_AUDIO_SAMPLE_RATE * dur_sec)
    t = np.linspace(0.0, dur_sec, n_s, endpoint=False, dtype=np.float32)
    env = np.minimum(1.0, t / 0.006) * np.exp(-t * 11.0)
    sig = (
        (
            0.50 * np.sin(2.0 * np.pi * 1046.50 * t)
            + 0.32 * np.sin(2.0 * np.pi * 1318.51 * t)
            + 0.18 * np.sin(2.0 * np.pi * 1567.98 * t)
        )
        * env
        * 0.19
    ).astype(np.float32)
    _write_wav_float32_stereo(dst_wav, np.column_stack((sig, sig)))
    return dst_wav


class MovieAudioAndSubMixer(IVoiceAudioMixer):
    """Synthesizes 3-tier Vietnamese narration, time-syncs lines, ducks original movie audio,
    mixes optional anti-copyright BGM, and builds `.ass` subtitles.
    """

    def __init__(self, tts_factory: Optional[TTSProviderFactory] = None) -> None:
        self._tts_factory = tts_factory or TTSProviderFactory()

    async def process(
        self,
        clip: ClipSpecDTO,
        profile: VoiceProfileDTO,
        audio_config: AudioSubConfigDTO,
        out_dir: Path,
        orig_stereo_wav: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        demo_audio_wav: Optional[Path] = None,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        voice_registry: Optional[Dict[str, VoiceProfileDTO]] = None,
    ) -> MasterAudioAndSubDTO:
        """Produce synchronized MasterAudioAndSubDTO (`master_audio.wav` + `subs.ass`)."""
        clip_dir = out_dir / clip.clip_id / "audio"
        clip_dir.mkdir(parents=True, exist_ok=True)
        chunks_dir = clip_dir / "tts_lines"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        default_provider = self._tts_factory.get_provider(profile.tier)
        is_chat_sfx = bool(getattr(audio_config, "chat_sfx_mode", False))
        is_quiz_sfx = bool(getattr(audio_config, "quiz_countdown_sfx_mode", False))
        quiz_cd_sec = max(2, min(5, int(getattr(audio_config, "quiz_countdown_sec", 3) or 3)))
        pop_sfx_wav: Optional[Path] = (
            _build_ui_pop_sfx_wav(chunks_dir / "_ui_card_pop.wav")
            if (getattr(audio_config, "enable_card_pop_sfx", False) and not is_chat_sfx and not is_quiz_sfx)
            else None
        )
        chat_send_wav: Optional[Path] = (
            _build_chat_send_sfx_wav(chunks_dir / "_sfx_chat_send.wav") if is_chat_sfx else None
        )
        chat_recv_wav: Optional[Path] = (
            _build_chat_receive_sfx_wav(chunks_dir / "_sfx_chat_recv.wav") if is_chat_sfx else None
        )
        quiz_tick_wav: Optional[Path] = (
            _build_quiz_tick_sfx_wav(chunks_dir / "_sfx_quiz_tick.wav") if is_quiz_sfx else None
        )
        quiz_ding_wav: Optional[Path] = (
            _build_quiz_ding_sfx_wav(chunks_dir / "_sfx_quiz_ding.wav") if is_quiz_sfx else None
        )
        primary_speaker = (clip.lines[0].speaker_handle or "").strip().lower() if clip.lines else ""
        use_smart_sfx = bool(getattr(audio_config, "enable_smart_sfx", True))
        sfx_gain = max(0.0, min(2.0, float(getattr(audio_config, "smart_sfx_volume", 0.22)) / 0.22))
        shimmer_wav = _build_hook_shimmer_sfx_wav(chunks_dir / "_sfx_shimmer.wav") if use_smart_sfx else None
        whoosh_wav = _build_soft_whoosh_sfx_wav(chunks_dir / "_sfx_whoosh.wav") if use_smart_sfx else None
        click_wav = _build_photo_click_sfx_wav(chunks_dir / "_sfx_click.wav") if use_smart_sfx else None

        timed_events: List[TimedSubtitleEvent] = []
        placed_chunks: List[tuple[int, Path]] = []
        pop_sfx_starts_ms: List[int] = []
        smart_sfx_cues: List[tuple[int, Path, float]] = []
        if shimmer_wav is not None:
            smart_sfx_cues.append((55, shimmer_wav, sfx_gain))
        last_whoosh_ms = -9999
        real_demo_windows_ms: List[tuple[int, int]] = []
        cursor_shift_ms = 0

        total_lines = max(len(clip.lines), 1)
        if on_progress:
            on_progress(
                "GENERATING_AUDIO",
                1.0,
                f"[Audio] Bắt đầu tổng hợp giọng đọc cho {total_lines} câu thoại...",
            )

        # Smart Content-Addressed TTS Cache + Bounded Parallel Pre-Synthesis (3x faster network TTS, 0s re-renders!)
        tts_cache_dir = out_dir.parent / "_tts_cache"
        tts_cache_dir.mkdir(parents=True, exist_ok=True)
        pre_synthesized: Dict[int, AudioChunkDTO] = {}

        if audio_config.enable_narration:
            line_jobs: List[tuple[int, str, VoiceProfileDTO, ITTSProvider, Path]] = []
            for idx, ln_item in enumerate(clip.lines):
                if ln_item.is_real_demo_slot:
                    continue
                b_prof = (
                    voice_registry[ln_item.voice_profile_override]
                    if (
                        voice_registry
                        and ln_item.voice_profile_override
                        and ln_item.voice_profile_override in voice_registry
                    )
                    else profile
                )
                l_prov = (
                    self._tts_factory.get_provider(b_prof.tier)
                    if b_prof.profile_id != profile.profile_id
                    else default_provider
                )
                e_spd = (
                    ln_item.voice_speed_override
                    if ln_item.voice_speed_override is not None
                    else (
                        audio_config.voice_speed_global
                        if audio_config.voice_speed_global is not None
                        else b_prof.speed_rate
                    )
                )
                e_pit = (
                    ln_item.voice_pitch_override
                    if ln_item.voice_pitch_override is not None
                    else (
                        audio_config.voice_pitch_global
                        if audio_config.voice_pitch_global is not None
                        else b_prof.pitch_hz
                    )
                )
                e_prof = b_prof.model_copy(update={"speed_rate": e_spd, "pitch_hz": e_pit})
                line_jobs.append(
                    (idx, ln_item.vi_text, e_prof, l_prov, chunks_dir / f"line_{idx:04d}.wav")
                )

            has_gpu_clone = any(j[2].tier == VoiceTier.LOCAL_F5_CLONE for j in line_jobs)
            tts_sem = asyncio.Semaphore(1 if has_gpu_clone else 3)
            done_counter = 0
            n_jobs = max(len(line_jobs), 1)

            async def _synth_or_load_cached(
                j_idx: int,
                j_text: str,
                j_prof: VoiceProfileDTO,
                j_prov: Any,
                j_dst: Path,
            ) -> None:
                nonlocal done_counter
                sig = (
                    f"{j_text.strip()}|{j_prof.tier.value}|{j_prof.voice_id_or_sample_path}|"
                    f"{j_prof.speed_rate:.3f}|{j_prof.pitch_hz:.2f}|{j_prof.dsp_preset}"
                )
                ckey = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:24]
                c_wav = tts_cache_dir / f"{ckey}.wav"
                c_meta = tts_cache_dir / f"{ckey}.json"

                async with tts_sem:
                    short_vname = j_prof.display_name.split("—")[0].strip()[:26]
                    preview_snip = " ".join(j_text.split())[:42]
                    if c_wav.exists() and c_meta.exists() and c_wav.stat().st_size > 256:
                        try:
                            shutil.copy2(c_wav, j_dst)
                            meta = json.loads(c_meta.read_text(encoding="utf-8"))
                            words = [WordTimestampDTO(**w) for w in (meta.get("words") or [])]
                            dur_c = max(1, int(meta.get("duration_ms") or 500))
                            pre_synthesized[j_idx] = AudioChunkDTO(
                                audio_path=j_dst, duration_ms=dur_c, word_timestamps=words
                            )
                            done_counter += 1
                            if on_progress:
                                pct_c = round((done_counter / n_jobs) * 82.0, 1)
                                on_progress(
                                    "GENERATING_AUDIO",
                                    pct_c,
                                    f'[TTS {j_idx + 1}/{total_lines}] Tái sử dụng tức thì từ Bộ đệm Cache ({dur_c / 1000.0:.1f}s): "{preview_snip}..."',
                                )
                            return
                        except Exception:
                            pass

                    if on_progress:
                        on_progress(
                            "GENERATING_AUDIO",
                            round((done_counter / n_jobs) * 82.0, 1),
                            f'[TTS {j_idx + 1}/{total_lines}] Đang thu giọng ({short_vname} • {j_prof.speed_rate:.2f}x): "{preview_snip}..."',
                        )
                    built = await j_prov.synthesize(j_text, j_prof, j_dst)
                    pre_synthesized[j_idx] = built
                    done_counter += 1
                    try:
                        shutil.copy2(j_dst, c_wav)
                        c_meta.write_text(
                            json.dumps(
                                {
                                    "duration_ms": built.duration_ms,
                                    "words": [w.model_dump() for w in built.word_timestamps],
                                },
                                ensure_ascii=False,
                            ),
                            encoding="utf-8",
                        )
                    except OSError:
                        pass
                    if on_progress:
                        pct_d = round((done_counter / n_jobs) * 82.0, 1)
                        on_progress(
                            "GENERATING_AUDIO",
                            pct_d,
                            f"[TTS {j_idx + 1}/{total_lines}] Đã thu xong câu #{j_idx + 1} ({built.duration_ms / 1000.0:.1f}s âm thanh)",
                        )

            await asyncio.gather(*[_synth_or_load_cached(*job) for job in line_jobs])

            # Keep TTS disk cache lightweight (cap at 220 recent entries)
            try:
                cached_wavs = list(tts_cache_dir.glob("*.wav"))
                if len(cached_wavs) > 220:
                    cached_wavs.sort(key=lambda p: p.stat().st_mtime)
                    for old_w in cached_wavs[:50]:
                        old_w.unlink(missing_ok=True)
                        old_w.with_suffix(".json").unlink(missing_ok=True)
            except OSError:
                pass

        for idx, line in enumerate(clip.lines):
            eff_start_ms = line.rel_start_ms + cursor_shift_ms
            orig_line_dur = max(500, line.rel_end_ms - line.rel_start_ms)

            # Real Acoustic / Product Demo Slot: Play 100% authentic demo sound without AI voiceover!
            if line.is_real_demo_slot:
                if demo_audio_wav and demo_audio_wav.exists():
                    demo_slice = chunks_dir / f"demo_slot_{idx:04d}.wav"
                    await asyncio.to_thread(
                        self._slice_wav, demo_audio_wav, demo_slice, 0, orig_line_dur
                    )
                    placed_chunks.append((eff_start_ms, demo_slice))
                ev_end = eff_start_ms + orig_line_dur
                real_demo_windows_ms.append((eff_start_ms, ev_end))
                timed_events.append(
                    TimedSubtitleEvent(
                        start_ms=eff_start_ms,
                        end_ms=ev_end,
                        text=line.vi_text,
                        words=line.words,
                    )
                )
                continue

            next_start_ms = (
                clip.lines[idx + 1].rel_start_ms + cursor_shift_ms
                if (idx + 1) < len(clip.lines)
                else max(clip.duration_ms + cursor_shift_ms, eff_start_ms + orig_line_dur)
            )
            slot_ms = max(400, next_start_ms - eff_start_ms - 40)

            if audio_config.enable_narration:
                speech_offset_ms = (
                    310
                    if (is_chat_sfx and idx >= 1)
                    else (85 if (pop_sfx_wav is not None or is_chat_sfx) else 0)
                )
                if pop_sfx_wav is not None:
                    pop_sfx_starts_ms.append(eff_start_ms)
                elif is_chat_sfx:
                    cur_spk = (line.speaker_handle or "").strip().lower()
                    is_outgoing = bool(cur_spk and cur_spk == primary_speaker) or (idx == 0)
                    chosen_chat_wav = chat_send_wav if is_outgoing else chat_recv_wav
                    if chosen_chat_wav is not None:
                        cue_t = eff_start_ms + (250 if idx >= 1 else 10)
                        smart_sfx_cues.append((cue_t, chosen_chat_wav, max(0.85, sfx_gain)))
                if use_smart_sfx:
                    if idx >= 1 and pop_sfx_wav is None and not is_chat_sfx and whoosh_wav is not None:
                        if (eff_start_ms - last_whoosh_ms) >= 2800:
                            smart_sfx_cues.append((max(0, eff_start_ms - 85), whoosh_wav, sfx_gain))
                            last_whoosh_ms = eff_start_ms
                    if click_wav is not None and bool(line.card_image_path):
                        smart_sfx_cues.append((eff_start_ms + 130, click_wav, sfx_gain))

                chunk = pre_synthesized[idx]
                chunk = await asyncio.to_thread(self._fit_chunk_to_slot, chunk, slot_ms)
                placed_chunks.append((eff_start_ms + speech_offset_ms, chunk.audio_path))
                speech_finish_ms = eff_start_ms + speech_offset_ms + chunk.duration_ms

                # Opt-in Quiz 3-2-1 Countdown Hold & Tick/Ding SFX synchronization
                spk_low = (line.speaker_handle or "").strip().lower()
                is_quiz_question = is_quiz_sfx and (
                    spk_low.startswith("@cau_do") or "câu " in (line.display_card_text or "").lower()[:14]
                ) and not line.is_op_post and not spk_low.startswith("@dap_an")
                is_quiz_answer = is_quiz_sfx and (
                    spk_low.startswith("@dap_an") or "đáp án" in (line.display_card_text or "").lower()[:24]
                )
                if is_quiz_answer and quiz_ding_wav is not None:
                    smart_sfx_cues.append((eff_start_ms + 15, quiz_ding_wav, max(0.95, sfx_gain)))

                if is_quiz_question:
                    cd_total_ms = quiz_cd_sec * 1000
                    if quiz_tick_wav is not None:
                        for sec_i in range(quiz_cd_sec):
                            smart_sfx_cues.append(
                                (speech_finish_ms + sec_i * 1000 + 80, quiz_tick_wav, max(0.95, sfx_gain))
                            )
                    ev_end = speech_finish_ms + cd_total_ms
                else:
                    ev_end = speech_finish_ms

                ev_words = chunk.word_timestamps
                if ev_end > next_start_ms and not audio_config.keep_original_audio:
                    cursor_shift_ms += (ev_end - next_start_ms) + 110
            else:
                ev_end = eff_start_ms + orig_line_dur
                ev_words = line.words

            timed_events.append(
                TimedSubtitleEvent(
                    start_ms=eff_start_ms,
                    end_ms=ev_end,
                    text=line.vi_text,
                    words=ev_words,
                )
            )

        speech_target_ms = max(
            clip.duration_ms + cursor_shift_ms,
            max((ev.end_ms for ev in timed_events), default=1000) + 300,
        )
        outro_tail_ms = max(0, int(audio_config.outro_tail_ms))
        total_target_ms = speech_target_ms + outro_tail_ms
        master_wav = clip_dir / "master_audio.wav"
        clean_voice_wav = clip_dir / "narration_clean.wav"
        if on_progress:
            on_progress(
                "GENERATING_AUDIO",
                88.0,
                f"[Audio Mix] Đang trộn {len(placed_chunks)} câu thoại, nhạc nền Lofi & hiệu ứng Micro-SFX ({total_target_ms / 1000.0:.1f}s)...",
            )
        actual_dur_ms = await asyncio.to_thread(
            self._mix_tracks_sync,
            clip=clip,
            total_target_ms=total_target_ms,
            placed_chunks=placed_chunks,
            audio_config=audio_config,
            orig_stereo_wav=orig_stereo_wav,
            master_wav=master_wav,
            clean_voice_wav=clean_voice_wav,
            real_demo_windows_ms=real_demo_windows_ms,
            pop_sfx_wav=pop_sfx_wav,
            pop_sfx_starts_ms=pop_sfx_starts_ms,
            smart_sfx_cues=smart_sfx_cues,
        )

        if on_progress and audio_config.subtitle_style.value != "NONE":
            on_progress(
                "GENERATING_AUDIO",
                95.0,
                "[Subtitle] Đang sinh phụ đề .ass đồng bộ mili-giây & tô sáng từ khóa...",
            )
        ass_path = await asyncio.to_thread(
            ASSSubtitleBuilder.build_ass_file,
            events=timed_events,
            style=audio_config.subtitle_style,
            out_ass_path=clip_dir / "subs.ass",
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            subtitle_pos_y=audio_config.subtitle_pos_y,
            subtitle_font_size=audio_config.subtitle_font_size,
            smart_keyword_highlight=bool(getattr(audio_config, "smart_keyword_highlight", True)),
        )
        srt_path = await asyncio.to_thread(
            ASSSubtitleBuilder.build_srt_file,
            events=timed_events,
            out_srt_path=clip_dir / "subs.srt",
        )

        if on_progress:
            on_progress(
                "GENERATING_AUDIO",
                100.0,
                f"[Audio Mix] Hoàn tất bản thu master_audio.wav ({actual_dur_ms / 1000.0:.1f}s • 44.1kHz Stereo)",
            )

        # Build contiguous scene spans matching exact spoken start times (excluding optional Outro tail)
        speech_end_ms = max(speech_target_ms, actual_dur_ms - outro_tail_ms)
        line_spans: List[tuple[int, int]] = []
        for i, ev in enumerate(timed_events):
            sp_start = 0 if i == 0 else ev.start_ms
            sp_end = (
                timed_events[i + 1].start_ms
                if (i + 1) < len(timed_events)
                else max(speech_end_ms, sp_start + 500)
            )
            line_spans.append((sp_start, max(sp_start + 500, sp_end)))

        return MasterAudioAndSubDTO(
            clip_id=clip.clip_id,
            master_audio_wav_path=master_wav,
            clean_narration_wav_path=clean_voice_wav if clean_voice_wav.exists() else None,
            ass_subtitle_path=ass_path,
            srt_subtitle_path=srt_path,
            total_audio_duration_ms=actual_dur_ms,
            line_spans_ms=line_spans,
        )

    @staticmethod
    def _fit_chunk_to_slot(chunk: AudioChunkDTO, slot_ms: int) -> AudioChunkDTO:
        """Apply slight FFmpeg `atempo` speedup if Vietnamese narration exceeds dialogue slot."""
        if chunk.duration_ms <= slot_ms:
            return chunk

        needed_ratio = chunk.duration_ms / float(max(slot_ms, 300))
        tempo = min(MAX_TTS_TEMPO_STRETCH, max(MIN_TTS_TEMPO_STRETCH, needed_ratio))
        if abs(tempo - 1.0) < 0.03:
            return chunk

        stretched_wav = chunk.audio_path.with_name(f"{chunk.audio_path.stem}_fit.wav")
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(chunk.audio_path),
            "-af",
            f"atempo={tempo:.3f}",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(MASTER_AUDIO_SAMPLE_RATE),
            "-ac",
            "2",
            str(stretched_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not stretched_wav.exists():
            return chunk

        with wave.open(str(stretched_wav), "rb") as wf:
            new_dur_ms = max(1, int(round(wf.getnframes() / float(wf.getframerate()) * 1000.0)))

        scaled_words = [
            WordTimestampDTO(
                word=w.word,
                start_ms=int(round(w.start_ms / tempo)),
                end_ms=max(int(round(w.start_ms / tempo)) + 10, int(round(w.end_ms / tempo))),
            )
            for w in chunk.word_timestamps
        ]
        chunk.audio_path.unlink(missing_ok=True)
        return AudioChunkDTO(
            audio_path=stretched_wav,
            duration_ms=new_dur_ms,
            word_timestamps=scaled_words,
        )

    @classmethod
    def _mix_tracks_sync(
        cls,
        clip: ClipSpecDTO,
        total_target_ms: int,
        placed_chunks: List[tuple[int, Path]],
        audio_config: AudioSubConfigDTO,
        orig_stereo_wav: Optional[Path],
        master_wav: Path,
        clean_voice_wav: Optional[Path] = None,
        real_demo_windows_ms: Optional[List[tuple[int, int]]] = None,
        pop_sfx_wav: Optional[Path] = None,
        pop_sfx_starts_ms: Optional[List[int]] = None,
        smart_sfx_cues: Optional[List[tuple[int, Path, float]]] = None,
    ) -> int:
        total_samples = max(1, int(round((total_target_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
        mix = np.zeros((total_samples, 2), dtype=np.float32)
        voice_stem = np.zeros((total_samples, 2), dtype=np.float32)

        # 1. Load & slice original movie / looped background video audio if enabled
        if audio_config.keep_original_audio and orig_stereo_wav and orig_stereo_wav.exists():
            sliced_wav = master_wav.with_name("orig_slice.tmp.wav")
            try:
                cls._slice_wav(
                    orig_stereo_wav,
                    sliced_wav,
                    clip.source_start_ms,
                    max(clip.duration_ms, total_target_ms),
                    loop_if_short=(clip.source_start_ms == 0),
                )
                bg = _read_wav_float32_stereo(sliced_wav)
                copy_len = min(total_samples, bg.shape[0])
                mix[:copy_len] = bg[:copy_len]
            finally:
                sliced_wav.unlink(missing_ok=True)

        # 2. Apply Cinema Dynamic Auto-Ducking (ducks original movie audio ONLY during active speech,
        #    smoothly swelling movie SFX & score back to 100% in natural breath pauses & silent scenes!)
        if placed_chunks:
            duck_lvl = float(audio_config.ducking_ratio)
            loaded_narration: List[tuple[int, np.ndarray]] = []
            for start_ms, wav_p in placed_chunks:
                s_idx = min(total_samples - 1, max(0, int((start_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
                arr = _read_wav_float32_stereo(wav_p)
                e_idx = min(total_samples, s_idx + arr.shape[0])
                loaded_narration.append((s_idx, arr[: e_idx - s_idx]))

            if getattr(audio_config, "dynamic_cinema_ducking", True):
                # Build 20ms frame-level voice activity curve across total_samples
                frame_len = max(1, int(0.020 * MASTER_AUDIO_SAMPLE_RATE))
                n_frames = (total_samples + frame_len - 1) // frame_len
                voice_active = np.zeros(n_frames, dtype=np.float32)

                for s_idx, arr in loaded_narration:
                    mono = 0.5 * (np.abs(arr[:, 0]) + np.abs(arr[:, 1]))
                    f_start = s_idx // frame_len
                    for k in range(0, arr.shape[0], frame_len):
                        fi = f_start + (k // frame_len)
                        if fi >= n_frames:
                            break
                        seg = mono[k : k + frame_len]
                        if seg.size > 0 and float(np.sqrt(np.mean(seg * seg))) > 0.012:
                            voice_active[fi] = 1.0

                # Bridge short micro-consonant gaps (< 260ms = 13 frames) so ducking never pumps mid-sentence
                bridged = voice_active.copy()
                bridge_frames = 13
                last_on = -999
                for fi in range(n_frames):
                    if voice_active[fi] > 0.5:
                        if 0 < (fi - last_on) <= bridge_frames:
                            bridged[last_on:fi] = 1.0
                        last_on = fi

                # Asymmetric cinema envelope follower on 20ms frames: fast 160ms attack, smooth 340ms release
                env_frames = np.ones(n_frames, dtype=np.float32)
                cur_g = 1.0
                attack_step = (1.0 - duck_lvl) / 8.0   # ~160ms smooth duck down before/at speech onset
                release_step = (1.0 - duck_lvl) / 17.0  # ~340ms cinema swell back up when narrator pauses
                # Pre-duck 3 frames (60ms) ahead of speech onset so first syllable is crystal-clear
                padded_active = bridged.copy()
                for fi in range(3, n_frames):
                    if bridged[fi] > 0.5:
                        padded_active[fi - 3 : fi] = 1.0

                for fi in range(n_frames):
                    target_g = duck_lvl if padded_active[fi] > 0.5 else 1.0
                    if target_g < cur_g:
                        cur_g = max(target_g, cur_g - attack_step)
                    else:
                        cur_g = min(target_g, cur_g + release_step)
                    env_frames[fi] = cur_g

                # Interpolate smoothly to sample accuracy
                centers = np.minimum(total_samples - 1, np.arange(n_frames) * frame_len + frame_len // 2)
                envelope = np.interp(
                    np.arange(total_samples, dtype=np.float32),
                    centers.astype(np.float32),
                    env_frames,
                ).astype(np.float32)
            else:
                envelope = np.full(total_samples, duck_lvl, dtype=np.float32)

            mix *= envelope[:, None]
            for s_idx, arr in loaded_narration:
                mix[s_idx : s_idx + arr.shape[0]] += arr * 1.08
                voice_stem[s_idx : s_idx + arr.shape[0]] += arr * 1.05
            if clean_voice_wav is not None:
                _write_wav_float32_stereo(clean_voice_wav, voice_stem)

        # 2B. Overlay crisp Threads Card Pop SFX & Smart Micro-SFX (Hook Shimmer, Soft Whoosh, Shutter)
        if pop_sfx_wav and pop_sfx_wav.exists() and pop_sfx_starts_ms:
            pop_arr = _read_wav_float32_stereo(pop_sfx_wav)
            for p_ms in pop_sfx_starts_ms:
                p_idx = min(
                    total_samples - 1, max(0, int((p_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE))
                )
                p_end = min(total_samples, p_idx + pop_arr.shape[0])
                mix[p_idx:p_end] += pop_arr[: p_end - p_idx]

        if smart_sfx_cues:
            sfx_cache: Dict[Path, np.ndarray] = {}
            for cue_ms, cue_path, cue_gain in smart_sfx_cues:
                if cue_gain <= 0.001 or not cue_path.exists():
                    continue
                if cue_path not in sfx_cache:
                    sfx_cache[cue_path] = _read_wav_float32_stereo(cue_path)
                c_arr = sfx_cache[cue_path]
                c_idx = min(
                    total_samples - 1, max(0, int((cue_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE))
                )
                c_end = min(total_samples, c_idx + c_arr.shape[0])
                mix[c_idx:c_end] += c_arr[: c_end - c_idx] * float(cue_gain)

        # 3. Mix optional BGM / subtle anti-copyright background bed
        if audio_config.bgm_path and audio_config.bgm_path.exists() and audio_config.bgm_volume > 0:
            bgm_tmp = master_wav.with_name("bgm_norm.tmp.wav")
            try:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(audio_config.bgm_path),
                    "-t",
                    f"{total_target_ms / 1000.0:.2f}",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    str(MASTER_AUDIO_SAMPLE_RATE),
                    "-ac",
                    "2",
                    str(bgm_tmp),
                ]
                proc = subprocess.run(cmd, capture_output=True, check=False)
                if proc.returncode == 0 and bgm_tmp.exists():
                    bgm_arr = _read_wav_float32_stereo(bgm_tmp)
                    c_len = min(total_samples, bgm_arr.shape[0])
                    bgm_env = np.full(c_len, float(audio_config.bgm_volume), dtype=np.float32)
                    # Mute BGM during authentic acoustic instrument demo windows
                    for ds_ms, de_ms in (real_demo_windows_ms or []):
                        s_i = max(0, min(c_len, int((ds_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
                        e_i = max(0, min(c_len, int((de_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
                        bgm_env[s_i:e_i] = 0.0

                    # Smoothly fade out BGM over the final 650ms (especially graceful on 2.5s Outro Card)
                    fade_out_n = min(c_len, int(0.65 * MASTER_AUDIO_SAMPLE_RATE))
                    if fade_out_n > 64:
                        fade_curve = 0.5 * (
                            1.0 + np.cos(np.linspace(0.0, np.pi, fade_out_n, dtype=np.float32))
                        )
                        bgm_env[-fade_out_n:] *= fade_curve

                    mix[:c_len] += bgm_arr[:c_len] * bgm_env[:, None]
            finally:
                bgm_tmp.unlink(missing_ok=True)

        return _write_wav_float32_stereo(master_wav, mix)

    @staticmethod
    def _slice_wav(
        src_wav: Path,
        dst_wav: Path,
        start_ms: int,
        dur_ms: int,
        loop_if_short: bool = False,
    ) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *(["-stream_loop", "-1"] if loop_if_short else ["-ss", f"{start_ms / 1000.0:.3f}"]),
            "-t",
            f"{dur_ms / 1000.0:.3f}",
            "-i",
            str(src_wav),
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(MASTER_AUDIO_SAMPLE_RATE),
            "-ac",
            "2",
            str(dst_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not dst_wav.exists():
            raise VoiceSynthesisError(f"Cắt âm thanh phim gốc thất bại: {proc.stderr.strip()}")

