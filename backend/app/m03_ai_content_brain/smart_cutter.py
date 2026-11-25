"""Smart episode splitter (65-120s sentence/cliffhanger snapping) & highlight extractor."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.m00_core_contracts import (
    ClipSpecDTO,
    CutConfigDTO,
    CutStrategy,
    MAX_ALLOWED_CLIP_SEC,
    NarrationLineDTO,
    RawTranscriptSegmentDTO,
    SILENCE_GAP_SNAP_MS,
    WordTimestampDTO,
)

CLIFFHANGER_PUNCTUATION = ("?", "!", "…", "...")


@dataclass
class TranslatedSegmentItem:
    """Intermediate paired segment holding original timing and Vietnamese narration."""

    seq_index: int
    start_ms: int
    end_ms: int
    original_text: str
    vi_text: str
    dramatic_weight: float = 50.0


class SmartEpisodeCutter:
    """Splits full-episode transcripts into Part 1..N or top viral highlights without mid-sentence cuts."""

    @classmethod
    def build_clips(
        cls,
        project_id: str,
        items: List[TranslatedSegmentItem],
        raw_segments: List[RawTranscriptSegmentDTO],
        config: CutConfigDTO,
        total_duration_ms: int,
    ) -> List[ClipSpecDTO]:
        """Execute either SEQUENTIAL_PARTS or VIRAL_HIGHLIGHTS strategy."""
        if not items:
            return []
        if config.cut_strategy == CutStrategy.VIRAL_HIGHLIGHTS:
            return cls._extract_viral_highlights(
                project_id, items, raw_segments, config, total_duration_ms
            )
        return cls._split_sequential_parts(
            project_id, items, raw_segments, config, total_duration_ms
        )

    @classmethod
    def _split_sequential_parts(
        cls,
        project_id: str,
        items: List[TranslatedSegmentItem],
        raw_segments: List[RawTranscriptSegmentDTO],
        config: CutConfigDTO,
        total_duration_ms: int,
    ) -> List[ClipSpecDTO]:
        min_ms = config.min_clip_sec * 1000
        max_ms = config.max_clip_sec * 1000
        raw_by_idx: Dict[int, RawTranscriptSegmentDTO] = {s.seq_index: s for s in raw_segments}

        windows: List[tuple[int, int, List[TranslatedSegmentItem]]] = []
        n = len(items)
        idx = 0
        clip_start_ms = 0

        while idx < n:
            best_end_idx: Optional[int] = None
            best_score = -1.0
            fallback_idx = idx

            for j in range(idx, n):
                seg = items[j]
                elapsed = seg.end_ms - clip_start_ms
                if elapsed <= max_ms:
                    fallback_idx = j

                if min_ms <= elapsed <= max_ms:
                    gap_after = (
                        (items[j + 1].start_ms - seg.end_ms)
                        if (j + 1) < n
                        else (total_duration_ms - seg.end_ms)
                    )
                    score = 10.0
                    if gap_after >= SILENCE_GAP_SNAP_MS:
                        score += min(gap_after / 100.0, 25.0)
                    if seg.vi_text.strip().endswith(CLIFFHANGER_PUNCTUATION):
                        score += 20.0
                    score += seg.dramatic_weight * 0.2
                    if score > best_score:
                        best_score = score
                        best_end_idx = j
                elif elapsed > max_ms:
                    break

            chosen_end_idx = best_end_idx if best_end_idx is not None else fallback_idx
            chosen_slice = items[idx : chosen_end_idx + 1]

            if chosen_end_idx == n - 1:
                clip_end_ms = max(total_duration_ms, chosen_slice[-1].end_ms)
            else:
                next_start = items[chosen_end_idx + 1].start_ms
                gap = max(0, next_start - chosen_slice[-1].end_ms)
                clip_end_ms = chosen_slice[-1].end_ms + min(gap // 2, 300)

            windows.append((clip_start_ms, clip_end_ms, chosen_slice))
            clip_start_ms = clip_end_ms
            idx = chosen_end_idx + 1

        # Merge tiny trailing tail into previous part if within MAX_ALLOWED_CLIP_SEC
        if len(windows) >= 2:
            last_start, last_end, last_items = windows[-1]
            prev_start, _, prev_items = windows[-2]
            if (last_end - last_start) < (min_ms // 2) and (
                last_end - prev_start
            ) <= MAX_ALLOWED_CLIP_SEC * 1000:
                windows[-2] = (prev_start, last_end, prev_items + last_items)
                windows.pop()

        clips: List[ClipSpecDTO] = []
        for part_num, (w_start, w_end, w_items) in enumerate(windows, start=1):
            clips.append(
                cls._materialize_clip(
                    project_id=project_id,
                    part_number=part_num,
                    w_start=w_start,
                    w_end=w_end,
                    w_items=w_items,
                    raw_by_idx=raw_by_idx,
                    config=config,
                )
            )
        return clips

    @classmethod
    def _extract_viral_highlights(
        cls,
        project_id: str,
        items: List[TranslatedSegmentItem],
        raw_segments: List[RawTranscriptSegmentDTO],
        config: CutConfigDTO,
        total_duration_ms: int,
    ) -> List[ClipSpecDTO]:
        # First partition into clean candidate windows, then pick top-K by dramatic weight
        seq_cfg = config.model_copy(update={"cut_strategy": CutStrategy.SEQUENTIAL_PARTS})
        candidates = cls._split_sequential_parts(
            project_id, items, raw_segments, seq_cfg, total_duration_ms
        )
        ranked = sorted(candidates, key=lambda c: c.highlight_score, reverse=True)[
            : config.max_highlights
        ]
        # Re-order chronologically and re-number Part 1..K
        chronological = sorted(ranked, key=lambda c: c.source_start_ms)
        final_clips: List[ClipSpecDTO] = []
        for new_part, clip in enumerate(chronological, start=1):
            banner = f"{config.series_title} | Đoạn Đặc Sắc {new_part}"
            final_clips.append(
                clip.model_copy(
                    update={
                        "clip_id": f"{project_id}_hl_{new_part:02d}",
                        "part_number": new_part,
                        "hook_banner_title": banner,
                    }
                )
            )
        return final_clips

    @staticmethod
    def _materialize_clip(
        project_id: str,
        part_number: int,
        w_start: int,
        w_end: int,
        w_items: List[TranslatedSegmentItem],
        raw_by_idx: Dict[int, RawTranscriptSegmentDTO],
        config: CutConfigDTO,
    ) -> ClipSpecDTO:
        lines: List[NarrationLineDTO] = []
        weights: List[float] = []

        for local_i, item in enumerate(w_items):
            rel_s = max(0, item.start_ms - w_start)
            rel_e = max(rel_s + 150, min(w_end - w_start, item.end_ms - w_start))
            weights.append(item.dramatic_weight)

            raw_seg = raw_by_idx.get(item.seq_index)
            rel_words: List[WordTimestampDTO] = []
            if raw_seg and raw_seg.words:
                for w in raw_seg.words:
                    ws = max(rel_s, w.start_ms - w_start)
                    we = max(ws + 10, min(rel_e, w.end_ms - w_start))
                    rel_words.append(WordTimestampDTO(word=w.word, start_ms=ws, end_ms=we))

            lines.append(
                NarrationLineDTO(
                    seq_index=local_i,
                    rel_start_ms=rel_s,
                    rel_end_ms=rel_e,
                    original_text=item.original_text,
                    vi_text=item.vi_text,
                    words=rel_words,
                )
            )

        avg_score = round(sum(weights) / max(len(weights), 1), 1)
        banner = f"{config.series_title} | Phần {part_number}"
        return ClipSpecDTO(
            clip_id=f"{project_id}_part_{part_number:02d}",
            project_id=project_id,
            part_number=part_number,
            source_start_ms=w_start,
            source_end_ms=max(w_end, w_start + 1000),
            hook_banner_title=banner,
            highlight_score=min(100.0, max(0.0, avg_score)),
            lines=lines,
            append_cta_outro=config.append_cta_outro,
        )

