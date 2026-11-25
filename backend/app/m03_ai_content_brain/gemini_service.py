"""Gemini Content Brain implementing `ILLMService` (Zero cross-module imports)."""

import asyncio
import json
import re
from typing import Any, Dict, List

from app.m00_core_contracts import (
    AIContentBrainError,
    ClipSpecDTO,
    CutConfigDTO,
    CutPlanDTO,
    ILLMService,
    LLMQuotaExceededError,
    MAX_NARRATION_CPS,
    NarrationLineDTO,
    ProductReviewPromptDTO,
    ProjectMode,
    RawTranscriptSegmentDTO,
    SEOPackageDTO,
    TopicPromptDTO,
    TranscriptResultDTO,
    WordTimestampDTO,
)

from .free_translator import FreeVietnameseTranslator
from .product_script_builder import ProductSalesScriptBuilder
from .smart_cutter import SmartEpisodeCutter, TranslatedSegmentItem

TRANSLATION_BATCH_SIZE = 60
MAX_LLM_RETRIES = 3
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _distribute_words(text: str, start_ms: int, end_ms: int) -> List[WordTimestampDTO]:
    tokens = [tok for tok in text.split() if tok]
    if not tokens:
        return []
    span = max(end_ms - start_ms, len(tokens))
    total_chars = max(sum(len(t) for t in tokens), 1)
    out: List[WordTimestampDTO] = []
    cur = start_ms
    for idx, tok in enumerate(tokens):
        w_end = end_ms if idx == len(tokens) - 1 else min(
            end_ms, max(cur + 1, cur + int(round(span * len(tok) / total_chars)))
        )
        out.append(WordTimestampDTO(word=tok, start_ms=cur, end_ms=w_end))
        cur = min(w_end, end_ms)
    return out


def _extract_json(raw: str) -> Any:
    cleaned = raw.strip()
    m = JSON_FENCE_RE.search(cleaned)
    if m:
        cleaned = m.group(1).strip()
    return json.loads(cleaned)


class GeminiContentBrainService(ILLMService):
    """Gemini-powered scriptwriter, context-aware drama translator, smart cutter & SEO generator."""

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-3-flash-preview",
        allow_offline_fallback: bool = True,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.allow_offline_fallback = allow_offline_fallback

    async def _call_gemini_json(self, prompt: str) -> Any:
        """Invoke Gemini API across resilient model chain and parse JSON output."""
        if not self.api_key:
            raise AIContentBrainError("Chưa cấu hình khóa GEMINI_API_KEY trong tệp .env.")

        eff_primary = (
            "gemini-3-flash-preview"
            if not self.model_name or "gemini-2.5" in self.model_name
            else self.model_name
        )
        candidate_models = list(
            dict.fromkeys(
                [
                    eff_primary,
                    "gemini-3-flash-preview",
                    "gemini-3.1-flash-lite",
                    "gemini-flash-latest",
                ]
            )
        )

        def _invoke_with_model(m_name: str) -> str:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore

            client = genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=m_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.55,
                    response_mime_type="application/json",
                ),
            )
            return resp.text or "{}"

        last_err: Exception | None = None
        for m_name in candidate_models:
            try:
                raw_text = await asyncio.to_thread(_invoke_with_model, m_name)
                return _extract_json(raw_text)
            except Exception as exc:
                last_err = exc
                continue

        raise AIContentBrainError(f"Gọi Gemini API thất bại: {last_err}")

    async def build_topic_clips(self, req: TopicPromptDTO) -> CutPlanDTO:
        """Generate multi-scene Topic-to-Video CutPlanDTO (Hook 3s + Body + CTA)."""
        if self.api_key:
            try:
                return await self._build_topic_via_gemini(req)
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        return self._build_topic_offline_fallback(req)

    async def build_product_review_clips(
        self, req: ProductReviewPromptDTO, demo_duration_ms: int = 0
    ) -> CutPlanDTO:
        """Analyze uploaded product photos & specs to generate persuasive sales CutPlanDTO."""
        return await ProductSalesScriptBuilder.build(
            req=req,
            demo_duration_ms=demo_duration_ms,
            api_key=self.api_key,
            model_name=self.model_name,
            allow_fallback=self.allow_offline_fallback,
        )

    async def _build_topic_via_gemini(self, req: TopicPromptDTO) -> CutPlanDTO:
        scenes_per_part = max(5, round(req.target_duration_sec / 8))
        prompt = (
            "Bạn là biên kịch video ngắn triệu view trên YouTube Shorts và TikTok.\n"
            f"Chủ đề: {req.topic_title}\n"
            f"Ý chính / Ghi chú: {req.key_points or 'Tự triển khai hấp dẫn, giàu kịch tính'}\n"
            f"Phong cách: {req.narrative_tone}\n"
            f"Số tập cần chia: {req.part_count} (mỗi tập dài khoảng {req.target_duration_sec} giây, "
            f"gồm khoảng {scenes_per_part} phân cảnh).\n"
            "Trả về JSON theo đúng cấu trúc:\n"
            '{"parts": [{"part_number": 1, "hook_banner_title": "...", "scenes": ['
            '{"duration_sec": 7, "vi_text": "Câu đọc thuyết minh tiếng Việt cuốn hút...", '
            '"image_prompt": "Detailed cinematic vertical 9:16 illustration prompt in English...", '
            '"stock_keywords": ["keyword1", "keyword2"]}]}]}'
        )
        data = await self._call_gemini_json(prompt)
        parts_raw = data.get("parts") or []
        if not parts_raw:
            raise AIContentBrainError("Gemini không trả về danh sách phân cảnh hợp lệ.")

        clips: List[ClipSpecDTO] = []
        for idx, p_obj in enumerate(parts_raw, start=1):
            part_num = int(p_obj.get("part_number") or idx)
            banner = str(p_obj.get("hook_banner_title") or f"{req.topic_title} | Phần {part_num}")
            scenes = p_obj.get("scenes") or []
            lines: List[NarrationLineDTO] = []
            cursor_ms = 0
            for s_idx, sc in enumerate(scenes):
                dur_ms = max(3000, int(round(float(sc.get("duration_sec") or 7.0) * 1000)))
                vi_txt = str(sc.get("vi_text") or "").strip()
                if not vi_txt:
                    continue
                img_p = str(sc.get("image_prompt") or f"cinematic vertical 9:16 {req.topic_title}")
                kws = [str(k) for k in (sc.get("stock_keywords") or [req.topic_title])][:4]
                end_ms = cursor_ms + dur_ms
                lines.append(
                    NarrationLineDTO(
                        seq_index=len(lines),
                        rel_start_ms=cursor_ms,
                        rel_end_ms=end_ms,
                        vi_text=vi_txt,
                        image_prompt=img_p,
                        stock_keywords=kws,
                        words=_distribute_words(vi_txt, cursor_ms, end_ms),
                    )
                )
                cursor_ms = end_ms

            if lines:
                clips.append(
                    ClipSpecDTO(
                        clip_id=f"{req.project_id}_part_{part_num:02d}",
                        project_id=req.project_id,
                        part_number=part_num,
                        source_start_ms=0,
                        source_end_ms=cursor_ms,
                        hook_banner_title=banner,
                        highlight_score=90.0,
                        lines=lines,
                        append_cta_outro=(req.part_count > 1),
                    )
                )

        if not clips:
            raise AIContentBrainError("Không tạo được phân cảnh hợp lệ nào từ kịch bản AI.")
        return CutPlanDTO(project_id=req.project_id, mode=ProjectMode.TOPIC_VIDEO, clips=clips)

    @staticmethod
    def _build_topic_offline_fallback(req: TopicPromptDTO) -> CutPlanDTO:
        """Deterministic offline script builder used when GEMINI_API_KEY is absent."""
        bullet_lines = [
            b.strip(" -•\t")
            for b in (req.key_points or "").splitlines()
            if b.strip(" -•\t")
        ]
        if not bullet_lines:
            bullet_lines = [
                f"Sự thật bất ngờ ít ai biết xoay quanh chủ đề {req.topic_title}.",
                "Điểm mấu chốt đầu tiên khiến nhiều người hoàn toàn hiểu lầm trước đây.",
                "Tình tiết bước ngoặt mở ra góc nhìn hoàn toàn mới đầy kịch tính.",
                "Bài học đắt giá và cái kết khiến người xem phải suy ngẫm.",
            ]

        clips: List[ClipSpecDTO] = []
        for part_num in range(1, req.part_count + 1):
            all_sentences = [
                f"Bạn có bao giờ tự hỏi sự thật đằng sau {req.topic_title} là gì không?",
                *bullet_lines,
                (
                    f"Hãy bấm theo dõi kênh để xem tiếp Phần {part_num + 1} ngay nhé!"
                    if part_num < req.part_count
                    else "Đừng quên thả tim và để lại ý kiến của bạn dưới phần bình luận nhé!"
                ),
            ]
            total_ms = req.target_duration_sec * 1000
            step_ms = max(4000, total_ms // len(all_sentences))
            lines: List[NarrationLineDTO] = []
            cur = 0
            for s_idx, sentence in enumerate(all_sentences):
                nxt = cur + step_ms if s_idx < len(all_sentences) - 1 else max(total_ms, cur + 4000)
                lines.append(
                    NarrationLineDTO(
                        seq_index=s_idx,
                        rel_start_ms=cur,
                        rel_end_ms=nxt,
                        vi_text=sentence,
                        image_prompt=f"cinematic dramatic vertical 9:16 scene about {req.topic_title}, scene {s_idx + 1}",
                        stock_keywords=[req.topic_title, "cinematic"],
                        words=_distribute_words(sentence, cur, nxt),
                    )
                )
                cur = nxt

            banner = (
                f"{req.topic_title} | Phần {part_num}"
                if req.part_count > 1
                else req.topic_title
            )
            clips.append(
                ClipSpecDTO(
                    clip_id=f"{req.project_id}_part_{part_num:02d}",
                    project_id=req.project_id,
                    part_number=part_num,
                    source_start_ms=0,
                    source_end_ms=cur,
                    hook_banner_title=banner,
                    highlight_score=85.0,
                    lines=lines,
                    append_cta_outro=(part_num < req.part_count),
                )
            )
        return CutPlanDTO(project_id=req.project_id, mode=ProjectMode.TOPIC_VIDEO, clips=clips)

    async def translate_and_split_movie(
        self,
        transcript: TranscriptResultDTO,
        config: CutConfigDTO,
        project_id: str,
        total_duration_ms: int,
    ) -> CutPlanDTO:
        """Translate foreign movie dialogue in context and split into 65-120s parts/highlights."""
        if not transcript.segments:
            raise AIContentBrainError("Tập phim không có dữ liệu lời thoại để dịch hoặc chia tập.")

        is_vietnamese = transcript.detected_language.lower().startswith("vi")
        if is_vietnamese:
            translated_items = [
                TranslatedSegmentItem(
                    seq_index=seg.seq_index,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    original_text=seg.raw_text,
                    vi_text=self._enforce_concise_cps(seg.raw_text, seg.end_ms - seg.start_ms),
                    dramatic_weight=self._heuristic_drama_score(seg.raw_text),
                )
                for seg in transcript.segments
            ]
        elif self.api_key:
            translated_items = await self._translate_batches_with_gemini(
                transcript.segments, config.drama_genre, transcript.detected_language
            )
        else:
            # Free zero-API-key automatic Vietnamese translation for foreign videos!
            vi_lines = await FreeVietnameseTranslator.translate_lines(
                [seg.raw_text for seg in transcript.segments],
                source_lang=transcript.detected_language,
            )
            translated_items = [
                TranslatedSegmentItem(
                    seq_index=seg.seq_index,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                    original_text=seg.raw_text,
                    vi_text=self._enforce_concise_cps(
                        vi_txt or seg.raw_text, seg.end_ms - seg.start_ms
                    ),
                    dramatic_weight=self._heuristic_drama_score(vi_txt or seg.raw_text),
                )
                for seg, vi_txt in zip(transcript.segments, vi_lines)
            ]

        clips = SmartEpisodeCutter.build_clips(
            project_id=project_id,
            items=translated_items,
            raw_segments=transcript.segments,
            config=config,
            total_duration_ms=total_duration_ms,
        )
        if not clips:
            raise AIContentBrainError("Không tạo được đoạn cắt hợp lệ từ tập phim.")

        return CutPlanDTO(project_id=project_id, mode=ProjectMode.MOVIE_CLIPPER, clips=clips)

    async def _translate_batches_with_gemini(
        self,
        segments: List[RawTranscriptSegmentDTO],
        drama_genre: str,
        source_lang: str = "auto",
    ) -> List[TranslatedSegmentItem]:
        results: List[TranslatedSegmentItem] = []
        for start_i in range(0, len(segments), TRANSLATION_BATCH_SIZE):
            batch = segments[start_i : start_i + TRANSLATION_BATCH_SIZE]
            payload_in = [
                {
                    "id": s.seq_index,
                    "dur_sec": round((s.end_ms - s.start_ms) / 1000.0, 2),
                    "text": s.raw_text,
                }
                for s in batch
            ]
            prompt = (
                "Bạn là biên dịch viên thuyết minh phim bộ chuyên nghiệp.\n"
                f"Thể loại & ngữ cảnh xưng hô: {drama_genre} (giữ nhất quán đại từ nhân xưng "
                "như tổng tài, phu nhân, hắn, cô ấy, đại ca...).\n"
                "Hãy dịch ngắn gọn, gãy gọn chuẩn câu nói thuyết minh để đọc vừa khít thời lượng `dur_sec` "
                "(tối đa 18-20 ký tự trên mỗi giây), kèm chấm điểm kịch tính `score` (0-100).\n"
                f"Dữ liệu đầu vào JSON:\n{json.dumps(payload_in, ensure_ascii=False)}\n"
                'Trả về JSON: {"items": [{"id": 0, "vi": "...", "score": 75}]}'
            )
            try:
                resp = await self._call_gemini_json(prompt)
                mapped: Dict[int, Dict[str, Any]] = {
                    int(it["id"]): it for it in (resp.get("items") or []) if "id" in it
                }
            except Exception:
                if not self.allow_offline_fallback:
                    raise
                fallback_vi = await FreeVietnameseTranslator.translate_lines(
                    [s.raw_text for s in batch], source_lang=source_lang
                )
                mapped = {
                    s.seq_index: {"id": s.seq_index, "vi": v_txt, "score": 70}
                    for s, v_txt in zip(batch, fallback_vi)
                }

            for seg in batch:
                hit = mapped.get(seg.seq_index)
                raw_vi = str(hit.get("vi") if hit else seg.raw_text).strip() or seg.raw_text
                score = float(hit.get("score") if hit and "score" in hit else 65.0)
                results.append(
                    TranslatedSegmentItem(
                        seq_index=seg.seq_index,
                        start_ms=seg.start_ms,
                        end_ms=seg.end_ms,
                        original_text=seg.raw_text,
                        vi_text=self._enforce_concise_cps(raw_vi, seg.end_ms - seg.start_ms),
                        dramatic_weight=min(100.0, max(0.0, score)),
                    )
                )
        return results

    @staticmethod
    def _enforce_concise_cps(text: str, slot_ms: int) -> str:
        """Trim overly verbose trailing filler if characters-per-second vastly exceeds limit."""
        slot_sec = max(slot_ms / 1000.0, 0.8)
        max_chars = int(slot_sec * MAX_NARRATION_CPS * 1.35)
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_chars:
            return cleaned
        words = cleaned.split()
        trimmed: List[str] = []
        count = 0
        for w in words:
            if count + len(w) + 1 > max_chars and len(trimmed) >= 3:
                break
            trimmed.append(w)
            count += len(w) + 1
        return " ".join(trimmed)

    @staticmethod
    def _heuristic_drama_score(text: str) -> float:
        score = 55.0
        if any(ch in text for ch in ("!", "?", "…")):
            score += 20.0
        if len(text) > 25:
            score += 10.0
        return min(score, 98.0)

    async def build_seo(self, clip: ClipSpecDTO, mode_label: str = "") -> SEOPackageDTO:
        """Generate ready-to-copy YouTube Shorts & TikTok titles, descriptions, and hashtags."""
        preview_lines = " ".join(ln.vi_text for ln in clip.lines[:6])[:500]
        is_product = mode_label == ProjectMode.PRODUCT_SHOWCASE.value
        if self.api_key:
            prompt = (
                (
                    "Sinh gói nội dung bán hàng chốt đơn trên YouTube Shorts và TikTok Shop chuẩn SEO:\n"
                    f"Sản phẩm: {clip.hook_banner_title}\n"
                    f"Điểm nổi bật & ưu đãi: {preview_lines}\n"
                    "Trả về JSON:\n"
                    '{"yt_shorts_title": "<= 70 ký tự nêu bật sản phẩm + #Shorts", '
                    '"yt_shorts_description": "Mô tả chi tiết ưu điểm + phụ kiện tặng kèm + kêu gọi nhắn tin", '
                    '"yt_shorts_tags": ["shorts", "reviewsanpham", "xuhuong"], '
                    '"tiktok_caption": "Caption bán hàng cuốn hút kích thích khách hỏi giá / để lại bình luận...", '
                    '"tiktok_hashtags": ["#reviewsanpham", "#xuhuong", "#tiktokshop", "#fyp"], '
                    '"pinned_comment": "Câu bình luận ghim đầu tiên dưới video của chủ shop để chốt đơn khéo léo"}'
                )
                if is_product
                else (
                    "Sinh gói nội dung đăng YouTube Shorts và TikTok chuẩn SEO từ đoạn video sau:\n"
                    f"Tiêu đề phần: {clip.hook_banner_title} (Phần {clip.part_number})\n"
                    f"Nội dung chính: {preview_lines}\n"
                    "Trả về JSON:\n"
                    '{"yt_shorts_title": "<= 70 ký tự có #Shorts", '
                    '"yt_shorts_description": "Mô tả cuốn hút + nhắc xem Phần tiếp theo", '
                    '"yt_shorts_tags": ["shorts", "phimngan", "xuhuong"], '
                    '"tiktok_caption": "Caption kích thích bình luận...", '
                    '"tiktok_hashtags": ["#xuhuong", "#phimhay", "#reviewphim", "#fyp"]}'
                )
            )
            try:
                data = await self._call_gemini_json(prompt)
                return SEOPackageDTO(
                    clip_id=clip.clip_id,
                    part_number=clip.part_number,
                    yt_shorts_title=str(data.get("yt_shorts_title") or clip.hook_banner_title)[:95],
                    yt_shorts_description=str(
                        data.get("yt_shorts_description")
                        or f"{clip.hook_banner_title} - Nhắn tin ngay để nhận tư vấn chi tiết!"
                    ),
                    yt_shorts_tags=[str(t) for t in (data.get("yt_shorts_tags") or ["shorts"])][:10],
                    tiktok_caption=str(data.get("tiktok_caption") or clip.hook_banner_title),
                    tiktok_hashtags=[
                        str(h) if str(h).startswith("#") else f"#{h}"
                        for h in (data.get("tiktok_hashtags") or ["#xuhuong", "#fyp"])
                    ][:10],
                    pinned_comment=str(data.get("pinned_comment") or ""),
                )
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        if is_product:
            short_title = f"{clip.hook_banner_title[:78]} #Shorts"
            sales_cta = "Nhắn trực tiếp cho shop hoặc để lại bình luận để nhận tư vấn chi tiết & video test thực tế!"
            pinned = (
                f"📌 Các bạn cần tư vấn chi tiết về {clip.hook_banner_title} hoặc muốn xem thêm video quay cận thực tế "
                "thì để lại chấm (.) dưới bình luận hoặc nhắn vào hộp thư kênh để mình hỗ trợ ngay nhé!"
            )
            return SEOPackageDTO(
                clip_id=clip.clip_id,
                part_number=clip.part_number,
                yt_shorts_title=short_title,
                yt_shorts_description=f"{clip.hook_banner_title}\n{preview_lines[:220]}...\n👉 {sales_cta}",
                yt_shorts_tags=["shorts", "reviewsanpham", "xuhuong", "chinhhang", "uudai"],
                tiktok_caption=f"✨ {clip.hook_banner_title} — Độ hoàn thiện thực tế vượt mong đợi! 👉 {sales_cta}",
                tiktok_hashtags=["#reviewsanpham", "#tiktokshop", "#xuhuong", "#viral", "#fyp"],
                pinned_comment=pinned,
            )

        next_cta = (
            f"Vào kênh xem ngay Phần {clip.part_number + 1} nhé!"
            if clip.append_cta_outro
            else "Follow kênh để đón xem video mới mỗi ngày!"
        )
        short_title = f"{clip.hook_banner_title[:78]} #Shorts"
        return SEOPackageDTO(
            clip_id=clip.clip_id,
            part_number=clip.part_number,
            yt_shorts_title=short_title,
            yt_shorts_description=f"{clip.hook_banner_title}\n{preview_lines[:160]}...\n{next_cta}",
            yt_shorts_tags=["shorts", "xuhuong", "phimngan", "thuyetminh", "viral"],
            tiktok_caption=f"{clip.hook_banner_title} — Không ngờ tình tiết lại căng thẳng thế này! {next_cta}",
            tiktok_hashtags=["#xuhuong", "#phimngan", "#thuyetminhphim", "#viral", "#fyp"],
        )

