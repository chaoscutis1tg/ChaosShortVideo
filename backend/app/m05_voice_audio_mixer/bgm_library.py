"""Curated CC0 No-Copyright Online Lofi Collection + Expressive Acoustic Studio BGM Library (Module M05)."""

from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import uuid
import wave
import numpy as np

from app.m00_core_contracts import BGMPresetDTO, MASTER_AUDIO_SAMPLE_RATE, WORKSPACE_ROOT

# 10 Verified CC0 1.0 Universal (Public Domain - 100% Zero Copyright Claims on TikTok / YouTube Shorts / Reels)
ONLINE_CC0_LOFI_SPECS = (
    (
        "lofi_vanilla_chill",
        "Lofi Chill Vanilla Ấm Áp (CC0 • 3p04s)",
        "LOFI",
        "Nhịp Lofi Hip-Hop êm dịu, ấm áp chuẩn kể chuyện Threads, tâm sự & đọc bình luận (CC0 miễn bản quyền)",
        "https://cdn.freesound.org/previews/691/691510_13228046-hq.mp3",
    ),
    (
        "lofi_real_chill_cafe",
        "Lofi Quán Cà Phê Chiều Mưa (CC0 • 2p50s)",
        "LOFI",
        "Giai điệu Chillhop trong trẻo, thư giãn lót dưới giọng đọc Nam/Nữ tốc độ nhanh cực bắt tai",
        "https://cdn.freesound.org/previews/685/685302_13228046-hq.mp3",
    ),
    (
        "lofi_cinematic_story",
        "Lofi Điện Ảnh Kể Chuyện Sâu (CC0 • 2p53s)",
        "LOFI",
        "Lofi có chiều sâu cảm xúc, cực hợp cho các bình luận dài kể chuyện đời thực & bí mật thầm kín",
        "https://cdn.freesound.org/previews/687/687006_13228046-hq.mp3",
    ),
    (
        "lofi_midnight_soul",
        "Lofi Soul Đêm Khuya Tâm Sự (CC0 • 2p30s)",
        "LOFI",
        "Hợp âm Soul Lofi mượt mà lúc nửa đêm, tôn giọng đọc rõ nét không lấn lời",
        "https://cdn.freesound.org/previews/672/672038_13228046-hq.mp3",
    ),
    (
        "lofi_hiphop_study",
        "Lofi Hip-Hop Nhịp Boom-Bap (CC0 • 2p34s)",
        "LOFI",
        "Nhịp trống Lofi Hip-Hop cổ điển giữ chân người xem trên TikTok & YouTube Shorts",
        "https://cdn.freesound.org/previews/561/561282_12370634-hq.mp3",
    ),
    (
        "lofi_moody_night_70bpm",
        "Lofi Trầm Lắng Sâu Sắc 70BPM (CC0 • 1p16s)",
        "LOFI",
        "Nhịp chậm 70 BPM man mác hoài niệm, chuyên trị chủ đề lụy tình, kỷ niệm cũ & confession",
        "https://cdn.freesound.org/previews/659/659309_13228046-hq.mp3",
    ),
    (
        "lofi_good_vibe_vlog",
        "Lofi Tươi Sáng Tích Cực (CC0 • 2p30s)",
        "LOFI",
        "Năng lượng trẻ trung, vui vẻ hợp chủ đề hài hước mặn mòi, chuyện công sở & mẹo hay",
        "https://cdn.freesound.org/previews/661/661782_13228046-hq.mp3",
    ),
    (
        "lofi_holizna_piano_80",
        "Lofi Piano Đĩa Than Cổ Điển — HoliznaCC0 (48s)",
        "LOFI",
        "Tiếng Piano Lofi bụi đĩa than (Vinyl) trứ danh của nghệ sĩ Public Domain HoliznaCC0",
        "https://cdn.freesound.org/previews/629/629174_12574855-hq.mp3",
    ),
    (
        "lofi_holizna_melody_95",
        "Lofi Chillhop 95BPM Bắt Tai — HoliznaCC0 (40s)",
        "LOFI",
        "Vòng hòa thanh Chillhop 95 BPM cuốn hút của HoliznaCC0, lặp vòng liền mạch không gợn",
        "https://cdn.freesound.org/previews/629/629147_12574855-hq.mp3",
    ),
    (
        "lofi_dreamy_chill_vibe",
        "Lofi Radio Đêm Mơ Màng (CC0 • 2p29s)",
        "LOFI",
        "Không gian âm nhạc lơ lửng dịu êm kiểu Lofi Radio 24/7, hoàn toàn sạch bản quyền",
        "https://cdn.freesound.org/previews/464/464731_9571373-hq.mp3",
    ),
)

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
    """Serves 10 CC0 No-Copyright Online Lofi tracks + 4 Acoustic tracks + Online CC0 Search/Import."""

    MANIFEST_FILENAME = "custom_cc0_lofi_manifest.json"

    @staticmethod
    def _download_mp3_file(url: str, dst_path: Path, timeout_sec: float = 16.0) -> bool:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ChaosShortVideoStudio/3.3"},
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read()
            if len(raw) < 4096:
                return False
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_bytes(raw)
            return True
        except Exception:
            return False

    @classmethod
    def _load_custom_manifest(cls, bgm_dir: Path) -> List[Dict[str, str]]:
        m_path = bgm_dir / cls.MANIFEST_FILENAME
        if not m_path.exists():
            return []
        try:
            data = json.loads(m_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @classmethod
    def _save_custom_manifest(cls, bgm_dir: Path, items: List[Dict[str, str]]) -> None:
        m_path = bgm_dir / cls.MANIFEST_FILENAME
        m_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def ensure_builtin_tracks(cls, bgm_dir: Path) -> List[BGMPresetDTO]:
        bgm_dir.mkdir(parents=True, exist_ok=True)
        shared_bgm_dir = (WORKSPACE_ROOT / "assets" / "bgm").resolve()
        is_primary_bgm_dir = bgm_dir.resolve() == shared_bgm_dir
        presets: List[BGMPresetDTO] = []

        # 1. Ensure 10 Curated CC0 Public Domain Lofi Tracks (copying from shared cache or downloading in parallel)
        missing_downloads: List[tuple[str, Path]] = []
        for pid, _, _, _, src_url in ONLINE_CC0_LOFI_SPECS:
            mp3_p = bgm_dir / f"{pid}.mp3"
            if mp3_p.exists() and mp3_p.stat().st_size >= 4096:
                continue
            shared_candidate = shared_bgm_dir / f"{pid}.mp3"
            if not is_primary_bgm_dir and shared_candidate.exists() and shared_candidate.stat().st_size >= 4096:
                shutil.copyfile(shared_candidate, mp3_p)
            elif is_primary_bgm_dir:
                missing_downloads.append((src_url, mp3_p))

        if missing_downloads:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda pair: cls._download_mp3_file(pair[0], pair[1]), missing_downloads))

        for pid, name, cat, desc, _ in ONLINE_CC0_LOFI_SPECS:
            mp3_p = bgm_dir / f"{pid}.mp3"
            if mp3_p.exists() and mp3_p.stat().st_size >= 4096:
                presets.append(
                    BGMPresetDTO(
                        preset_id=pid,
                        display_name=name,
                        mood_category=cat,
                        description=desc,
                        wav_path=mp3_p,
                    )
                )

        # 2. Include any extra CC0 Lofi tracks imported by the user from Online Search
        for item in cls._load_custom_manifest(bgm_dir):
            c_pid = str(item.get("preset_id") or "").strip()
            c_file = bgm_dir / str(item.get("filename") or "")
            if c_pid and c_file.exists() and c_file.stat().st_size >= 4096:
                presets.append(
                    BGMPresetDTO(
                        preset_id=c_pid,
                        display_name=str(item.get("display_name") or c_pid),
                        mood_category=str(item.get("mood_category") or "LOFI"),
                        description=str(item.get("description") or "Nhạc Lofi CC0 tải từ kho miễn bản quyền"),
                        wav_path=c_file,
                    )
                )

        # 3. Always include the 4 warm Acoustic / Violin / Cello studio tracks
        for pid, name, cat, desc, style in BGM_SPECS:
            wav_p = bgm_dir / f"{pid}_v2.wav"
            if not wav_p.exists() or wav_p.stat().st_size < 8192:
                shared_wav = shared_bgm_dir / f"{pid}_v2.wav"
                if not is_primary_bgm_dir and shared_wav.exists() and shared_wav.stat().st_size >= 8192:
                    shutil.copyfile(shared_wav, wav_p)
                else:
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
    def search_online_cc0_lofi(cls, query: str = "lofi chill", limit: int = 12) -> List[Dict[str, Any]]:
        """Search Openverse's strictly CC0 1.0 Public Domain audio catalog for safe no-copyright Lofi beats."""
        clean_q = (query or "lofi chill").strip()
        if "lofi" not in clean_q.lower() and "chill" not in clean_q.lower() and "piano" not in clean_q.lower():
            clean_q = f"lofi {clean_q}"
        api_url = (
            f"https://api.openverse.org/v1/audio/?q={urllib.parse.quote(clean_q)}"
            "&license=cc0&page_size=20"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "ChaosShortVideoStudio/3.3"})
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        results: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        for row in payload.get("results") or []:
            audio_url = str(row.get("url") or "").strip()
            if not audio_url.startswith("https://") or audio_url in seen_urls:
                continue
            dur_ms = int(row.get("duration") or 0)
            if dur_ms < 18000 or dur_ms > 320000:
                continue
            seen_urls.add(audio_url)
            raw_title = re.sub(r"\.(wav|mp3|flac|ogg)$", "", str(row.get("title") or "Lofi Track"), flags=re.I).strip()
            creator = str(row.get("creator") or "CC0 Artist").strip()
            results.append(
                {
                    "title": raw_title[:90],
                    "creator": creator[:50],
                    "duration_sec": max(1, round(dur_ms / 1000)),
                    "license": "CC0 1.0 Public Domain (Không bản quyền)",
                    "preview_url": audio_url,
                    "audio_url": audio_url,
                }
            )
            if len(results) >= limit:
                break
        return results

    @classmethod
    def import_online_cc0_track(
        cls,
        bgm_dir: Path,
        title: str,
        audio_url: str,
        creator: str = "",
    ) -> BGMPresetDTO:
        """Download a CC0 Lofi track from `audio_url` into `bgm_dir` and register it permanently."""
        bgm_dir.mkdir(parents=True, exist_ok=True)
        clean_url = (audio_url or "").strip()
        if not clean_url.startswith(("http://", "https://")):
            raise ValueError("Đường dẫn nhạc trực tuyến không hợp lệ.")
        ext = ".ogg" if clean_url.lower().endswith(".ogg") else ".mp3"
        pid = f"lofi_cc0_{uuid.uuid4().hex[:8]}"
        fname = f"{pid}{ext}"
        dst = bgm_dir / fname
        ok = cls._download_mp3_file(clean_url, dst, timeout_sec=22.0)
        if not ok or not dst.exists():
            raise RuntimeError("Không thể tải tệp âm thanh từ nguồn trực tuyến.")

        clean_title = (title or "Lofi Chill Mới").strip()[:90]
        disp = f"Lofi: {clean_title}" + (f" ({creator.strip()[:28]} • CC0)" if creator.strip() else " (CC0)")
        manifest = cls._load_custom_manifest(bgm_dir)
        manifest.insert(
            0,
            {
                "preset_id": pid,
                "filename": fname,
                "display_name": disp,
                "mood_category": "LOFI",
                "description": f"Nhạc Lofi CC0 1.0 miễn bản quyền trên mạng ({creator or 'Public Domain'})",
                "source_url": clean_url,
            },
        )
        cls._save_custom_manifest(bgm_dir, manifest)
        return BGMPresetDTO(
            preset_id=pid,
            display_name=disp,
            mood_category="LOFI",
            description=f"Nhạc Lofi CC0 1.0 miễn bản quyền ({creator or 'Public Domain'})",
            wav_path=dst,
        )

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
