"""Expressive Acoustic Violin, Nylon Guitar & Felt Piano Studio BGM Library (Module M05)."""

import math
from pathlib import Path
from typing import List, Optional
import wave
import numpy as np

from app.m00_core_contracts import BGMPresetDTO, MASTER_AUDIO_SAMPLE_RATE

BGM_SPECS = (
    (
        "bgm_luxury_acoustic",
        "Hòa tấu Đàn Violin & Guitar Acoustic ấm áp",
        "PRODUCT",
        "Giai điệu đàn dây mộc mạc, êm dịu tôn vinh nhạc cụ gỗ và sản phẩm thủ công",
        "violin_guitar",
    ),
    (
        "bgm_lofi_story",
        "Đàn Piano trầm lắng & sâu sắc",
        "TOPIC",
        "Tiếng dương cầm mềm mại phù hợp chia sẻ câu chuyện và tư vấn nhẹ nhàng",
        "felt_piano",
    ),
    (
        "bgm_upbeat_shop",
        "Guitar Acoustic rải hợp âm tươi sáng",
        "TIKTOK",
        "Nhịp guitar mộc trẻ trung, giữ nhịp tự nhiên cho video thời trang và đời sống",
        "acoustic_fingerstyle",
    ),
    (
        "bgm_drama_tension",
        "Hòa tấu Cello trầm điện ảnh",
        "MOVIE",
        "Âm trầm sâu lắng dành riêng cho thuyết minh phim bộ và kịch tính",
        "cello_cinema",
    ),
)


def _warm_lowpass(sig: np.ndarray, kernel_len: int = 19) -> np.ndarray:
    """Apply smooth FIR low-pass filter to remove harsh digital harmonics for natural wood warmth."""
    win = np.hanning(kernel_len).astype(np.float32)
    win /= np.sum(win)
    return np.convolve(sig, win, mode="same").astype(np.float32)


def _bowed_string_voice(t: np.ndarray, freq: float, vibrato_hz: float = 5.1) -> np.ndarray:
    """Expressive bowed Violin / Cello wave with natural delayed vibrato & warm harmonics."""
    vib_env = np.minimum(1.0, t / 0.65)
    phase_mod = (0.0032 * vib_env) * np.sin(2.0 * math.pi * vibrato_hz * t)
    inst_phase = 2.0 * math.pi * freq * (t + phase_mod)
    wave_out = (
        0.68 * np.sin(inst_phase)
        + 0.22 * np.sin(2.0 * inst_phase + 0.3)
        + 0.08 * np.sin(3.0 * inst_phase + 0.7)
        + 0.03 * np.sin(4.0 * inst_phase)
    )
    attack = np.minimum(1.0, t / 0.38) ** 1.3
    release = np.minimum(1.0, np.maximum(0.0, (t[-1] - t) / 0.42))
    return (wave_out * attack * release).astype(np.float32)


def _plucked_nylon_guitar(t: np.ndarray, freq: float, delay_sec: float) -> np.ndarray:
    """Karplus-inspired warm nylon guitar pluck with natural wooden body resonance."""
    dt = np.maximum(0.0, t - delay_sec)
    active = (t >= delay_sec).astype(np.float32)
    env = np.exp(-1.55 * dt) * np.minimum(1.0, dt / 0.012) * active
    # Higher harmonics decay faster than fundamental just like a real acoustic string!
    f1 = np.sin(2.0 * math.pi * freq * dt)
    f2 = 0.36 * np.sin(2.0 * math.pi * (2.0 * freq) * dt) * np.exp(-2.6 * dt)
    f3 = 0.14 * np.sin(2.0 * math.pi * (3.0 * freq) * dt) * np.exp(-4.2 * dt)
    return ((f1 + f2 + f3) * env).astype(np.float32)


class StudioBGMLibrary:
    """Generates and serves 4 warm acoustic copyright-free WAV tracks + custom file resolution."""

    @classmethod
    def ensure_builtin_tracks(cls, bgm_dir: Path) -> List[BGMPresetDTO]:
        bgm_dir.mkdir(parents=True, exist_ok=True)
        presets: List[BGMPresetDTO] = []
        for pid, name, cat, desc, style in BGM_SPECS:
            wav_p = bgm_dir / f"{pid}_v2.wav"
            if not wav_p.exists() or wav_p.stat().st_size < 8192:
                cls._render_acoustic_track(wav_p, style, duration_sec=20.0)
            presets.append(
                BGMPresetDTO(
                    preset_id=pid,
                    display_name=name,
                    mood_category=cat,
                    description=desc,
                    wav_path=wav_p,
                )
            )
        return presets

    @classmethod
    def resolve_bgm_path(cls, bgm_dir: Path, preset_or_path: Optional[str]) -> Optional[Path]:
        if not preset_or_path or preset_or_path == "NONE":
            return None
        presets = cls.ensure_builtin_tracks(bgm_dir)
        for pr in presets:
            if pr.preset_id == preset_or_path:
                return pr.wav_path
        candidate = Path(preset_or_path)
        return candidate if candidate.exists() else None

    @staticmethod
    def _render_acoustic_track(dst_wav: Path, style: str, duration_sec: float = 20.0) -> None:
        sr = MASTER_AUDIO_SAMPLE_RATE
        n_total = int(sr * duration_sec)
        left = np.zeros(n_total, dtype=np.float32)
        right = np.zeros(n_total, dtype=np.float32)

        # Lyrical G-major / E-minor progression: Gmaj7 -> Em7 -> Cmaj7 -> Dadd9
        progression = (
            ((196.00, 246.94, 293.66, 369.99), 587.33),  # Gmaj7 + Violin D5
            ((164.81, 246.94, 293.66, 392.00), 493.88),  # Em7   + Violin B4
            ((130.81, 196.00, 246.94, 329.63), 523.25),  # Cmaj7 + Violin C5
            ((146.83, 220.00, 293.66, 369.99), 440.00),  # D6    + Violin A4
        )
        bar_len = n_total // len(progression)

        for b_idx, (chord_freqs, melody_freq) in enumerate(progression):
            s0 = b_idx * bar_len
            s1 = n_total if b_idx == len(progression) - 1 else (b_idx + 1) * bar_len
            seg_n = s1 - s0
            t = np.arange(seg_n, dtype=np.float32) / float(sr)

            bar_l = np.zeros(seg_n, dtype=np.float32)
            bar_r = np.zeros(seg_n, dtype=np.float32)

            if style == "violin_guitar":
                # Gentle arpeggiated nylon guitar accompaniment + warm cantabile Violin melody
                for n_i, f_hz in enumerate(chord_freqs):
                    pluck = _plucked_nylon_guitar(t, f_hz, n_i * 0.34)
                    pluck2 = _plucked_nylon_guitar(t, f_hz, 2.4 + n_i * 0.34)
                    bar_l += (pluck + 0.8 * pluck2) * (0.24 if n_i % 2 == 0 else 0.16)
                    bar_r += (pluck + 0.8 * pluck2) * (0.16 if n_i % 2 == 0 else 0.24)
                violin_mel = _bowed_string_voice(t, melody_freq, vibrato_hz=5.2) * 0.22
                bar_l += violin_mel * 0.92
                bar_r += violin_mel * 1.05
            elif style == "acoustic_fingerstyle":
                pattern = (0, 2, 1, 3, 2, 1, 0, 3)
                step_sec = (seg_n / float(sr)) / len(pattern)
                for p_i, c_slot in enumerate(pattern):
                    pl = _plucked_nylon_guitar(t, chord_freqs[c_slot] * 1.5, p_i * step_sec)
                    bar_l += pl * (0.28 if p_i % 2 == 0 else 0.18)
                    bar_r += pl * (0.18 if p_i % 2 == 0 else 0.28)
            elif style == "cello_cinema":
                cello_root = _bowed_string_voice(t, chord_freqs[0] * 0.5, vibrato_hz=4.4) * 0.34
                cello_fifth = _bowed_string_voice(t, chord_freqs[1] * 0.5, vibrato_hz=4.6) * 0.22
                bar_l += cello_root + 0.7 * cello_fifth
                bar_r += 0.85 * cello_root + cello_fifth
            else:
                # felt_piano
                for n_i, f_hz in enumerate(chord_freqs):
                    note = _plucked_nylon_guitar(t, f_hz, n_i * 0.12) * 0.26
                    bar_l += note * (0.95 if n_i < 2 else 0.75)
                    bar_r += note * (0.75 if n_i < 2 else 0.95)
                mel_note = _plucked_nylon_guitar(t, melody_freq * 0.5, 1.8) * 0.22
                bar_l += mel_note * 0.85
                bar_r += mel_note

            left[s0:s1] = bar_l
            right[s0:s1] = bar_r

        # Warm wooden body low-pass + subtle stereo room ambiance
        left = _warm_lowpass(left, kernel_len=21)
        right = _warm_lowpass(right, kernel_len=21)
        delay_samples = int(0.028 * sr)
        if delay_samples < n_total:
            left[delay_samples:] += 0.18 * right[:-delay_samples]
            right[delay_samples:] += 0.18 * left[:-delay_samples]

        # Loop-end smooth fade
        fade_n = int(0.25 * sr)
        left[:fade_n] *= np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        right[:fade_n] *= np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        left[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
        right[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

        peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-4)
        norm_gain = 0.65 / peak
        stereo = np.column_stack((left * norm_gain, right * norm_gain))
        pcm16 = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(str(dst_wav), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm16.tobytes())
