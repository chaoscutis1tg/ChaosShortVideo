"""GPU-accelerated Faster-Whisper transcriber with automatic CUDA DLL registration & CPU fallback."""

import asyncio
from typing import List, Optional, Tuple

from app.m00_core_contracts import (
    GPUResourceManager,
    ITranscriber,
    MediaAssetDTO,
    ProgressCallback,
    RawTranscriptSegmentDTO,
    TranscriptionError,
    TranscriptResultDTO,
    WordTimestampDTO,
)

from .srt_parser import SRTSubtitleParser, interpolate_words

WHISPER_HALLUCINATION_PATTERNS = (
    "ghiền mì gõ",
    "la la school",
    "amara.org",
    "hãy subscribe cho kênh",
    "đăng ký kênh để không bỏ lỡ",
    "cảm ơn các bạn đã theo dõi",
    "subtitles by",
)


def _is_whisper_hallucination(text: str) -> bool:
    low = text.lower().strip()
    return any(pat in low for pat in WHISPER_HALLUCINATION_PATTERNS)


class FasterWhisperTranscriber(ITranscriber):
    """Transcribes speech using Faster-Whisper on RTX 3060 CUDA (with full lazy-iteration
    fallback to CPU int8 if CUDA/cuBLAS DLLs fail) and handles music/instrumental clips safely.
    """

    def __init__(
        self,
        model_size: str = "medium",
        compute_type: str = "float16",
        gpu_manager: Optional[GPUResourceManager] = None,
    ) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self._gpu_manager = gpu_manager or GPUResourceManager()

    async def transcribe(
        self,
        media: MediaAssetDTO,
        lang_hint: str = "auto",
        on_progress: Optional[ProgressCallback] = None,
    ) -> TranscriptResultDTO:
        """Use external SRT if attached; otherwise run Faster-Whisper with CUDA->CPU resilience."""
        if media.external_srt_path is not None and media.external_srt_path.exists():
            if on_progress:
                on_progress("TRANSCRIBING_GPU", 100.0, "Đã đọc trực tiếp tệp phụ đề .srt đi kèm.")
            return await asyncio.to_thread(
                SRTSubtitleParser.parse, media.external_srt_path, media.media_id, lang_hint
            )

        if not media.audio_16k_wav_path.exists():
            raise TranscriptionError(
                f"Không tìm thấy tệp âm thanh 16kHz WAV: {media.audio_16k_wav_path}"
            )

        return await asyncio.to_thread(self._run_whisper_sync, media, lang_hint, on_progress)

    def _run_whisper_sync(
        self,
        media: MediaAssetDTO,
        lang_hint: str,
        on_progress: Optional[ProgressCallback],
    ) -> TranscriptResultDTO:
        self._gpu_manager.register_nvidia_cuda_dlls()
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise TranscriptionError("Chưa cài đặt thư viện faster-whisper.") from exc

        model_holder = {"model": None}

        def _release_model() -> None:
            model_holder["model"] = None

        attempts: List[Tuple[str, int, str, str, str]] = []
        target_dev, target_idx, target_lbl = self._gpu_manager.resolve_whisper_target()
        if target_dev == "cuda":
            attempts.append(("cuda", target_idx, self.compute_type, self.model_size, target_lbl))
        attempts.append(("cpu", 0, "int8", self.model_size, "CPU int8 ổn định"))

        last_err: Optional[Exception] = None
        segments: List[RawTranscriptSegmentDTO] = []
        detected_lang = "vi"

        with self._gpu_manager.acquire_vram("faster-whisper", cleanup_fn=_release_model):
            for idx, (device, dev_index, comp_type, m_size, mode_lbl) in enumerate(attempts):
                try:
                    if on_progress:
                        on_progress(
                            "TRANSCRIBING_GPU",
                            10.0,
                            f"Đang nạp mô hình Faster-Whisper ({m_size} trên {mode_lbl})...",
                        )
                    model_holder["model"] = WhisperModel(
                        m_size,
                        device=device,
                        device_index=dev_index,
                        compute_type=comp_type,
                    )
                    segments, detected_lang = self._decode_segments(
                        model=model_holder["model"],
                        media=media,
                        lang_hint=lang_hint,
                        device_label=device.upper(),
                        on_progress=on_progress,
                    )
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    model_holder["model"] = None
                    self._gpu_manager.flush_cuda_cache()
                    if idx + 1 < len(attempts) and on_progress:
                        on_progress(
                            "TRANSCRIBING_GPU",
                            12.0,
                            f"Chuyển tự động từ GPU sang CPU int8 ({exc})...",
                        )

        if last_err is not None:
            raise TranscriptionError(f"Lỗi nhận diện giọng nói Faster-Whisper: {last_err}")

        # Graceful fallback if the entire video is pure music / non-speech audio
        if not segments:
            segments = self._build_instrumental_fallback_segments(media.duration_ms)

        if on_progress:
            on_progress("TRANSCRIBING_GPU", 100.0, "Hoàn tất tách thoại & giải phóng VRAM.")

        return TranscriptResultDTO(
            media_id=media.media_id,
            detected_language=detected_lang,
            segments=segments,
        )

    @classmethod
    def _decode_segments(
        cls,
        model: object,
        media: MediaAssetDTO,
        lang_hint: str,
        device_label: str,
        on_progress: Optional[ProgressCallback],
    ) -> Tuple[List[RawTranscriptSegmentDTO], str]:
        language_arg = None if (not lang_hint or lang_hint.lower() == "auto") else lang_hint
        total_sec = max(media.duration_ms / 1000.0, 1.0)

        # Pass 1: VAD enabled; Pass 2 (if empty or sparse on >45s music/drama): VAD disabled
        min_expected_segs = 2 if media.duration_ms > 45000 else 1
        best_segments: List[RawTranscriptSegmentDTO] = []
        detected_lang = language_arg or "vi"

        for use_vad in (True, False):
            seg_iter, info = model.transcribe(  # type: ignore[attr-defined]
                str(media.audio_16k_wav_path),
                language=language_arg,
                vad_filter=use_vad,
                vad_parameters={"min_silence_duration_ms": 350} if use_vad else None,
                condition_on_previous_text=False,
                no_speech_threshold=0.65,
                word_timestamps=True,
            )
            segments: List[RawTranscriptSegmentDTO] = []
            for seg in seg_iter:
                text = (seg.text or "").strip()
                if not text or _is_whisper_hallucination(text):
                    continue
                s_ms = max(0, min(media.duration_ms - 150, int(round(seg.start * 1000.0))))
                e_ms = max(s_ms + 120, min(media.duration_ms, int(round(seg.end * 1000.0))))

                words: List[WordTimestampDTO] = []
                if getattr(seg, "words", None):
                    for w in seg.words:
                        w_txt = (w.word or "").strip()
                        if not w_txt:
                            continue
                        ws = max(s_ms, min(e_ms - 10, int(round(w.start * 1000.0))))
                        we = max(ws + 10, min(e_ms, int(round(w.end * 1000.0))))
                        words.append(WordTimestampDTO(word=w_txt, start_ms=ws, end_ms=we))
                if not words:
                    words = interpolate_words(text, s_ms, e_ms)

                segments.append(
                    RawTranscriptSegmentDTO(
                        seq_index=len(segments),
                        start_ms=s_ms,
                        end_ms=e_ms,
                        raw_text=text,
                        words=words,
                    )
                )
                if on_progress:
                    pct = min(98.0, 15.0 + (seg.end / total_sec) * 80.0)
                    on_progress(
                        "TRANSCRIBING_GPU",
                        round(pct, 1),
                        f"[{device_label}] Đã tách thoại tới mốc {int(seg.end)}s / {int(total_sec)}s...",
                    )

            detected_lang = getattr(info, "language", None) or language_arg or "vi"
            if len(segments) > len(best_segments):
                best_segments = segments
            if len(best_segments) >= min_expected_segs:
                return best_segments, detected_lang

        return best_segments, detected_lang

    @staticmethod
    def _build_instrumental_fallback_segments(duration_ms: int) -> List[RawTranscriptSegmentDTO]:
        """Ensure pure music/non-vocal videos still split cleanly without crashing M03."""
        step_ms = 20000
        out: List[RawTranscriptSegmentDTO] = []
        cur = 0
        idx = 0
        while cur < duration_ms:
            nxt = min(duration_ms, cur + step_ms)
            if nxt - cur < 500:
                break
            txt = f"Khoảnh khắc ấn tượng phần {idx + 1}."
            out.append(
                RawTranscriptSegmentDTO(
                    seq_index=idx,
                    start_ms=cur,
                    end_ms=nxt,
                    raw_text=txt,
                    words=interpolate_words(txt, cur, nxt),
                )
            )
            cur = nxt
            idx += 1
        return out
