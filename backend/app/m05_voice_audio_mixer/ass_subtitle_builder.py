"""ASS (Advanced SubStation Alpha) 1080x1920 Karaoke & Cinema subtitle generator."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.m00_core_contracts import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    SubtitleStyle,
    WordTimestampDTO,
)

MAX_WORDS_PER_KARAOKE_CHUNK = 6


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


class ASSSubtitleBuilder:
    """Generates styled `.ass` files for vertical 1080x1920 Shorts/TikTok rendering."""

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
                dialogue_lines.extend(cls._render_karaoke_chunks(ev))
            else:
                safe_txt = _escape_ass_text(ev.text)
                if safe_txt:
                    dialogue_lines.append(
                        f"Dialogue: 0,{_fmt_ass_time(ev.start_ms)},{_fmt_ass_time(ev.end_ms)},"
                        f"StudioSub,,0,0,0,,{safe_txt}"
                    )

        out_ass_path.write_text(header + "\n".join(dialogue_lines) + "\n", encoding="utf-8-sig")
        return out_ass_path

    @staticmethod
    def _render_karaoke_chunks(ev: TimedSubtitleEvent) -> List[str]:
        """Split long sentences into snappy 6-word CapCut chunks with `{\\kf}` highlight tags."""
        lines_out: List[str] = []
        words = ev.words
        for idx in range(0, len(words), MAX_WORDS_PER_KARAOKE_CHUNK):
            chunk = words[idx : idx + MAX_WORDS_PER_KARAOKE_CHUNK]
            if not chunk:
                continue
            c_start = ev.start_ms + chunk[0].start_ms
            c_end = min(ev.end_ms, ev.start_ms + chunk[-1].end_ms + 80)
            if c_end <= c_start:
                c_end = c_start + 300

            parts: List[str] = []
            for w in chunk:
                dur_cs = max(5, (w.end_ms - w.start_ms) // 10)
                parts.append(f"{{\\kf{dur_cs}}}{_escape_ass_text(w.word)}")
            lines_out.append(
                f"Dialogue: 0,{_fmt_ass_time(c_start)},{_fmt_ass_time(c_end)},"
                f"StudioSub,,0,0,0,,{' '.join(parts)}"
            )
        return lines_out

