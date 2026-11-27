"""ASS (Advanced SubStation Alpha) 1080x1920 Karaoke & Cinema subtitle generator."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional

from app.m00_core_contracts import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    SubtitleStyle,
    WordTimestampDTO,
)

MAX_WORDS_PER_KARAOKE_CHUNK = 6

_DIGIT_RE = re.compile(r"\d")
_CLEAN_WORD_RE = re.compile(r"[^\wà-ỹÀ-Ỹ%$€₫]+", re.UNICODE)

_VN_STOPWORDS = {
    "nhưng", "những", "trong", "ngoài", "không", "chẳng", "được", "đang", "vẫn",
    "cũng", "nhiều", "người", "mình", "chúng", "cùng", "nhau", "thôi", "luôn",
    "rồi", "với", "của", "cho", "khi", "nếu", "thì", "mà", "là", "vì", "để",
    "tại", "theo", "này", "kia", "đấy", "đây", "vậy", "sao", "thế", "nào",
    "một", "hai", "các", "cái", "con", "bạn", "tôi", "anh", "chị", "em", "họ",
    "rất", "quá", "lắm", "hơn", "nhất", "nữa", "mới", "vừa", "đến", "tới",
}

_VN_IMPACT_WORDS = {
    "bímật", "sựthật", "sailầm", "cảnhbáo", "tuyệtđối", "bấtngờ", "hốihận",
    "đỉnhcao", "miễnphí", "độcquyền", "duynhất", "quantrọng", "nguyhiểm",
    "ámảnh", "kinhhoàng", "độtphá", "nguyênbản", "thủcông", "sốc", "khóc",
}

_VN_UNITS = {
    "năm", "tháng", "tuần", "ngày", "giờ", "phút", "giây", "tuổi",
    "triệu", "nghìn", "ngàn", "tỷ", "lần", "bước", "cấp", "phần",
}


def _pick_highlight_token_indices(tokens: List[str], max_picks: int = 2) -> set[int]:
    """Select 1-2 high-impact keyword token indices (numbers+units, impact words, or salient nouns)."""
    if len(tokens) < 3:
        return set()
    cap = 1 if len(tokens) <= 7 else max_picks
    picked: set[int] = set()

    cleaned = [_CLEAN_WORD_RE.sub("", t).lower() for t in tokens]

    # 1. Numbers (+ immediately following unit word like '3 năm', '15 phút')
    for i, raw_tok in enumerate(tokens):
        if len(picked) >= cap:
            break
        if _DIGIT_RE.search(raw_tok):
            picked.add(i)
            if i + 1 < len(cleaned) and cleaned[i + 1] in _VN_UNITS:
                picked.add(i + 1)

    if len(picked) >= cap:
        return picked

    # 2. High-impact compound pairs or single emotional words
    for i in range(len(cleaned)):
        if len(picked) >= cap:
            break
        if i + 1 < len(cleaned) and (cleaned[i] + cleaned[i + 1]) in _VN_IMPACT_WORDS:
            picked.add(i)
            picked.add(i + 1)
        elif cleaned[i] in _VN_IMPACT_WORDS:
            picked.add(i)

    if len(picked) >= cap:
        return picked

    # 3. Salient non-stopword content token in sentences >= 5 words
    if len(tokens) >= 5 and not picked:
        candidates = [
            (len(cleaned[i]), i)
            for i in range(len(cleaned))
            if len(cleaned[i]) >= 5 and cleaned[i] not in _VN_STOPWORDS
        ]
        if candidates:
            candidates.sort(reverse=True)
            picked.add(candidates[0][1])

    return picked


def _apply_cinema_keyword_tags(text: str) -> str:
    """Wrap 1-2 punch words in warm gold ASS override tags `{\\c&H0024D8FF&}...{\\c&HFFFFFF&}`."""
    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""
    hl = _pick_highlight_token_indices(tokens, max_picks=2)
    if not hl:
        return _escape_ass_text(text)
    out: List[str] = []
    for i, tok in enumerate(tokens):
        esc = _escape_ass_text(tok)
        if i in hl:
            out.append(f"{{\\c&H0024D8FF&}}{esc}{{\\c&HFFFFFF&}}")
        else:
            out.append(esc)
    return " ".join(out)


@dataclass
class TimedSubtitleEvent:
    """Actual timeline placement of a spoken line after TTS time-sync."""

    start_ms: int
    end_ms: int
    text: str
    words: List[WordTimestampDTO]


def _fmt_ass_time(ms: int) -> str:
    ms = max(0, ms)
    cs = (ms % 1000) // 10
    total_sec = ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(raw: str) -> str:
    return raw.replace("\\", "").replace("{", "(").replace("}", ")").strip()


def _fmt_srt_time(ms: int) -> str:
    ms = max(0, int(ms))
    millis = ms % 1000
    total_sec = ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


class ASSSubtitleBuilder:
    """Generates styled `.ass` and standard `.srt` files for Shorts/TikTok & CapCut PC."""

    @classmethod
    def build_srt_file(
        cls,
        events: List[TimedSubtitleEvent],
        out_srt_path: Path,
    ) -> Optional[Path]:
        """Export standard UTF-8 `.srt` subtitle file for CapCut PC / Premiere import."""
        if not events:
            return None
        out_srt_path.parent.mkdir(parents=True, exist_ok=True)
        blocks: List[str] = []
        seq = 1
        for ev in events:
            txt = (ev.text or "").strip()
            if not txt:
                continue
            end_ms = max(ev.start_ms + 250, ev.end_ms)
            blocks.append(
                f"{seq}\n{_fmt_srt_time(ev.start_ms)} --> {_fmt_srt_time(end_ms)}\n{txt}\n"
            )
            seq += 1
        if not blocks:
            return None
        out_srt_path.write_text("\n".join(blocks), encoding="utf-8")
        return out_srt_path

    @classmethod
    def build_ass_file(
        cls,
        events: List[TimedSubtitleEvent],
        style: SubtitleStyle,
        out_ass_path: Path,
        margin_v_px: Optional[int] = None,
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
        subtitle_pos_y: float = 0.84,
        subtitle_font_size: Optional[int] = None,
        smart_keyword_highlight: bool = True,
    ) -> Optional[Path]:
        """Write `.ass` file positioned at `subtitle_pos_y` (`[0.15..0.95]`) and `subtitle_font_size`."""
        if style == SubtitleStyle.NONE or not events:
            return None

        out_ass_path.parent.mkdir(parents=True, exist_ok=True)
        is_karaoke = style == SubtitleStyle.KARAOKE_CAPCUT
        base_fsize = subtitle_font_size if subtitle_font_size is not None else (60 if is_karaoke else 50)
        # Scale font gracefully on shorter 4:5 or 1:1 canvases so lines never wrap awkwardly
        height_scale = min(1.0, max(0.76, canvas_h / 1920.0))
        font_size = max(26, int(round(base_fsize * (0.86 + 0.14 * height_scale))))
        eff_margin_v = (
            margin_v_px
            if margin_v_px is not None
            else max(28, min(canvas_h - 90, int(round(canvas_h * (1.0 - subtitle_pos_y)))))
        )
        # ASS colors use &HAABBGGRR: Primary yellow-gold for Karaoke highlight, white secondary
        primary_col = "&H0000EAFF" if is_karaoke else "&H00FFFFFF"
        secondary_col = "&H00FFFFFF"

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            f"PlayResX: {canvas_w}\n"
            f"PlayResY: {canvas_h}\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: StudioSub,Segoe UI,{font_size},{primary_col},{secondary_col},&H00000000,&H78000000,"
            f"-1,0,0,0,100,100,0,0,1,4.2,2.0,2,64,64,{eff_margin_v},1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        dialogue_lines: List[str] = []
        for ev in events:
            if is_karaoke and ev.words:
                dialogue_lines.extend(
                    cls._render_karaoke_chunks(ev, smart_keyword_highlight=smart_keyword_highlight)
                )
            else:
                formatted_txt = (
                    _apply_cinema_keyword_tags(ev.text)
                    if smart_keyword_highlight
                    else _escape_ass_text(ev.text)
                )
                if formatted_txt:
                    dialogue_lines.append(
                        f"Dialogue: 0,{_fmt_ass_time(ev.start_ms)},{_fmt_ass_time(ev.end_ms)},"
                        f"StudioSub,,0,0,0,,{formatted_txt}"
                    )

        out_ass_path.write_text(header + "\n".join(dialogue_lines) + "\n", encoding="utf-8-sig")
        return out_ass_path

    @staticmethod
    def _render_karaoke_chunks(
        ev: TimedSubtitleEvent, smart_keyword_highlight: bool = True
    ) -> List[str]:
        """Split long sentences into snappy 6-word CapCut chunks with `{\\kf}` highlight tags."""
        lines_out: List[str] = []
        words = ev.words
        global_hl = (
            _pick_highlight_token_indices([w.word for w in words], max_picks=2)
            if smart_keyword_highlight
            else set()
        )
        for idx in range(0, len(words), MAX_WORDS_PER_KARAOKE_CHUNK):
            chunk = words[idx : idx + MAX_WORDS_PER_KARAOKE_CHUNK]
            if not chunk:
                continue
            c_start = ev.start_ms + chunk[0].start_ms
            c_end = min(ev.end_ms, ev.start_ms + chunk[-1].end_ms + 80)
            if c_end <= c_start:
                c_end = c_start + 300

            parts: List[str] = []
            for local_i, w in enumerate(chunk):
                dur_cs = max(5, (w.end_ms - w.start_ms) // 10)
                esc_w = _escape_ass_text(w.word)
                if (idx + local_i) in global_hl:
                    # Subtle electric-cyan keyword accent on punch words inside Karaoke mode
                    parts.append(
                        f"{{\\1c&H00FFFF38&\\kf{dur_cs}}}{esc_w}{{\\1c&H0000EAFF&}}"
                    )
                else:
                    parts.append(f"{{\\kf{dur_cs}}}{esc_w}")
            lines_out.append(
                f"Dialogue: 0,{_fmt_ass_time(c_start)},{_fmt_ass_time(c_end)},"
                f"StudioSub,,0,0,0,,{' '.join(parts)}"
            )
        return lines_out

