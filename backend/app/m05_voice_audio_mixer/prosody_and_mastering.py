"""Vietnamese Dramatic Prosody Enhancer & Broadcast Dubbing Studio Mastering DSP."""

from pathlib import Path
import re
import subprocess
import wave

from app.m00_core_contracts import MASTER_AUDIO_SAMPLE_RATE, VoiceSynthesisError

DRAMATIC_OPENERS = (
    "không ai ngờ rằng",
    "không ai ngờ",
    "thật không ngờ",
    "thế nhưng",
    "nhưng không ngờ",
    "hóa ra",
    "ngay khoảnh khắc đó",
    "ngay lúc đó",
    "ngay lập tức",
    "bất ngờ thay",
    "đáng tiếc thay",
    "trớ trêu thay",
    "chỉ trong chớp mắt",
    "sự thật là",
    "thực chất",
    "cuối cùng",
    "điều đáng sợ là",
)

CLAUSE_BREAK_CONJUNCTIONS = (
    "lại chính là",
    "nhưng lại",
    "thế mà",
    "để rồi",
    "khiến cho",
    "nhưng",
    "thì",
)


def _probe_wav_ms(wav_path: Path) -> int:
    with wave.open(str(wav_path), "rb") as wf:
        return max(1, int(round((wf.getnframes() / float(wf.getframerate())) * 1000.0)))


_VN_DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")


def _int_to_vietnamese_words(n: int) -> str:
    """Convert non-negative integer `0..9999` into natural spoken Vietnamese words."""
    if n < 0 or n > 9999:
        return str(n)
    if n < 10:
        return _VN_DIGITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        prefix = "mười" if tens == 1 else f"{_VN_DIGITS[tens]} mươi"
        if unit == 0:
            return prefix
        if unit == 1 and tens > 1:
            return f"{prefix} mốt"
        if unit == 4 and tens > 1:
            return f"{prefix} tư"
        if unit == 5:
            return f"{prefix} lăm"
        return f"{prefix} {_VN_DIGITS[unit]}"
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        head = f"{_VN_DIGITS[hundreds]} trăm"
        if rem == 0:
            return head
        if rem < 10:
            return f"{head} lẻ {_VN_DIGITS[rem]}"
        return f"{head} {_int_to_vietnamese_words(rem)}"
    thousands, rem = divmod(n, 1000)
    head = f"{_VN_DIGITS[thousands]} nghìn"
    if rem == 0:
        return head
    if rem < 10:
        return f"{head} không trăm lẻ {_VN_DIGITS[rem]}"
    if rem < 100:
        return f"{head} không trăm {_int_to_vietnamese_words(rem)}"
    return f"{head} {_int_to_vietnamese_words(rem)}"


def _verbalize_numbers_for_vietnamese_tts(text: str) -> str:
    """Convert standalone numbers & percentages into Vietnamese words so Multilingual TTS never reads English digits."""
    text = re.sub(
        r"\b(\d{1,4})\s*%",
        lambda m: f"{_int_to_vietnamese_words(int(m.group(1)))} phần trăm",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-zÀ-ỹ\d])(\d{1,4})(?![A-Za-zÀ-ỹ\d])",
        lambda m: _int_to_vietnamese_words(int(m.group(1))),
        text,
    )
    return text


class DramaticProsodyEnhancer:
    """Injects natural human breath pauses and dramatic emphasis cues into Vietnamese lines."""

    @classmethod
    def enhance(cls, raw_text: str) -> str:
        """Format Vietnamese narration text with expressive punctuation for neural TTS."""
        text = re.sub(r"[♪♫]+", " ", raw_text)
        text = _verbalize_numbers_for_vietnamese_tts(text)
        text = " ".join(text.split()).strip()
        if not text:
            return ""

        low = text.lower()
        for opener in DRAMATIC_OPENERS:
            if low.startswith(opener):
                rest = text[len(opener) :].lstrip()
                if rest and rest[0] not in (",", ".", "!", "?", ":", ";", "—", "-"):
                    text = f"{text[:len(opener)]}, {rest}"
                break

        # Insert a natural breath comma in long unpunctuated clauses (> 9 words)
        if "," not in text and ";" not in text:
            words = text.split()
            if len(words) >= 9:
                text = cls._insert_mid_clause_pause(text)

        if text[-1] not in (".", "!", "?", "…"):
            text = f"{text}."
        return text

    @staticmethod
    def _insert_mid_clause_pause(text: str) -> str:
        for conj in CLAUSE_BREAK_CONJUNCTIONS:
            pattern = re.compile(rf"^((?:\S+\s+){{3,9}})({re.escape(conj)}\s+(?:\S+\s*){{2,}})$", re.I)
            m = pattern.match(text)
            if m:
                left = m.group(1).rstrip()
                right = m.group(2)
                if not left.endswith((",", ".", "!", "?")):
                    return f"{left}, {right}"
        return text


class StudioVoiceMasteringDSP:
    """Applies broadcast EQ, dynamic compression, subtle booth warmth & pitch/tempo sculpting."""

    EQ_PRESETS = {
        "movie_male_deep": (
            "highpass=f=70,"
            "equalizer=f=130:width_type=o:width=1.1:g=3.6,"
            "equalizer=f=330:width_type=o:width=1.0:g=-1.4,"
            "equalizer=f=3500:width_type=o:width=1.4:g=2.6,"
            "acompressor=threshold=-18dB:ratio=3.0:attack=12:release=170:makeup=2.2,"
            "aecho=0.8:0.88:18:0.05"
        ),
        "drama_female_emotional": (
            "highpass=f=85,"
            "equalizer=f=185:width_type=o:width=1.2:g=2.8,"
            "equalizer=f=4600:width_type=o:width=1.5:g=2.8,"
            "acompressor=threshold=-19dB:ratio=2.6:attack=16:release=210:makeup=2.0,"
            "aecho=0.8:0.88:22:0.06"
        ),
        "thriller_suspense": (
            "highpass=f=75,"
            "equalizer=f=145:width_type=o:width=1.1:g=3.4,"
            "equalizer=f=3200:width_type=o:width=1.3:g=3.2,"
            "acompressor=threshold=-16dB:ratio=3.5:attack=8:release=140:makeup=2.4"
        ),
        "artisan_warm_studio": (
            "highpass=f=68,"
            "equalizer=f=155:width_type=o:width=1.2:g=3.2,"
            "equalizer=f=380:width_type=o:width=1.0:g=-1.2,"
            "equalizer=f=3800:width_type=o:width=1.5:g=2.1,"
            "acompressor=threshold=-19dB:ratio=2.5:attack=18:release=230:makeup=2.0,"
            "aecho=0.8:0.88:20:0.04"
        ),
        "luxury_silk_female": (
            "highpass=f=82,"
            "equalizer=f=195:width_type=o:width=1.2:g=2.6,"
            "equalizer=f=4800:width_type=o:width=1.6:g=2.5,"
            "acompressor=threshold=-19dB:ratio=2.4:attack=18:release=220:makeup=1.9,"
            "aecho=0.8:0.88:24:0.05"
        ),
        "cinema_uslt_female": (
            "highpass=f=85,"
            "equalizer=f=190:width_type=o:width=1.1:g=2.4,"
            "equalizer=f=360:width_type=o:width=1.0:g=-1.8,"
            "equalizer=f=3100:width_type=o:width=1.3:g=3.4,"
            "acompressor=threshold=-17dB:ratio=3.2:attack=10:release=160:makeup=2.3"
        ),
        "cinema_uslt_male": (
            "highpass=f=72,"
            "equalizer=f=135:width_type=o:width=1.1:g=3.4,"
            "equalizer=f=340:width_type=o:width=1.0:g=-1.8,"
            "equalizer=f=3000:width_type=o:width=1.3:g=3.2,"
            "acompressor=threshold=-17dB:ratio=3.2:attack=10:release=165:makeup=2.3"
        ),
        "tiktok_punchy_bright": (
            "highpass=f=95,"
            "equalizer=f=210:width_type=o:width=1.1:g=2.0,"
            "equalizer=f=4200:width_type=o:width=1.4:g=3.5,"
            "acompressor=threshold=-16dB:ratio=3.4:attack=6:release=125:makeup=2.5"
        ),
        "yt_documentary_warm": (
            "highpass=f=72,"
            "equalizer=f=150:width_type=o:width=1.2:g=3.0,"
            "equalizer=f=350:width_type=o:width=1.0:g=-1.3,"
            "equalizer=f=3700:width_type=o:width=1.5:g=2.2,"
            "acompressor=threshold=-18dB:ratio=2.6:attack=15:release=210:makeup=2.0"
        ),
        "horror_dark_male": (
            "highpass=f=65,"
            "equalizer=f=115:width_type=o:width=1.1:g=4.0,"
            "equalizer=f=3600:width_type=o:width=1.4:g=2.8,"
            "acompressor=threshold=-17dB:ratio=3.2:attack=12:release=190:makeup=2.3,"
            "aecho=0.8:0.86:28:0.08"
        ),
    }

    @classmethod
    def master_audio(
        cls,
        src_audio: Path,
        dst_wav: Path,
        speed_rate: float = 1.0,
        pitch_semitones: float = 0.0,
        preset: str = "movie_male_deep",
        src_sample_rate: int = 22050,
    ) -> int:
        """Process raw TTS output into warm, expressive 44.1kHz stereo broadcast WAV."""
        dst_wav.parent.mkdir(parents=True, exist_ok=True)
        filters: list[str] = []

        # Pitch shift via sample-rate scaling + tempo compensation
        pitch_ratio = 2.0 ** (float(pitch_semitones) / 12.0)
        compensated_tempo = float(speed_rate) / pitch_ratio

        if abs(pitch_semitones) >= 0.15:
            shifted_sr = int(round(src_sample_rate * pitch_ratio))
            filters.append(f"asetrate={shifted_sr}")
            filters.append(f"aresample={MASTER_AUDIO_SAMPLE_RATE}")
        else:
            filters.append(f"aresample={MASTER_AUDIO_SAMPLE_RATE}")

        # Chain safe atempo stages within [0.5, 2.0]
        rem_tempo = max(0.60, min(1.85, compensated_tempo))
        if abs(rem_tempo - 1.0) >= 0.02:
            filters.append(f"atempo={rem_tempo:.4f}")

        eq_chain = cls.EQ_PRESETS.get(preset, cls.EQ_PRESETS["movie_male_deep"])
        filters.append(eq_chain)
        filters.append("alimiter=limit=0.95")

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src_audio),
            "-af",
            ",".join(filters),
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(MASTER_AUDIO_SAMPLE_RATE),
            "-ac",
            "2",
            str(dst_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
        if proc.returncode != 0 or not dst_wav.exists():
            raise VoiceSynthesisError(f"Xử lý âm thanh phòng thu thất bại: {proc.stderr.strip()}")
        return _probe_wav_ms(dst_wav)

