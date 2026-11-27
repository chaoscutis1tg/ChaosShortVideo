"""Gemini Content Brain implementing `ILLMService` (Zero cross-module imports)."""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from app.m00_core_contracts import (
    AIContentBrainError,
    BriefExpandRequestDTO,
    BriefExpandResultDTO,
    ClipSpecDTO,
    CopywritingTone,
    CutConfigDTO,
    CutPlanDTO,
    ILLMService,
    LLMQuotaExceededError,
    MAX_ALLOWED_CLIP_SEC,
    MAX_NARRATION_CPS,
    MIN_ALLOWED_CLIP_SEC,
    NarrationLineDTO,
    ProductCategory,
    ProductReviewPromptDTO,
    ProjectMode,
    RawTranscriptSegmentDTO,
    SalesScriptAngle,
    ScrapedThreadBundleDTO,
    SEOPackageDTO,
    ThreadCommentItemDTO,
    ThreadFilterVibe,
    ThreadsExtractRequestDTO,
    TopicPromptDTO,
    TranscriptResultDTO,
    VisualMode,
    WordTimestampDTO,
)

from .free_translator import FreeVietnameseTranslator
from .product_script_builder import ProductSalesScriptBuilder
from .smart_cutter import SmartEpisodeCutter, TranslatedSegmentItem
from .tiktok_compliance import TikTokShopComplianceChecker

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

    async def expand_short_brief(self, req: BriefExpandRequestDTO) -> BriefExpandResultDTO:
        """Analyze a short title + rough description via API Key and expand into a full video plan."""
        if self.api_key:
            try:
                return await self._expand_brief_via_gemini(req)
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        return self._expand_brief_offline_fallback(req)

    async def _expand_brief_via_gemini(self, req: BriefExpandRequestDTO) -> BriefExpandResultDTO:
        seed_title = req.raw_title.strip()
        seed_brief = req.short_brief.strip()

        if req.mode == ProjectMode.PRODUCT_SHOWCASE:
            prompt = (
                "Bạn là Giám đốc Sáng tạo Nội dung Thương mại & Chuyên gia Tư vấn Sản phẩm trên TikTok / YouTube Shorts.\n"
                "Từ tiêu đề ngắn và vài dòng ghi chú sơ lược của người dùng, hãy phân tích và triển khai thành bản thông tin "
                "chi tiết, giàu sức thuyết phục và cảm xúc thực tế để tạo video bán hàng tốt nhất.\n"
                "LƯU Ý CHÍNH SÁCH: Tuyệt đối KHÔNG dùng từ tuyệt đối hóa vi phạm chính sách TikTok Shop "
                "(như 'số 1', 'tốt nhất thế giới', 'cam kết 100%', 'rẻ nhất', 'chữa khỏi', 'chuyển khoản trước').\n\n"
                f"- Tên / Tiêu đề sơ bộ: {seed_title or '(Chưa đặt tên — hãy đặt tên chuẩn từ mô tả)'}\n"
                f"- Mô tả ngắn ban đầu: {seed_brief or '(Chỉ có tên sản phẩm — hãy triển khai chi tiết hợp lý)'}\n"
                f"- Nhóm ngành hàng: {req.product_category.value}\n"
                f"- Thời lượng mong muốn: ~{req.target_duration_sec} giây\n\n"
                "Danh sách mã giọng đọc hợp lệ (`recommended_voice_id`):\n"
                "- edge_nam_nghe_nhan: Nam trầm ấm chia sẻ nhạc cụ, đồ gỗ thủ công, đồng hồ, trà\n"
                "- edge_nu_boutique_silk: Nữ sang trọng mềm mại tư vấn thời trang thiết kế, mỹ phẩm, nhạc cụ\n"
                "- gemini_actor_aoede: Nữ ấm áp kể chuyện nghệ thuật & thủ công tinh tế\n"
                "- edge_nam_gia_bao_consult: Nam trẻ trung tư vấn thông số rõ ràng, phân biệt phiên bản\n"
                "- edge_nu_phuong_anh_lookbook: Nữ hiện đại tươi sáng review quần áo, phụ kiện\n\n"
                "Danh sách mã nhạc nền hợp lệ (`recommended_bgm_id`):\n"
                "- bgm_luxury_acoustic (Violin & Guitar ấm áp sang trọng)\n"
                "- bgm_upbeat_shop (Guitar rải hợp âm tươi sáng hiện đại)\n"
                "- bgm_lofi_story (Piano trầm lắng sâu sắc)\n\n"
                "Trả về JSON theo đúng cấu trúc:\n"
                "{\n"
                '  "refined_title": "Tiêu đề sản phẩm cuốn hút, sang trọng, rõ điểm đắt giá (<= 110 ký tự)",\n'
                '  "alternative_titles": ["Phương án tiêu đề 2", "Phương án tiêu đề 3", "Phương án tiêu đề 4"],\n'
                '  "hook_opening": "Câu mở đầu 3 giây đầu chạm đúng nhu cầu người xem",\n'
                '  "expanded_description": "- Điểm ấn tượng đầu tiên: ...\\n- Chất liệu & độ hoàn thiện thực tế: ...\\n- Trải nghiệm sử dụng / âm sắc thực tế: ...\\n- Phù hợp cho ai & giá trị lâu dài: ...\\n- Phụ kiện đi kèm & hỗ trợ trải nghiệm thực tế: ...",\n'
                '  "visual_direction": "Gợi ý thứ tự khung hình cận cảnh chi tiết, góc toàn cảnh và đoạn test thực tế",\n'
                '  "recommended_tone": "ARTISAN_STORYTELLER hoặc MODERN_CONSULTANT hoặc LUXURY_MINIMAL",\n'
                '  "recommended_sales_angle": "EXPERT_SPEC_REVIEW hoặc BEGINNER_CONSULT hoặc UNBOXING_AND_GIFT hoặc PRICE_COMPARISON_DEAL",\n'
                '  "recommended_cta": "Câu mời khách ghé trải nghiệm hoặc nhắn tin nhận clip test riêng lịch sự, tự nhiên",\n'
                '  "recommended_duration_sec": 55,\n'
                '  "recommended_voice_id": "edge_nam_nghe_nhan",\n'
                '  "recommended_bgm_id": "bgm_luxury_acoustic",\n'
                '  "analysis_summary": "Nhận định ngắn gọn 1-2 câu về điểm mạnh cốt lõi AI vừa khai thác cho sản phẩm"\n'
                "}"
            )
            data = await self._call_gemini_json(prompt)
            raw_desc = str(data.get("expanded_description") or seed_brief or seed_title).strip()
            raw_cta = str(
                data.get("recommended_cta")
                or "Nhắn trực tiếp cho cửa hàng hoặc để lại bình luận để nhận video test thực tế nhé."
            ).strip()
            clean_desc = TikTokShopComplianceChecker.check_and_sanitize(raw_desc).sanitized_text or raw_desc
            clean_cta = TikTokShopComplianceChecker.check_and_sanitize(raw_cta).sanitized_text or raw_cta

            tone_str = str(data.get("recommended_tone") or CopywritingTone.ARTISAN_STORYTELLER.value).strip()
            if tone_str not in {t.value for t in CopywritingTone}:
                tone_str = CopywritingTone.ARTISAN_STORYTELLER.value

            angle_raw = str(data.get("recommended_sales_angle") or SalesScriptAngle.EXPERT_SPEC_REVIEW.value).strip()
            angle_enum = (
                SalesScriptAngle(angle_raw)
                if angle_raw in {a.value for a in SalesScriptAngle}
                else SalesScriptAngle.EXPERT_SPEC_REVIEW
            )
            dur = int(data.get("recommended_duration_sec") or req.target_duration_sec or 55)
            dur = max(MIN_ALLOWED_CLIP_SEC, min(MAX_ALLOWED_CLIP_SEC, dur))
            ref_title = str(data.get("refined_title") or seed_title or "Giới thiệu sản phẩm nổi bật").strip()[:195]
            alt_titles = [
                str(x).strip()[:195]
                for x in (data.get("alternative_titles") or [])
                if str(x).strip() and str(x).strip() != ref_title
            ][:3]

            return BriefExpandResultDTO(
                refined_title=ref_title if len(ref_title) >= 3 else "Giới thiệu sản phẩm chi tiết",
                alternative_titles=alt_titles,
                hook_opening=str(data.get("hook_opening") or "").strip(),
                expanded_description=clean_desc,
                visual_direction=str(data.get("visual_direction") or "").strip(),
                recommended_tone=tone_str,
                recommended_sales_angle=angle_enum,
                recommended_cta=clean_cta,
                recommended_duration_sec=dur,
                recommended_part_count=1,
                recommended_voice_id=str(data.get("recommended_voice_id") or "edge_nam_nghe_nhan").strip(),
                recommended_bgm_id=str(data.get("recommended_bgm_id") or "bgm_luxury_acoustic").strip(),
                recommended_visual_mode=VisualMode.AI_IMAGE,
                used_api_key=True,
                analysis_summary=str(
                    data.get("analysis_summary")
                    or "Đã phân tích ý tưởng ngắn và mở rộng thành bản mô tả bán hàng chi tiết chuẩn chính sách."
                ).strip(),
            )

        # Mode 1: TOPIC_VIDEO deep story/knowledge expansion
        prompt = (
            "Bạn là Đạo diễn & Biên kịch trưởng Video Ngắn Triệu View trên YouTube Shorts và TikTok.\n"
            "Người dùng chỉ đưa vào một tiêu đề sơ bộ và/hoặc vài từ mô tả ngắn. Hãy phân tích sâu hạt giống ý tưởng đó "
            "và mở rộng thành một đề cương kịch bản chi tiết, chặt chẽ, giàu hình ảnh điện ảnh nhất để bước tiếp theo "
            "hệ thống dựng ra video có tỷ lệ giữ chân người xem cao nhất.\n\n"
            f"- Tiêu đề / Chủ đề sơ bộ của người dùng: {seed_title or '(Chưa có tiêu đề — hãy sáng tạo tiêu đề đắt giá nhất từ mô tả)'}\n"
            f"- Mô tả ngắn / Ý tưởng ban đầu: {seed_brief or '(Chỉ có chủ đề — hãy tự phát triển câu chuyện/kiến thức sâu sắc, cuốn hút nhất)'}\n"
            f"- Thời lượng dự kiến hiện tại: ~{req.target_duration_sec} giây ({req.part_count} tập)\n\n"
            "Danh sách mã giọng đọc hợp lệ (`recommended_voice_id` — chọn đúng 1 mã hợp nội dung nhất):\n"
            "- edge_bong_dem_horror: Nam trầm lạnh (Kinh dị, bí ẩn đêm khuya, tin nhắn lạ, giải mã vụ án)\n"
            "- edge_hoang_vu_action: Nam gay cấn dồn dập (Hành động, sinh tồn, kịch tính bất ngờ)\n"
            "- edge_nam_minh_movie: Nam trầm đĩnh đạc (Kể chuyện đời người, phim bộ, bài học cuộc sống)\n"
            "- gemini_yt_orus: Nam trầm uyên bác (Khoa học, vũ trụ, lịch sử, kiến thức chuyên sâu)\n"
            "- edge_van_minh_knowledge: Nam điềm đạm mạch lạc (Tài chính, kinh doanh, tóm tắt sách, kỹ năng)\n"
            "- edge_lan_anh_story: Nữ trầm dịu sâu lắng (Tâm lý học, chữa lành, tâm sự đêm khuya)\n"
            "- gemini_actor_aoede: Nữ ấm áp tinh tế (Âm nhạc, nhạc cụ Guitar/Violin, nghệ thuật, văn hóa)\n"
            "- edge_hoai_my_fast: Nữ trẻ bắt tai nhịp nhanh (Bắt trend TikTok, mẹo hay, tự đánh giá cấp độ)\n"
            "- edge_tuan_kiet_tiktok: Nam tốc độ cao sắc nét (Công nghệ, mẹo thực chiến 60s)\n\n"
            "Danh sách mã nhạc nền hợp lệ (`recommended_bgm_id`):\n"
            "- bgm_drama_tension (Cello trầm điện ảnh hồi hộp, kịch tính, bí ẩn)\n"
            "- bgm_lofi_story (Đàn Piano trầm lắng sâu sắc cho kiến thức, tâm lý, kể chuyện)\n"
            "- bgm_luxury_acoustic (Violin & Guitar mộc ấm áp cho âm nhạc, nhạc cụ, nghệ thuật)\n"
            "- bgm_upbeat_shop (Guitar rải hợp âm tươi sáng cho mẹo hay, đời sống, cấp độ kỹ năng)\n\n"
            "Yêu cầu cho trường `expanded_description`: Viết chi tiết bằng tiếng Việt gồm 5 đến 7 gạch đầu dòng theo đúng "
            "trình tự thời gian của video (1. Mở đầu Hook 3 giây gây tò mò -> 2..5. Các lớp triển khai chi tiết cụ thể, ví dụ/tình tiết sống động, bước ngoặt cao trào -> 6. Kết luận đắt giá & câu hỏi kích thích bình luận), "
            "mỗi dòng đủ ý sâu sắc để biên kịch viết lời bình không bị chung chung.\n\n"
            "Trả về JSON theo đúng cấu trúc:\n"
            "{\n"
            '  "refined_title": "Tiêu đề video đã nâng cấp cực cuốn hút, rõ chủ đề (<= 110 ký tự)",\n'
            '  "alternative_titles": ["Gợi ý tiêu đề 2", "Gợi ý tiêu đề 3", "Gợi ý tiêu đề 4"],\n'
            '  "hook_opening": "Câu nói mở đầu 3 giây đầu tiên giữ chân người xem ngay lập tức",\n'
            '  "expanded_description": "- Mở đầu (0-5s): ...\\n- Triển khai 1: ...\\n- Triển khai 2: ...\\n- Cao trào / Điểm mấu chốt: ...\\n- Cái kết & Tương tác: ...",\n'
            '  "visual_direction": "Mô tả thống nhất về nhân vật/chủ thể, bối cảnh và tông ánh sáng bằng tiếng Việt để các cảnh lên hình đồng bộ",\n'
            '  "recommended_tone": "Mô tả chi tiết nhịp đọc, cảm xúc và phong cách kể chuyện phù hợp nhất",\n'
            '  "recommended_duration_sec": 75,\n'
            '  "recommended_part_count": 1,\n'
            '  "recommended_voice_id": "gemini_yt_orus",\n'
            '  "recommended_bgm_id": "bgm_lofi_story",\n'
            '  "recommended_visual_mode": "AI_IMAGE hoặc HYBRID",\n'
            '  "analysis_summary": "Tóm tắt 1-2 câu cách AI vừa phát triển ý tưởng ngắn của bạn để tối ưu giữ chân người xem"\n'
            "}"
        )
        data = await self._call_gemini_json(prompt)
        ref_title = str(data.get("refined_title") or seed_title or seed_brief[:80]).strip()[:195]
        if len(ref_title) < 3:
            ref_title = "Câu chuyện & Góc nhìn đặc sắc"

        alt_titles = [
            str(x).strip()[:195]
            for x in (data.get("alternative_titles") or [])
            if str(x).strip() and str(x).strip() != ref_title
        ][:3]
        hook_open = str(data.get("hook_opening") or "").strip()
        vis_dir = str(data.get("visual_direction") or "").strip()
        exp_desc = str(data.get("expanded_description") or seed_brief or ref_title).strip()
        if vis_dir and "Định hướng hình ảnh" not in exp_desc:
            exp_desc = f"{exp_desc}\n- Định hướng hình ảnh xuyên suốt: {vis_dir}"

        dur = int(data.get("recommended_duration_sec") or req.target_duration_sec or 75)
        dur = max(MIN_ALLOWED_CLIP_SEC, min(MAX_ALLOWED_CLIP_SEC, dur))
        parts = max(1, min(20, int(data.get("recommended_part_count") or req.part_count or 1)))
        vis_raw = str(data.get("recommended_visual_mode") or "AI_IMAGE").strip().upper()
        vis_mode = VisualMode.HYBRID if vis_raw == "HYBRID" else VisualMode.AI_IMAGE

        return BriefExpandResultDTO(
            refined_title=ref_title,
            alternative_titles=alt_titles,
            hook_opening=hook_open,
            expanded_description=exp_desc[:5900],
            visual_direction=vis_dir,
            recommended_tone=str(
                data.get("recommended_tone")
                or "Mở đầu cuốn hút trong 3 giây đầu, nhịp kể giàu cảm xúc và cuốn người xem tới giây cuối"
            ).strip(),
            recommended_duration_sec=dur,
            recommended_part_count=parts,
            recommended_voice_id=str(data.get("recommended_voice_id") or "edge_nam_minh_movie").strip(),
            recommended_bgm_id=str(data.get("recommended_bgm_id") or "bgm_lofi_story").strip(),
            recommended_visual_mode=vis_mode,
            used_api_key=True,
            analysis_summary=str(
                data.get("analysis_summary")
                or "Đã phân tích ý tưởng gốc và triển khai thành kịch bản phân cảnh chi tiết kèm bối cảnh hình ảnh đồng bộ."
            ).strip(),
        )

    @staticmethod
    def _expand_brief_offline_fallback(req: BriefExpandRequestDTO) -> BriefExpandResultDTO:
        """Smart local structure expander when GEMINI_API_KEY is not configured."""
        raw_t = req.raw_title.strip()
        raw_b = req.short_brief.strip()
        base_subject = raw_t or raw_b.splitlines()[0][:90].strip()
        combined_low = f"{raw_t} {raw_b}".lower()

        if req.mode == ProjectMode.PRODUCT_SHOWCASE:
            refined = raw_t if len(raw_t) >= 12 else f"{base_subject} — Chất Liệu Thực Tế & Độ Hoàn Thiện Sắc Nét"
            seed_lines = [ln.strip(" -•\t") for ln in raw_b.splitlines() if ln.strip(" -•\t")]
            seed_note = "; ".join(seed_lines) if seed_lines else base_subject
            expanded = (
                f"- Điểm chạm ấn tượng đầu tiên: Thiết kế chỉn chu và độ hoàn thiện thực tế nổi bật của {base_subject}.\n"
                f"- Chi tiết cốt lõi từ mô tả gốc: {seed_note}.\n"
                "- Cảm giác trải nghiệm thực tế: Chất liệu chọn lọc mang lại độ bền ổn định và trải nghiệm sử dụng êm ái.\n"
                "- Đối tượng phù hợp: Dành cho cả người mới bắt đầu lẫn người dùng yêu cầu sự tinh tế lâu dài.\n"
                "- Quyền lợi đi kèm: Kiểm tra kỹ lưỡng từng sản phẩm trước khi gửi và hỗ trợ tư vấn trực tiếp tận tâm."
            )
            clean_exp = TikTokShopComplianceChecker.check_and_sanitize(expanded).sanitized_text or expanded
            return BriefExpandResultDTO(
                refined_title=refined[:195],
                alternative_titles=[
                    f"Đánh giá chi tiết {base_subject}: Đâu là điểm đáng giá nhất?"[:195],
                    f"Trải nghiệm thực tế {base_subject} dành cho người mới"[:195],
                ],
                hook_opening=f"Điều gì khiến {base_subject} luôn được khách hàng hỏi kỹ ngay từ cái nhìn đầu tiên?",
                expanded_description=clean_exp,
                visual_direction="Cận cảnh bề mặt chất liệu, góc nghiêng 45 độ tôn dáng và khung hình trải nghiệm thực tế.",
                recommended_tone=CopywritingTone.ARTISAN_STORYTELLER.value,
                recommended_sales_angle=SalesScriptAngle.EXPERT_SPEC_REVIEW,
                recommended_cta="Bạn nhắn trực tiếp hoặc để lại bình luận để cửa hàng gửi video quay cận thực tế nhé.",
                recommended_duration_sec=max(MIN_ALLOWED_CLIP_SEC, min(MAX_ALLOWED_CLIP_SEC, req.target_duration_sec or 55)),
                recommended_part_count=1,
                recommended_voice_id="edge_nam_nghe_nhan",
                recommended_bgm_id="bgm_luxury_acoustic",
                recommended_visual_mode=VisualMode.AI_IMAGE,
                used_api_key=False,
                analysis_summary="Đã chuẩn hóa bố cục giới thiệu sản phẩm 5 phần (Gắn thêm GEMINI_API_KEY ở mục API & Sao lưu để AI viết sâu hơn theo ngữ cảnh riêng).",
            )

        is_mystery = any(
            k in combined_low
            for k in ("kinh dị", "bí ẩn", "đêm", "tin nhắn", "tương lai", "cửa", "ma", "vụ án", "rùng rợn")
        )
        is_music = any(
            k in combined_low for k in ("guitar", "violin", "piano", "đàn", "âm nhạc", "hợp âm", "nhạc cụ")
        )
        voice_id = (
            "edge_bong_dem_horror"
            if is_mystery
            else "gemini_actor_aoede"
            if is_music
            else "edge_hoai_my_fast"
        )
        bgm_id = (
            "bgm_drama_tension"
            if is_mystery
            else "bgm_luxury_acoustic"
            if is_music
            else "bgm_lofi_story"
        )
        tone_txt = (
            "Hồi hộp, trầm lạnh, nhấn nhịp căng thẳng ở từng tình tiết bất ngờ"
            if is_mystery
            else "Gần gũi, truyền cảm hứng và chia sẻ thực tế dễ áp dụng ngay"
        )
        refined = (
            raw_t
            if len(raw_t) >= 18
            else f"{base_subject}: Sự Thật & Những Chi Tiết Đắt Giá Ít Ai Nhận Ra"
        )
        extra_context = f" ({raw_b.strip()})" if raw_b.strip() and raw_b.strip() != raw_t else ""
        vis_guide = (
            "Bối cảnh phòng tối ánh trăng xanh điện ảnh, góc máy cận cảnh giàu chiều sâu kịch tính"
            if is_mystery
            else "Ánh sáng ấm áp điện ảnh, góc quay cận chủ thể sắc nét chuẩn khung dọc 9:16"
        )
        expanded = (
            f"- Mở đầu Hook 3s: Đặt câu hỏi trực diện gây tò mò mạnh về {base_subject}{extra_context}.\n"
            f"- Bối cảnh & Khởi đầu: Giới thiệu tình huống thực tế khiến người xem lập tức đồng cảm hoặc hồi hộp theo dõi.\n"
            f"- Triển khai chi tiết 1: Phân tích dấu hiệu / tình tiết đầu tiên rõ ràng, dễ hình dung bằng hình ảnh cụ thể.\n"
            f"- Triển khai chi tiết 2: Đẩy sâu vào điểm khác biệt cốt lõi hoặc tình tiết bước ngoặt bất ngờ.\n"
            f"- Cao trào: Khoảnh khắc đắt giá nhất giải đáp nút thắt chính của chủ đề {base_subject}.\n"
            f"- Kết thúc & Tương tác: Đúc kết thông điệp ngắn gọn và đặt câu hỏi mở để khán giả bình luận chia sẻ.\n"
            f"- Định hướng hình ảnh xuyên suốt: {vis_guide}."
        )
        return BriefExpandResultDTO(
            refined_title=refined[:195],
            alternative_titles=[
                f"90% Người Xem Bất Ngờ Khi Biết Điều Này Về {base_subject}"[:195],
                f"Giải Mã Chi Tiết: {base_subject} Trong 60 Giây"[:195],
            ],
            hook_opening=f"Bạn đã bao giờ rơi vào tình huống {base_subject} và nhận ra điều bất ngờ phía sau chưa?",
            expanded_description=expanded,
            visual_direction=vis_guide,
            recommended_tone=tone_txt,
            recommended_duration_sec=max(MIN_ALLOWED_CLIP_SEC, min(MAX_ALLOWED_CLIP_SEC, req.target_duration_sec or 75)),
            recommended_part_count=req.part_count,
            recommended_voice_id=voice_id,
            recommended_bgm_id=bgm_id,
            recommended_visual_mode=VisualMode.AI_IMAGE,
            used_api_key=False,
            analysis_summary="Đã mở rộng ý tưởng ngắn thành dàn ý 6 phân cảnh chuẩn Shorts/TikTok (Cấu hình GEMINI_API_KEY để kích hoạt AI phân tích chuyên sâu).",
        )

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
        scenes_per_part = max(6, round(req.target_duration_sec / 7.5))
        prompt = (
            "Bạn là biên kịch & đạo diễn hình ảnh video ngắn triệu view trên YouTube Shorts và TikTok.\n"
            f"Chủ đề / Tiêu đề chính: {req.topic_title}\n"
            f"Mô tả chi tiết & Dàn ý triển khai:\n{req.key_points or 'Tự triển khai hấp dẫn, giàu kịch tính, lớp lang rõ ràng'}\n"
            f"Phong cách giọng kể: {req.narrative_tone}\n"
            f"Số tập cần chia: {req.part_count} (mỗi tập dài khoảng {req.target_duration_sec} giây, "
            f"gồm khoảng {scenes_per_part} phân cảnh nối tiếp mượt mà).\n\n"
            "QUY TẮC BẮT BUỘC ĐỂ VIDEO ĐẠT CHẤT LƯỢNG CAO NHẤT:\n"
            "1. `vi_text`: Lời đọc thuyết minh tiếng Việt tự nhiên, truyền cảm, giàu nhịp điệu nói (KHÔNG viết nhãn 'Cảnh 1:', KHÔNG dùng dấu hai chấm khô cứng). Cảnh 1 phải là câu Hook 3 giây cực cuốn.\n"
            "2. `image_prompt`: Viết bằng TIẾNG ANH mô tả cụ thể khung hình điện ảnh dọc (nhân vật đồng nhất giữa các cảnh, hành động cụ thể khớp 100% với `vi_text`, bối cảnh, góc máy, ánh sáng rõ nét — TUYỆT ĐỐI KHÔNG yêu cầu vẽ chữ/văn bản trên màn hình và KHÔNG dùng từ pitch-black tối đen hoàn toàn).\n"
            "3. `stock_keywords`: 2-3 từ khóa tiếng Anh cụ thể khớp sát nội dung cảnh.\n\n"
            "Trả về JSON theo đúng cấu trúc:\n"
            '{"parts": [{"part_number": 1, "hook_banner_title": "...", "scenes": ['
            '{"duration_sec": 7, "vi_text": "Câu đọc thuyết minh tiếng Việt cuốn hút...", '
            '"image_prompt": "Cinematic portrait movie still of [consistent subject + concrete action + vivid lighting + detailed setting]...", '
            '"stock_keywords": ["english photo keyword 1", "english photo keyword 2"]}]}]}'
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

    @staticmethod
    def _expand_slang_vi(text: str) -> str:
        """Clean emojis/URLs and expand Vietnamese Threads teen-code for clear TTS pronunciation."""
        slang = {
            "ko": "không",
            "k": "không",
            "khum": "không",
            "đc": "được",
            "dc": "được",
            "chx": "chưa",
            "bt": "bình thường",
            "bth": "bình thường",
            "mn": "mọi người",
            "ny": "người yêu",
            "nyc": "người yêu cũ",
            "nv": "nhân viên",
            "cty": "công ty",
            "gđ": "gia đình",
            "tr": "trời",
            "đhs": "chẳng hiểu sao",
            "ntn": "như thế nào",
            "vs": "với",
            "j": "gì",
            "cx": "cũng",
            "mik": "mình",
            "mk": "mình",
            "bh": "bây giờ",
            "trc": "trước",
            "ngta": "người ta",
            "cmt": "bình luận",
            "rep": "trả lời",
            "ib": "nhắn tin",
            "t": "tôi",
            "tui": "tôi",
            "toi": "tôi",
            "hx": "hàng xóm",
            "nm": "nhưng mà",
            "nma": "nhưng mà",
            "nhma": "nhưng mà",
            "bả": "bà ấy",
            "ổng": "ông ấy",
            "xg": "xong",
            "xog": "xong",
            "r": "rồi",
            "rùi": "rồi",
            "s": "sao",
            "v": "vậy",
            "trg": "trường",
            "c1": "cấp một",
            "c2": "cấp hai",
            "c3": "cấp ba",
            "thk": "thằng",
            "ctay": "chia tay",
            "xl": "xin lỗi",
            "dth": "dễ thương",
            "cr": "người thương",
            "lm": "làm",
            "iar": "đi vệ sinh",
            "ỉa": "đi vệ sinh",
            "đái": "đi tiểu",
            "cứt": "chất bẩn",
            "deo": "chẳng",
            "đéo": "chẳng",
            "đếch": "chẳng",
            "vl": "thật sự",
            "vcl": "thật sự",
        }
        cleaned = re.sub(r"https?://\S+", "", text or "")
        cleaned = re.sub(r"(?:[:;=xX][\-^']*[)DdpPvV3/(|]+|=\)+|\^\^|-_-|T_T)", " ", cleaned)
        cleaned = re.sub(
            "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"([a-zA-Zà-ỹÀ-Ỹ])\1{2,}", r"\1", cleaned).strip()
        if not cleaned:
            return ""
        pat = r"\b(" + "|".join(re.escape(k) for k in slang.keys()) + r")\b"
        out = re.sub(
            pat,
            lambda m: (
                slang[m.group(0).lower()].capitalize()
                if m.group(0)[0].isupper()
                else slang[m.group(0).lower()]
            ),
            cleaned,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s{2,}", " ", out).strip()

    @staticmethod
    def _assign_comment_voices(
        comments: List[ThreadCommentItemDTO],
        host_voice_id: str,
        available_voice_ids: List[str],
        multi_voice_cast: bool,
        male_voice_id: str = "threads_nam_chinh",
        female_voice_id: str = "threads_nu_chinh",
    ) -> List[ThreadCommentItemDTO]:
        """Strictly use ONLY the 2 main voices (1 Male & 1 Female) alternating across comments."""
        eff_male = (
            male_voice_id
            if male_voice_id in available_voice_ids
            else (
                "threads_nam_chinh"
                if "threads_nam_chinh" in available_voice_ids
                else (available_voice_ids[0] if available_voice_ids else host_voice_id)
            )
        )
        eff_female = (
            female_voice_id
            if female_voice_id in available_voice_ids
            else (
                "threads_nu_chinh"
                if "threads_nu_chinh" in available_voice_ids
                else (
                    next((v for v in available_voice_ids if v != eff_male), eff_male)
                )
            )
        )
        if not multi_voice_cast:
            return [c.model_copy(update={"voice_profile_id": host_voice_id}) for c in comments]

        # Start Comment #1 with the opposite voice from OP so OP -> Comment #1 contrasts immediately
        two_voice_pair = (
            [eff_male, eff_female]
            if host_voice_id == eff_female
            else [eff_female, eff_male]
        )

        updated: List[ThreadCommentItemDTO] = []
        for idx, c in enumerate(comments):
            chosen = (
                c.voice_profile_id
                if (c.voice_profile_id and c.voice_profile_id in (eff_male, eff_female))
                else two_voice_pair[idx % len(two_voice_pair)]
            )
            updated.append(c.model_copy(update={"voice_profile_id": chosen}))
        return updated

    async def curate_threads_bundle(
        self,
        raw_bundle: ScrapedThreadBundleDTO,
        req: ThreadsExtractRequestDTO,
        available_voice_ids: List[str],
    ) -> ScrapedThreadBundleDTO:
        """Curate top N replies by vibe & length mode, preserve full long stories, expand teen-code & cast 2 voices."""
        vibe_desc_map = {
            ThreadFilterVibe.FUNNY_VIRAL: "Hài hước, mặn mòi, duyên dáng, bất ngờ chuẩn viral TikTok",
            ThreadFilterVibe.LONG_STORY: "Kể chuyện dài, tâm sự chi tiết có đầu có cuối, nhiều tình tiết lôi cuốn người nghe",
            ThreadFilterVibe.EMPATHY_STORY: "Đồng cảm, tâm sự chân thật, sâu sắc, chạm cảm xúc người nghe",
            ThreadFilterVibe.DEBATE_SPICY: "Tranh luận đa chiều, phản biện sắc sảo, nhiều góc nhìn trái ngược",
            ThreadFilterVibe.TOP_LIKED: "Tương tác cao nhất, đại diện đúng tâm lý số đông",
        }
        vibe_desc = vibe_desc_map.get(req.filter_vibe, "Cuốn hút, tự nhiên")
        target_n = max(1, min(20, int(req.max_comments)))
        eff_min_chars = max(
            int(req.min_comment_chars or 0),
            95 if req.filter_vibe == ThreadFilterVibe.LONG_STORY else (65 if req.prefer_long_comments else 0),
        )
        wants_long = bool(
            req.prefer_long_comments
            or req.filter_vibe == ThreadFilterVibe.LONG_STORY
            or eff_min_chars >= 55
        )

        # Pre-rank raw comments: when `wants_long` is active, sort longest real stories to the top!
        if wants_long:
            long_enough = [
                c
                for c in raw_bundle.comments
                if len(c.raw_text.strip()) >= eff_min_chars
                or bool(c.attached_image_url or c.attached_image_path)
            ]
            shorter_rest = [
                c
                for c in raw_bundle.comments
                if c not in long_enough
            ]
            long_enough.sort(key=lambda it: -len(it.raw_text.strip()))
            shorter_rest.sort(key=lambda it: -len(it.raw_text.strip()))
            ranked_pool = [*long_enough, *shorter_rest]
        else:
            ranked_pool = sorted(
                raw_bundle.comments,
                key=lambda it: (
                    0 if (it.attached_image_url or it.attached_image_path) else 1,
                    0 if len(it.raw_text.strip()) >= 45 else 1,
                ),
            )

        if self.api_key:
            raw_cmts_dump = [
                {
                    "source_index": i,
                    "author": c.author_handle,
                    "char_length": len(c.raw_text.strip()),
                    "text": c.raw_text[:2500],
                    "likes": c.likes_display or str(c.likes_count),
                    "has_attached_image": bool(c.attached_image_url or c.attached_image_path),
                }
                for i, c in enumerate(ranked_pool[:40])
            ]
            long_rule_txt = (
                f"\n- CHẾ ĐỘ SĂN BÌNH LUẬN DÀI ĐANG BẬT (ưu tiên >= {eff_min_chars} ký tự): BẮT BUỘC chọn các bình luận có `char_length` DÀI NHẤT, kể câu chuyện chi tiết nhiều câu từ đầu đến cuối; loại bỏ các bình luận cụt 2-5 chữ nếu trong danh sách có bình luận dài hơn!"
                if wants_long
                else ""
            )
            prompt = (
                "Bạn là đạo diễn sản xuất video ngắn 'Chủ đề Threads & Bình luận cộng đồng' triệu view trên TikTok/Shorts.\n"
                f"Bài đăng gốc ({raw_bundle.op_author_handle}, có ảnh đính kèm={bool(raw_bundle.op_image_url or raw_bundle.op_image_path)}): {raw_bundle.op_display_text}\n"
                f"Danh sách bình luận thô thu thập được ({len(raw_cmts_dump)} mục): {json.dumps(raw_cmts_dump, ensure_ascii=False)}\n"
                f"Số lượng bình luận tiêu biểu cần lấy: ĐÚNG {target_n} bình luận.\n"
                f"Gu chọn lọc mong muốn: {vibe_desc}.{long_rule_txt}\n"
                f"Bung viết tắt teen-code & dịch sang tiếng Việt tự nhiên: {'CÓ' if req.expand_slang_and_translate else 'KHÔNG'}.\n\n"
                "Yêu cầu bắt buộc:\n"
                "1. Nếu bài gốc hoặc bình luận bằng tiếng nước ngoài (Anh/Trung...), hãy dịch mượt sang tiếng Việt đời thường chuẩn văn phong Threads.\n"
                f"2. Chọn ra ĐÚNG {target_n} bình luận xuất sắc nhất khớp gu '{vibe_desc}' "
                f"{'(ưu tiên số 1 các câu chuyện DÀI nhiều tình tiết có char_length cao nhất, kế đến là bình luận có ảnh đính kèm)' if wants_long else '(ưu tiên giữ lại bình luận thật có has_attached_image: true kèm các bình luận mặn mòi nhất)'}. "
                "Nếu lấy từ danh sách thô, BẮT BUỘC giữ đúng `source_index` (0..N-1) của bình luận đó và đặt `is_ai_suggested: false`. "
                f"Chỉ khi danh sách thô ít hơn {target_n} câu thì mới viết bổ sung cho đủ {target_n} câu (`source_index: -1`, `is_ai_suggested: true` — nếu ở chế độ bình luận dài thì câu bổ sung cũng phải là một câu chuyện dài 3–5 câu sinh động).\n"
                "3. CẤM TÓM TẮT HAY CẮT BỚT NỘI DUNG BÌNH LUẬN DÀI! Với các bình luận kể chuyện dài (100 - 1500 ký tự), BẮT BUỘC giữ TRỌN VẸN 100% độ dài và mọi tình tiết từ đầu đến cuối ở cả `display_text` lẫn `spoken_vi_text`.\n"
                "4. Với cả bài gốc và mỗi bình luận, trả về 2 phiên bản:\n"
                "   - display_text: Văn bản đầy đủ hiển thị đẹp trên Thẻ Bình Luận (giữ nguyên độ dài & cảm xúc gốc).\n"
                "   - spoken_vi_text: Lời đọc đầy đủ cho diễn viên giọng Việt bản ngữ tốc độ nhanh — TUYỆT ĐỐI bung hết viết tắt (ko->không, đc->được, t->tôi, hx->hàng xóm, nm->nhưng mà, xog->xong, trg->trường, c3->cấp ba...), nói giảm nhẹ từ thô tục nhạy cảm cho an toàn TikTok, xóa sạch emoji/ký hiệu (=)), :)), 🤣), đặt dấu phẩy/chấm ngắt nhịp tự nhiên.\n"
                "Trả về JSON hợp lệ:\n"
                "{\n"
                '  "topic_title": "Tiêu đề ngắn gọn giật tít <= 85 ký tự",\n'
                '  "op_author_handle": "@ten_chu_thot",\n'
                '  "op_display_text": "Nội dung bài đăng gốc hiển thị trên thẻ",\n'
                '  "op_spoken_vi_text": "Lời đọc bài đăng gốc tự nhiên truyền cảm",\n'
                '  "comments": [\n'
                "    {\n"
                '      "source_index": 0,\n'
                '      "author_handle": "@nickname_tu_nhien",\n'
                '      "display_text": "Toàn bộ nội dung bình luận không cắt bớt",\n'
                '      "spoken_vi_text": "Toàn bộ lời đọc bình luận mượt mà không có icon",\n'
                '      "likes_display": "1,4K",\n'
                '      "is_ai_suggested": false\n'
                "    }\n"
                "  ]\n"
                "}"
            )
            try:
                data = await self._call_gemini_json(prompt)
                ai_cmts_raw = data.get("comments") or []
                curated_list: List[ThreadCommentItemDTO] = []
                used_raw_indices: set[int] = set()

                raw_avatar_lookup: Dict[str, str] = {}
                for rc_item in ranked_pool:
                    norm_h = re.sub(r"[^a-z0-9]", "", rc_item.author_handle.lower())
                    if norm_h and rc_item.avatar_url and norm_h not in raw_avatar_lookup:
                        raw_avatar_lookup[norm_h] = rc_item.avatar_url

                def _match_raw_comment(item_dict: dict) -> Optional[ThreadCommentItemDTO]:
                    s_idx = item_dict.get("source_index")
                    try:
                        s_int = int(s_idx) if s_idx is not None and not isinstance(s_idx, bool) else -1
                    except (TypeError, ValueError):
                        s_int = -1
                    if 0 <= s_int < len(ranked_pool):
                        used_raw_indices.add(s_int)
                        return ranked_pool[s_int]
                    h_cand = re.sub(r"[^a-z0-9]", "", str(item_dict.get("author_handle") or "").lower())
                    d_cand = str(item_dict.get("display_text") or "").strip().lower()[:32]
                    for r_i, rc in enumerate(ranked_pool):
                        if r_i in used_raw_indices:
                            continue
                        rc_h = re.sub(r"[^a-z0-9]", "", rc.author_handle.lower())
                        if (h_cand and rc_h == h_cand) or (
                            len(d_cand) >= 8 and d_cand in rc.raw_text.lower()
                        ):
                            used_raw_indices.add(r_i)
                            return rc
                    return None

                for idx, item in enumerate(ai_cmts_raw[:target_n], start=1):
                    if not isinstance(item, dict):
                        continue
                    disp = str(item.get("display_text") or "").strip()
                    spoken = str(item.get("spoken_vi_text") or disp).strip()
                    if not disp:
                        continue
                    matched_rc = _match_raw_comment(item)
                    # Anti-truncation guardrail: NEVER let LLM shorten a real long story comment!
                    if matched_rc is not None:
                        orig_full = (matched_rc.display_text or matched_rc.raw_text).strip()
                        if len(orig_full) >= 85 and len(disp) < int(len(orig_full) * 0.78):
                            disp = orig_full
                        if len(orig_full) >= 85 and len(spoken) < int(len(orig_full) * 0.75):
                            spoken = self._expand_slang_vi(orig_full) or orig_full

                    h_raw = str(
                        item.get("author_handle")
                        or (matched_rc.author_handle if matched_rc else f"@thanhvien_{idx:02d}")
                    ).strip()
                    if not h_raw.startswith("@"):
                        h_raw = f"@{h_raw}"
                    if req.anonymize_handles:
                        h_raw = f"@nguoila_{idx:02d}"
                    curated_list.append(
                        ThreadCommentItemDTO(
                            comment_id=f"cur_{idx:02d}",
                            author_handle=h_raw[:60],
                            raw_text=disp[:4000],
                            display_text=disp[:4000],
                            spoken_vi_text=self._expand_slang_vi(spoken)[:4000]
                            if req.expand_slang_and_translate
                            else spoken[:4000],
                            likes_display=str(
                                item.get("likes_display")
                                or (matched_rc.likes_display if matched_rc else f"{max(24, 680 - idx * 53)}")
                            )[:24],
                            attached_image_url=matched_rc.attached_image_url if matched_rc else "",
                            attached_image_path=matched_rc.attached_image_path if matched_rc else "",
                            avatar_url=(
                                matched_rc.avatar_url
                                if (matched_rc and matched_rc.avatar_url)
                                else raw_avatar_lookup.get(re.sub(r"[^a-z0-9]", "", h_raw.lower()), "")
                            ),
                            avatar_path=matched_rc.avatar_path if matched_rc else "",
                            is_ai_suggested=bool(item.get("is_ai_suggested")) and matched_rc is None,
                            selected=True,
                        )
                    )

                # When `wants_long` is active, ensure real long story comments (>= 95 chars) were not skipped in favor of tiny 1-liners!
                if wants_long:
                    missed_long = [
                        (r_i, rc)
                        for r_i, rc in enumerate(ranked_pool)
                        if r_i not in used_raw_indices and len(rc.raw_text.strip()) >= max(90, eff_min_chars)
                    ]
                    for r_i, long_rc in missed_long:
                        if len(curated_list) < target_n:
                            used_raw_indices.add(r_i)
                            curated_list.append(
                                long_rc.model_copy(
                                    update={
                                        "author_handle": f"@nguoila_{len(curated_list) + 1:02d}"
                                        if req.anonymize_handles
                                        else long_rc.author_handle,
                                        "spoken_vi_text": self._expand_slang_vi(
                                            long_rc.spoken_vi_text or long_rc.display_text
                                        ),
                                        "selected": True,
                                    }
                                )
                            )
                        else:
                            # Replace shortest item in curated_list if that item is much shorter (< 75 chars)
                            shortest_idx = min(
                                range(len(curated_list)),
                                key=lambda k: len(curated_list[k].display_text.strip()),
                            )
                            if len(curated_list[shortest_idx].display_text.strip()) < 75:
                                used_raw_indices.add(r_i)
                                curated_list[shortest_idx] = long_rc.model_copy(
                                    update={
                                        "comment_id": f"cur_{shortest_idx + 1:02d}",
                                        "author_handle": f"@nguoila_{shortest_idx + 1:02d}"
                                        if req.anonymize_handles
                                        else long_rc.author_handle,
                                        "spoken_vi_text": self._expand_slang_vi(
                                            long_rc.spoken_vi_text or long_rc.display_text
                                        ),
                                        "selected": True,
                                    }
                                )
                    # Sort final curated list longest-first when in Long Story mode so best stories lead the video!
                    curated_list.sort(key=lambda c_it: -len(c_it.display_text.strip()))

                # Ensure real comments with attached images are never accidentally left behind (unless strict min_comment_chars excluded tiny captions)
                missed_img_cmts = [
                    (r_i, rc)
                    for r_i, rc in enumerate(ranked_pool)
                    if r_i not in used_raw_indices
                    and (rc.attached_image_url or rc.attached_image_path)
                    and (not wants_long or len(rc.raw_text.strip()) >= max(35, eff_min_chars // 2))
                ]
                for _, img_rc in missed_img_cmts:
                    if len(curated_list) < target_n:
                        curated_list.append(
                            img_rc.model_copy(
                                update={
                                    "author_handle": f"@nguoila_{len(curated_list) + 1:02d}"
                                    if req.anonymize_handles
                                    else img_rc.author_handle,
                                    "spoken_vi_text": self._expand_slang_vi(
                                        img_rc.spoken_vi_text or img_rc.display_text
                                    ),
                                    "selected": True,
                                }
                            )
                        )
                    elif not wants_long and any(
                        not c.attached_image_url and not c.attached_image_path for c in curated_list
                    ):
                        for rep_idx in range(len(curated_list) - 1, -1, -1):
                            if not curated_list[rep_idx].attached_image_url and not curated_list[rep_idx].attached_image_path:
                                curated_list[rep_idx] = img_rc.model_copy(
                                    update={
                                        "comment_id": f"cur_{rep_idx + 1:02d}",
                                        "author_handle": f"@nguoila_{rep_idx + 1:02d}"
                                        if req.anonymize_handles
                                        else img_rc.author_handle,
                                        "spoken_vi_text": self._expand_slang_vi(
                                            img_rc.spoken_vi_text or img_rc.display_text
                                        ),
                                        "selected": True,
                                    }
                                )
                                break

                if curated_list:
                    voiced_cmts = self._assign_comment_voices(
                        curated_list,
                        req.host_voice_id,
                        available_voice_ids,
                        req.multi_voice_cast,
                        req.male_voice_id,
                        req.female_voice_id,
                    )
                    op_disp = str(data.get("op_display_text") or raw_bundle.op_display_text).strip()
                    if len(raw_bundle.op_display_text.strip()) >= 85 and len(op_disp) < int(len(raw_bundle.op_display_text.strip()) * 0.78):
                        op_disp = raw_bundle.op_display_text.strip()
                    op_sp = str(data.get("op_spoken_vi_text") or op_disp).strip()
                    if req.expand_slang_and_translate:
                        op_sp = self._expand_slang_vi(op_sp) or op_sp
                    op_h = (
                        "@chuthot_threads"
                        if req.anonymize_handles
                        else str(data.get("op_author_handle") or raw_bundle.op_author_handle).strip()
                    )
                    if not op_h.startswith("@"):
                        op_h = f"@{op_h}"
                    img_cnt = sum(1 for c in voiced_cmts if c.attached_image_url or c.attached_image_path) + (
                        1 if (raw_bundle.op_image_url or raw_bundle.op_image_path) else 0
                    )
                    long_cnt = sum(1 for c in voiced_cmts if len(c.display_text.strip()) >= 95)
                    extra_tags: List[str] = []
                    if long_cnt > 0:
                        extra_tags.append(f"{long_cnt} bình luận kể chuyện dài")
                    if img_cnt > 0:
                        extra_tags.append(f"{img_cnt} ảnh đính kèm")
                    tag_note = f" ({', '.join(extra_tags)})" if extra_tags else ""
                    return ScrapedThreadBundleDTO(
                        source_url=raw_bundle.source_url,
                        platform=raw_bundle.platform,
                        topic_title=str(data.get("topic_title") or raw_bundle.topic_title)[:180],
                        op_author_handle=op_h[:60],
                        op_display_text=op_disp[:3000],
                        op_spoken_vi_text=op_sp[:3000],
                        op_image_url=raw_bundle.op_image_url,
                        op_image_path=raw_bundle.op_image_path,
                        op_avatar_url=raw_bundle.op_avatar_url,
                        op_avatar_path=raw_bundle.op_avatar_path,
                        op_likes_display=raw_bundle.op_likes_display or "2,3K",
                        op_replies_display=raw_bundle.op_replies_display or str(len(voiced_cmts) * 14),
                        op_is_verified=raw_bundle.op_is_verified,
                        op_voice_profile_id=req.host_voice_id,
                        male_voice_id=req.male_voice_id,
                        female_voice_id=req.female_voice_id,
                        comments=voiced_cmts,
                        used_api_key=True,
                        extraction_note=f"AI đã chọn lọc {len(voiced_cmts)} bình luận tiêu biểu{tag_note} & giữ trọn vẹn câu chuyện gốc!",
                    )
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        # Deterministic offline fallback curation (respecting `wants_long` sorting!)
        base_cmts = list(ranked_pool[:target_n])
        fallback_templates = (
            [
                (
                    "@minhkhoi.story",
                    "Kể thật với mọi người, hồi mới ra trường mình từng giấu cả nhà chuyện nghỉ việc ở công ty lớn suốt hai tháng trời. Sáng nào cũng mặc sơ mi xách cặp ra quán cà phê ngồi tự học lại từ đầu, áp lực tới mức không dám gọi điện về quê, may sao cuối cùng cũng xin được đúng công việc mình mê.",
                    "842",
                ),
                (
                    "@linhchi.daily",
                    "Hồi nhỏ mình từng lỡ làm vỡ chiếc bình gốm quý của bố nhưng sợ bị phạt nên đổ thừa cho con mèo hàng xóm chạy qua làm đổ. Mãi tới tận mười năm sau trong bữa cơm Tết mình mới dám thú nhận thì bố chỉ cười bảo bố biết thừa từ hôm đó rồi nhưng thấy mặt con tái mét nên thôi không mắng.",
                    "519",
                ),
                (
                    "@hoangnam.official",
                    "Có một bí mật mình giữ trong lòng suốt ba năm đi làm là người hay để phần hộp sữa chua trên bàn cho cô lao công mỗi chiều tăng ca chính là mình. Cô cứ tưởng phòng nhân sự phát thêm nên hôm nào gặp cũng khoe công ty tâm lý lắm, nhìn nụ cười của cô mà thấy ấm lòng thực sự.",
                    "376",
                ),
            ]
            if wants_long
            else [
                ("@minhkhoi.98", "Đọc xong thấy đúng tâm lý số đông thật sự, ai trải qua rồi mới hiểu cảm giác này.", "842"),
                ("@linhchi.daily", "Mình từng rơi vào đúng hoàn cảnh y hệt chủ thớt luôn, mất gần nửa năm mới rút ra bài học.", "519"),
                ("@hoangnam.official", "Thực ra nhìn ở góc độ ngược lại thì chuyện này cũng có hai mặt, quan trọng là cách mình ứng xử thôi.", "376"),
                ("@thao.vy.genz", "lướt Threads lúc nửa đêm mà gặp đúng bài chạm trúng tim đen thế này sao ngủ nổi trời.", "264"),
                ("@anhduc.work", "Chuẩn không cần chỉnh! Lưu lại ngay để thỉnh thoảng mở ra tự nhắc bản thân.", "195"),
                ("@ngocanh.story", "Bình luận trên Threads lúc nào cũng mặn mà thực tế hơn hẳn, đọc cuốn thật.", "148"),
            ]
        )
        while len(base_cmts) < target_n:
            idx = len(base_cmts)
            h_f, txt_f, lk_f = fallback_templates[idx % len(fallback_templates)]
            base_cmts.append(
                ThreadCommentItemDTO(
                    comment_id=f"fb_{idx + 1:02d}",
                    author_handle=f"@nguoila_{idx + 1:02d}" if req.anonymize_handles else h_f,
                    raw_text=txt_f,
                    display_text=txt_f,
                    spoken_vi_text=self._expand_slang_vi(txt_f),
                    likes_display=lk_f,
                    is_ai_suggested=True,
                    selected=True,
                )
            )

        normalized_cmts: List[ThreadCommentItemDTO] = []
        for idx, c in enumerate(base_cmts[:target_n], start=1):
            disp = (c.display_text or c.raw_text).strip()
            sp = self._expand_slang_vi(c.spoken_vi_text or disp) if req.expand_slang_and_translate else (c.spoken_vi_text or disp)
            h_eff = f"@nguoila_{idx:02d}" if req.anonymize_handles else c.author_handle
            normalized_cmts.append(
                c.model_copy(
                    update={
                        "author_handle": h_eff,
                        "display_text": disp,
                        "spoken_vi_text": sp or disp,
                        "likes_display": c.likes_display or str(max(18, 350 - idx * 25)),
                    }
                )
            )

        voiced_cmts = self._assign_comment_voices(
            normalized_cmts,
            req.host_voice_id,
            available_voice_ids,
            req.multi_voice_cast,
            req.male_voice_id,
            req.female_voice_id,
        )
        op_sp = (
            self._expand_slang_vi(raw_bundle.op_spoken_vi_text or raw_bundle.op_display_text)
            if req.expand_slang_and_translate
            else (raw_bundle.op_spoken_vi_text or raw_bundle.op_display_text)
        ) or raw_bundle.op_display_text
        return raw_bundle.model_copy(
            update={
                "op_author_handle": "@chuthot_threads" if req.anonymize_handles else raw_bundle.op_author_handle,
                "op_spoken_vi_text": op_sp,
                "op_voice_profile_id": req.host_voice_id,
                "male_voice_id": req.male_voice_id,
                "female_voice_id": req.female_voice_id,
                "comments": voiced_cmts,
                "used_api_key": False,
            }
        )

    async def build_threads_clips(
        self,
        bundle: ScrapedThreadBundleDTO,
        project_id: str,
        append_cta_comment: str = "",
        anonymize_handles: bool = False,
    ) -> CutPlanDTO:
        """Build timed CutPlanDTO from approved Threads OP post and selected replies (with card images)."""
        lines: List[NarrationLineDTO] = []
        cursor_ms = 0

        def _estimate_dur_ms(txt: str) -> int:
            words = max(1, len((txt or "").split()))
            return max(1850, int(round((words / 3.55) * 1000.0)) + 200)

        # 1. Opening OP Post Card (seq_index = 0)
        op_disp = bundle.op_display_text.strip()
        op_spoken = (bundle.op_spoken_vi_text or self._expand_slang_vi(op_disp) or op_disp).strip()
        op_dur = _estimate_dur_ms(op_spoken)
        op_handle = "@chuthot_threads" if anonymize_handles else (bundle.op_author_handle or "@chuthot")
        lines.append(
            NarrationLineDTO(
                seq_index=0,
                rel_start_ms=cursor_ms,
                rel_end_ms=cursor_ms + op_dur,
                original_text=op_disp,
                vi_text=op_spoken,
                callout_label="",
                voice_profile_override=bundle.op_voice_profile_id or None,
                speaker_handle=op_handle,
                speaker_avatar_path="" if anonymize_handles else (bundle.op_avatar_path or ""),
                display_card_text=op_disp,
                likes_display=bundle.op_likes_display or "1,8K",
                card_image_path=bundle.op_image_path or "",
                is_op_post=True,
                words=_distribute_words(op_spoken, cursor_ms, cursor_ms + op_dur),
            )
        )
        cursor_ms += op_dur + 110

        def _split_long_story_pairs(disp_text: str, spoken_text: str, max_card_chars: int = 560) -> List[tuple[str, str]]:
            """Keep comments <= 560 chars on 1 full card; split essay-length stories cleanly at sentence boundaries."""
            d_clean = (disp_text or "").strip()
            s_clean = (spoken_text or d_clean).strip()
            if len(d_clean) <= max_card_chars:
                return [(d_clean, s_clean)]

            sentences = [
                seg.strip()
                for seg in re.split(r"(?<=[.!?…\n])\s+|(?<=[,;])\s+(?=[A-ZÀ-Ỹa-zà-ỹ])", d_clean)
                if seg.strip()
            ]
            if len(sentences) <= 1:
                words = d_clean.split()
                chunks_d: List[str] = []
                cur_w: List[str] = []
                for w in words:
                    if cur_w and len(" ".join(cur_w + [w])) > 460:
                        chunks_d.append(" ".join(cur_w))
                        cur_w = [w]
                    else:
                        cur_w.append(w)
                if cur_w:
                    chunks_d.append(" ".join(cur_w))
            else:
                chunks_d = []
                cur_s: List[str] = []
                for sent in sentences:
                    if cur_s and len(" ".join(cur_s + [sent])) > 480:
                        chunks_d.append(" ".join(cur_s))
                        cur_s = [sent]
                    else:
                        cur_s.append(sent)
                if cur_s:
                    chunks_d.append(" ".join(cur_s))

            pairs: List[tuple[str, str]] = []
            for ch_d in chunks_d:
                ch_sp = self._expand_slang_vi(ch_d) or ch_d
                pairs.append((ch_d, ch_sp))
            return pairs or [(d_clean, s_clean)]

        # 2. Selected Comment Cards (seq_index = 1..N, supporting multi-card continuation for essay-length comments)
        active_comments = [c for c in bundle.comments if c.selected]
        for idx, c in enumerate(active_comments, start=1):
            c_disp = (c.display_text or c.raw_text).strip()
            c_spoken = (c.spoken_vi_text or self._expand_slang_vi(c_disp) or c_disp).strip()
            if not c_spoken:
                continue
            c_handle = f"@nguoila_{idx:02d}" if anonymize_handles else (c.author_handle or f"@thanhvien_{idx:02d}")
            story_parts = _split_long_story_pairs(c_disp, c_spoken, max_card_chars=560)
            for p_idx, (part_disp, part_sp) in enumerate(story_parts):
                c_dur = _estimate_dur_ms(part_sp)
                seq = len(lines)
                lines.append(
                    NarrationLineDTO(
                        seq_index=seq,
                        rel_start_ms=cursor_ms,
                        rel_end_ms=cursor_ms + c_dur,
                        original_text=part_disp,
                        vi_text=part_sp,
                        callout_label="",
                        voice_profile_override=c.voice_profile_id or None,
                        speaker_handle=c_handle,
                        speaker_avatar_path="" if anonymize_handles else (c.avatar_path or ""),
                        display_card_text=part_disp,
                        likes_display=c.likes_display or str(max(19, 450 - idx * 35)),
                        card_image_path=(c.attached_image_path or "") if p_idx == 0 else "",
                        is_op_post=False,
                        words=_distribute_words(part_sp, cursor_ms, cursor_ms + c_dur),
                    )
                )
                cursor_ms += c_dur + (70 if p_idx < len(story_parts) - 1 else 110)

        # 3. Optional Engagement Hook CTA Card at the end
        clean_cta = append_cta_comment.strip()
        if clean_cta:
            cta_spoken = self._expand_slang_vi(clean_cta) or clean_cta
            cta_dur = _estimate_dur_ms(cta_spoken)
            seq = len(lines)
            lines.append(
                NarrationLineDTO(
                    seq_index=seq,
                    rel_start_ms=cursor_ms,
                    rel_end_ms=cursor_ms + cta_dur,
                    original_text=clean_cta,
                    vi_text=cta_spoken,
                    callout_label="",
                    voice_profile_override=bundle.op_voice_profile_id or None,
                    speaker_handle=op_handle,
                    speaker_avatar_path="" if anonymize_handles else (bundle.op_avatar_path or ""),
                    display_card_text=clean_cta,
                    likes_display="Ghim",
                    card_image_path="",
                    is_op_post=True,
                    words=_distribute_words(cta_spoken, cursor_ms, cursor_ms + cta_dur),
                )
            )
            cursor_ms += cta_dur + 120

        clip = ClipSpecDTO(
            clip_id=f"{project_id}_part_01",
            project_id=project_id,
            part_number=1,
            source_start_ms=0,
            source_end_ms=max(3000, cursor_ms),
            hook_banner_title=bundle.topic_title[:120] or "Thảo luận nổi bật trên Threads",
            highlight_score=92.0,
            lines=lines,
            append_cta_outro=False,
        )
        return CutPlanDTO(
            project_id=project_id,
            mode=ProjectMode.THREADS_TOPIC,
            clips=[clip],
        )


