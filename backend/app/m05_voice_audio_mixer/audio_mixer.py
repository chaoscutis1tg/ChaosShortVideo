"""Sample-accurate Movie Audio Ducking & 3-Tier TTS Narration Mixer (`IVoiceAudioMixer`)."""

import asyncio
from pathlib import Path
import subprocess
from typing import List, Optional
import wave
import numpy as np

from app.m00_core_contracts import (
    AudioChunkDTO,
    AudioSubConfigDTO,
    ClipSpecDTO,
    DUCKING_FADE_MS,
    IVoiceAudioMixer,
    MASTER_AUDIO_SAMPLE_RATE,
    MasterAudioAndSubDTO,
    MAX_TTS_TEMPO_STRETCH,
    MIN_TTS_TEMPO_STRETCH,
    ProgressCallback,
    VoiceProfileDTO,
    VoiceSynthesisError,
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
    ) -> MasterAudioAndSubDTO:
        """Produce synchronized MasterAudioAndSubDTO (`master_audio.wav` + `subs.ass`)."""
        clip_dir = out_dir / clip.clip_id / "audio"
        clip_dir.mkdir(parents=True, exist_ok=True)
        chunks_dir = clip_dir / "tts_lines"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        provider = self._tts_factory.get_provider(profile.tier)
        timed_events: List[TimedSubtitleEvent] = []
        placed_chunks: List[tuple[int, Path]] = []
        real_demo_windows_ms: List[tuple[int, int]] = []
        cursor_shift_ms = 0

        total_lines = max(len(clip.lines), 1)
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
                raw_wav = chunks_dir / f"line_{idx:04d}.wav"
                eff_speed = (
                    line.voice_speed_override
                    if line.voice_speed_override is not None
                    else (
                        audio_config.voice_speed_global
                        if audio_config.voice_speed_global is not None
                        else profile.speed_rate
                    )
                )
                eff_pitch = (
                    line.voice_pitch_override
                    if line.voice_pitch_override is not None
                    else (
                        audio_config.voice_pitch_global
                        if audio_config.voice_pitch_global is not None
                        else profile.pitch_hz
                    )
                )
                eff_profile = profile.model_copy(
                    update={"speed_rate": eff_speed, "pitch_hz": eff_pitch}
                )
                chunk = await provider.synthesize(line.vi_text, eff_profile, raw_wav)
                chunk = await asyncio.to_thread(self._fit_chunk_to_slot, chunk, slot_ms)
                placed_chunks.append((eff_start_ms, chunk.audio_path))
                ev_end = eff_start_ms + chunk.duration_ms
                ev_words = chunk.word_timestamps
                # If spoken product description is still slightly longer than estimated scene, shift subsequent lines cleanly
                if ev_end > next_start_ms and not audio_config.keep_original_audio:
                    cursor_shift_ms += (ev_end - next_start_ms) + 80
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

            if on_progress:
                pct = round(((idx + 1) / total_lines) * 80.0, 1)
                on_progress("GENERATING_ASSETS", pct, f"Đã thu thuyết minh câu {idx + 1}/{total_lines}")

        speech_target_ms = max(
            clip.duration_ms + cursor_shift_ms,
            max((ev.end_ms for ev in timed_events), default=1000) + 300,
        )
        outro_tail_ms = max(0, int(audio_config.outro_tail_ms))
        total_target_ms = speech_target_ms + outro_tail_ms
        master_wav = clip_dir / "master_audio.wav"
        actual_dur_ms = await asyncio.to_thread(
            self._mix_tracks_sync,
            clip=clip,
            total_target_ms=total_target_ms,
            placed_chunks=placed_chunks,
            audio_config=audio_config,
            orig_stereo_wav=orig_stereo_wav,
            master_wav=master_wav,
            real_demo_windows_ms=real_demo_windows_ms,
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
        )

        if on_progress:
            on_progress("GENERATING_ASSETS", 100.0, "Hoàn tất trộn âm Audio Ducking & phụ đề .ass")

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
            ass_subtitle_path=ass_path,
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
        real_demo_windows_ms: Optional[List[tuple[int, int]]] = None,
    ) -> int:
        total_samples = max(1, int(round((total_target_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
        mix = np.zeros((total_samples, 2), dtype=np.float32)

        # 1. Load & slice original movie audio if enabled
        if audio_config.keep_original_audio and orig_stereo_wav and orig_stereo_wav.exists():
            sliced_wav = master_wav.with_name("orig_slice.tmp.wav")
            try:
                cls._slice_wav(
                    orig_stereo_wav,
                    sliced_wav,
                    clip.source_start_ms,
                    clip.duration_ms,
                )
                bg = _read_wav_float32_stereo(sliced_wav)
                copy_len = min(total_samples, bg.shape[0])
                mix[:copy_len] = bg[:copy_len]
            finally:
                sliced_wav.unlink(missing_ok=True)

        # 2. Apply smooth 200ms envelope Audio Ducking where narrator or real demo plays
        if placed_chunks:
            envelope = np.ones(total_samples, dtype=np.float32)
            fade_samples = max(1, int((DUCKING_FADE_MS / 1000.0) * MASTER_AUDIO_SAMPLE_RATE))
            duck_lvl = float(audio_config.ducking_ratio)

            loaded_narration: List[tuple[int, np.ndarray]] = []
            for start_ms, wav_p in placed_chunks:
                s_idx = min(total_samples - 1, max(0, int((start_ms / 1000.0) * MASTER_AUDIO_SAMPLE_RATE)))
                arr = _read_wav_float32_stereo(wav_p)
                e_idx = min(total_samples, s_idx + arr.shape[0])
                loaded_narration.append((s_idx, arr[: e_idx - s_idx]))

                envelope[s_idx:e_idx] = np.minimum(envelope[s_idx:e_idx], duck_lvl)
                # Ramp down before speech
                ramp_s = max(0, s_idx - fade_samples)
                if s_idx > ramp_s:
                    ramp_down = np.linspace(1.0, duck_lvl, s_idx - ramp_s, dtype=np.float32)
                    envelope[ramp_s:s_idx] = np.minimum(envelope[ramp_s:s_idx], ramp_down)
                # Ramp up after speech
                ramp_e = min(total_samples, e_idx + fade_samples)
                if ramp_e > e_idx:
                    ramp_up = np.linspace(duck_lvl, 1.0, ramp_e - e_idx, dtype=np.float32)
                    envelope[e_idx:ramp_e] = np.minimum(envelope[e_idx:ramp_e], ramp_up)

            mix *= envelope[:, None]
            for s_idx, arr in loaded_narration:
                mix[s_idx : s_idx + arr.shape[0]] += arr * 1.08

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
    def _slice_wav(src_wav: Path, dst_wav: Path, start_ms: int, dur_ms: int) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_ms / 1000.0:.3f}",
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

