"""SRT/VTT external subtitle parser and language detector for Module M02."""

from pathlib import Path
import re
from typing import List

from app.m00_core_contracts import (
    RawTranscriptSegmentDTO,
    TranscriptionError,
    TranscriptResultDTO,
    WordTimestampDTO,
)

SRT_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
)
HTML_TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]+\}")

VIETNAMESE_CHARS_RE = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
CJK_CHARS_RE = re.compile(r"[\u4e00-\u9fff]")
HANGUL_CHARS_RE = re.compile(r"[\uac00-\ud7af]")
KANA_CHARS_RE = re.compile(r"[\u3040-\u30ff]")


def _to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 3600) + (int(m) * 60) + int(s)) * 1000 + int(ms)


def detect_text_language(text: str) -> str:
    """Heuristically identify ISO language code from subtitle text."""
    if VIETNAMESE_CHARS_RE.search(text):
        return "vi"
    if CJK_CHARS_RE.search(text):
        return "zh"
    if HANGUL_CHARS_RE.search(text):
        return "ko"
    if KANA_CHARS_RE.search(text):
        return "ja"
    return "en"


def interpolate_words(text: str, start_ms: int, end_ms: int) -> List[WordTimestampDTO]:
    """Distribute word-level timestamps proportionally across segment duration."""
    tokens = [tok for tok in text.split() if tok]
    if not tokens:
        return []
    total_dur = max(end_ms - start_ms, len(tokens))
    total_chars = max(sum(len(t) for t in tokens), 1)

    words: List[WordTimestampDTO] = []
    cursor = start_ms
    for idx, tok in enumerate(tokens):
        if idx == len(tokens) - 1:
            w_end = end_ms
        else:
            share = int(round(total_dur * (len(tok) / total_chars)))
            w_end = min(end_ms, max(cursor + 1, cursor + share))
        words.append(WordTimestampDTO(word=tok, start_ms=cursor, end_ms=w_end))
        cursor = min(w_end, end_ms)
    return words


class SRTSubtitleParser:
    """Parses external `.srt` or `.vtt` files into standardized `TranscriptResultDTO`."""

    @staticmethod
    def parse(srt_path: Path, media_id: str, lang_hint: str = "auto") -> TranscriptResultDTO:
        """Read subtitle file with UTF-8/CP1258 fallback and convert to TranscriptResultDTO."""
        if not srt_path.exists():
            raise TranscriptionError(f"Tệp phụ đề không tồn tại: {srt_path}")

        raw_content = ""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "utf-16"):
            try:
                raw_content = srt_path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if not raw_content.strip():
            raise TranscriptionError(f"Tệp phụ đề rỗng hoặc không đọc được mã hóa: {srt_path.name}")

        blocks = re.split(r"\r?\n\r?\n+", raw_content.strip())
        segments: List[RawTranscriptSegmentDTO] = []
        combined_text_parts: List[str] = []

        for blk in blocks:
            lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
            if not lines:
                continue
            time_idx = next((i for i, ln in enumerate(lines) if SRT_TIME_RE.search(ln)), None)
            if time_idx is None:
                continue
            match = SRT_TIME_RE.search(lines[time_idx])
            if match is None:
                continue

            start_ms = _to_ms(*match.groups()[:4])
            end_ms = _to_ms(*match.groups()[4:])
            if end_ms <= start_ms:
                end_ms = start_ms + 500

            body = " ".join(lines[time_idx + 1 :])
            clean_text = HTML_TAG_RE.sub("", body).strip()
            if not clean_text:
                continue

            seq_idx = len(segments)
            segments.append(
                RawTranscriptSegmentDTO(
                    seq_index=seq_idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    raw_text=clean_text,
                    words=interpolate_words(clean_text, start_ms, end_ms),
                )
            )
            combined_text_parts.append(clean_text)

        if not segments:
            raise TranscriptionError(f"Không tìm thấy dòng phụ đề hợp lệ trong '{srt_path.name}'.")

        detected = (
            lang_hint
            if lang_hint and lang_hint.lower() != "auto"
            else detect_text_language(" ".join(combined_text_parts[:30]))
        )
        return TranscriptResultDTO(
            media_id=media_id,
            detected_language=detected,
            segments=segments,
        )

