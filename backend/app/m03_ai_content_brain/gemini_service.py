"""Gemini Content Brain implementing `ILLMService` (Zero cross-module imports)."""

import asyncio
import json
import re
from typing import Any, Dict, List

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
    SEOPackageDTO,
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

