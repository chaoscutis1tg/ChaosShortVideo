"""Gemini Content Brain implementing `ILLMService` (Zero cross-module imports)."""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from app.m00_core_contracts import (
    AIContentBrainError,
    BriefExpandRequestDTO,
    BriefExpandResultDTO,
    ChatStoryGenerateRequestDTO,
    ClipSpecDTO,
    CopywritingTone,
    CutConfigDTO,
    CutPlanDTO,
    HookScoreRequestDTO,
    HookScoreResultDTO,
    HookVariantDTO,
    ILLMService,
    LLMQuotaExceededError,
    MAX_ALLOWED_CLIP_SEC,
    MAX_NARRATION_CPS,
    MIN_ALLOWED_CLIP_SEC,
    MotionSceneRefineRequestDTO,
    MotionSceneSpecDTO,
    MotionSceneTemplate,
    MotionThemeStyle,
    NarrationLineDTO,
    ProductCategory,
    ProductReviewPromptDTO,
    ProjectMode,
    QuizGenerateRequestDTO,
    RawTranscriptSegmentDTO,
    SalesScriptAngle,
    ScrapedThreadBundleDTO,
    SEOPackageDTO,
    ThreadCommentItemDTO,
    ThreadFilterVibe,
    ThreadsExtractRequestDTO,
    TopicPromptDTO,
    TranscriptResultDTO,
    ViralRadarItemDTO,
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
    if not cleaned.startswith(("{", "[")):
        i_brace = cleaned.find("{")
        j_brace = cleaned.rfind("}")
        if i_brace != -1 and j_brace > i_brace:
            cleaned = cleaned[i_brace : j_brace + 1]
    return json.loads(cleaned)


def infer_motion_spec_for_line(
    vi_text: str,
    seq_index: int = 0,
    total_lines: int = 5,
    theme: MotionThemeStyle = MotionThemeStyle.APPLE_GLASS_DARK,
    topic_hint: str = "",
) -> MotionSceneSpecDTO:
    """Deterministic Motion Graphics storyboarder creating varied Remotion/Claude-style specs
    from natural Vietnamese narration (used both as offline engine & structured sanitizer).
    """
    clean = re.sub(r"\s+", " ", vi_text or "").strip()
    low = clean.lower()
    words = clean.split()
    short_head = " ".join(words[:9]) + ("..." if len(words) > 9 else "")

    # Scene 0 -> Opening Kinetic Hook unless explicit A/B comparison
    if seq_index == 0:
        return MotionSceneSpecDTO(
            template=MotionSceneTemplate.KINETIC_HOOK,
            theme=theme,
            badge_text=(topic_hint[:28].upper() if topic_hint else "ĐIỂM MẤU CHỐT"),
            headline=clean[:140],
            subheadline="Trọng tâm cốt lõi quyết định 80% trải nghiệm thực tế",
        )

    # Detect percentage / number metric (`70%`, `3 lần`, `20 phút`, `4 cấp độ`)
    num_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(%|phần trăm|lần|phút|giây|cấp độ|bước|năm)", low)
    if num_m and seq_index % 4 != 3:
        raw_val = float(num_m.group(1).replace(",", "."))
        unit_raw = num_m.group(2)
        suffix = "%" if unit_raw in ("%", "phần trăm") else f" {unit_raw}"
        return MotionSceneSpecDTO(
            template=MotionSceneTemplate.STAT_COUNTER,
            theme=theme,
            badge_text="CON SỐ BIẾT NÓI",
            headline=short_head,
            subheadline=clean[:180],
            stat_value=max(1.0, min(999.0, raw_val)),
            stat_suffix=suffix,
        )

    # Detect comparison (`so với`, `khác`, `gỗ thịt`, `gỗ ép`, `hay`, `phân biệt`)
    if any(k in low for k in ("so với", "khác biệt", "phân biệt", "gỗ ép", "thay vì", "trong khi")):
        is_wood = any(k in low for k in ("gỗ", "đàn", "guitar", "violin", "âm"))
        return MotionSceneSpecDTO(
            template=MotionSceneTemplate.VERSUS_SPLIT,
            theme=theme,
            badge_text="SO SÁNH TRỰC DIỆN",
            headline=short_head,
            left_title="Gỗ Thịt Solid" if is_wood else "Cách Tối Ưu",
            right_title="Gỗ Ép Phổ Thông" if is_wood else "Cách Cũ Dễ Sai",
            left_points=(
                ["Âm vang dày, ấm tự nhiên", "Càng chơi lâu tiếng càng mở", "Bấm êm tay, giữ âm chuẩn"]
                if is_wood
                else ["Đi thẳng trọng tâm cốt lõi", "Tiết kiệm 60% thời gian", "Hiệu quả bền vững lâu dài"]
            ),
            right_points=(
                ["Âm mỏng, ít độ ngân sâu", "Độ cộng hưởng giảm theo năm", "Dễ mỏi tay khi mới tập"]
                if is_wood
                else ["Lan man thiếu điểm tựa", "Nhanh nản ở tuần thứ 2", "Khó đo lường tiến bộ"]
            ),
        )

    # Cycle cleanly across remaining high-retention infographic templates so scenes never repeat!
    cycle = [
        MotionSceneTemplate.STEP_FLOW,
        MotionSceneTemplate.BAR_CHART,
        MotionSceneTemplate.SPEC_SPOTLIGHT,
        MotionSceneTemplate.VERSUS_SPLIT,
    ]
    chosen_tpl = cycle[(seq_index - 1) % len(cycle)]

    # Split sentence clauses into crisp card items
    clauses = [
        c.strip(" ,.;:-•")
        for c in re.split(r"[,.;—–\-]|(?:\s+và\s+)|(?:\s+nhưng\s+)", clean)
        if len(c.strip(" ,.;:-•")) >= 6
    ]
    while len(clauses) < 3:
        clauses.append(
            [
                "Nắm vững nền tảng cốt lõi ngay từ đầu",
                "Duy trì nhịp thực hành đều đặn mỗi ngày",
                "Cảm nhận sự thay đổi rõ rệt qua từng tuần",
            ][len(clauses)]
        )

    if chosen_tpl == MotionSceneTemplate.BAR_CHART:
        bars = [
            f"{clauses[0][:30]}|94",
            f"{clauses[1][:30]}|72",
            f"{clauses[2][:30]}|46",
        ]
        return MotionSceneSpecDTO(
            template=MotionSceneTemplate.BAR_CHART,
            theme=theme,
            badge_text="THƯỚC ĐO HIỆU QUẢ",
            headline=short_head,
            subheadline=clean[:160],
            items=bars,
        )

    if chosen_tpl == MotionSceneTemplate.VERSUS_SPLIT:
        return MotionSceneSpecDTO(
            template=MotionSceneTemplate.VERSUS_SPLIT,
            theme=theme,
            badge_text="GÓC NHÌN ĐỐI CHIẾU",
            headline=short_head,
            left_title="Chuẩn Chuyên Gia",
            right_title="Thói Quen Cũ",
            left_points=[clauses[0][:44], clauses[1][:44], "Tối ưu trải nghiệm thực tế"],
            right_points=["Bỏ qua bước chuẩn bị nền", clauses[2][:44], "Dễ chững lại giữa chừng"],
        )

    return MotionSceneSpecDTO(
        template=chosen_tpl,
        theme=theme,
        badge_text=f"PHÂN CẢNH {seq_index + 1:02d}/{max(total_lines, seq_index + 1):02d}",
        headline=short_head,
        subheadline=clean[:160],
        items=[c[:54] for c in clauses[:4]],
    )


def _coerce_motion_spec(
    raw_obj: Any,
    vi_text: str,
    seq_index: int,
    total_lines: int,
    theme: MotionThemeStyle,
    topic_hint: str = "",
) -> MotionSceneSpecDTO:
    """Safely parse LLM JSON `motion_spec` dict or fall back to deterministic scene inference."""
    fallback = infer_motion_spec_for_line(vi_text, seq_index, total_lines, theme, topic_hint)
    if not isinstance(raw_obj, dict):
        return fallback
    try:
        tpl_str = str(raw_obj.get("template") or fallback.template.value).strip().upper()
        tpl = (
            MotionSceneTemplate(tpl_str)
            if tpl_str in {t.value for t in MotionSceneTemplate}
            else fallback.template
        )
        raw_items = [str(x).strip()[:68] for x in (raw_obj.get("items") or []) if str(x).strip()][:4]
        raw_lp = [str(x).strip()[:56] for x in (raw_obj.get("left_points") or []) if str(x).strip()][:3]
        raw_rp = [str(x).strip()[:56] for x in (raw_obj.get("right_points") or []) if str(x).strip()][:3]
        return MotionSceneSpecDTO(
            template=tpl,
            theme=theme,
            badge_text=str(raw_obj.get("badge_text") or fallback.badge_text).strip()[:75],
            headline=str(raw_obj.get("headline") or fallback.headline).strip()[:200],
            subheadline=str(raw_obj.get("subheadline") or fallback.subheadline).strip()[:300],
            stat_value=float(raw_obj.get("stat_value") if raw_obj.get("stat_value") is not None else fallback.stat_value),
            stat_prefix=str(raw_obj.get("stat_prefix") or "").strip()[:18],
            stat_suffix=str(raw_obj.get("stat_suffix") or fallback.stat_suffix).strip()[:24],
            items=raw_items or fallback.items,
            left_title=str(raw_obj.get("left_title") or fallback.left_title).strip()[:75],
            right_title=str(raw_obj.get("right_title") or fallback.right_title).strip()[:75],
            left_points=raw_lp or fallback.left_points,
            right_points=raw_rp or fallback.right_points,
        )
    except Exception:
        return fallback


class GeminiContentBrainService(ILLMService):
    """Multi-Brain (Anthropic Claude Sonnet + Google Gemini) scriptwriter, Motion Graphics director,
    context-aware drama translator, smart cutter & SEO generator.
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-3-flash-preview",
        allow_offline_fallback: bool = True,
        anthropic_api_key: str = "",
        anthropic_model: str = "claude-sonnet-4-5",
        preferred_llm: str = "AUTO",
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.anthropic_api_key = anthropic_api_key.strip()
        self.anthropic_model = anthropic_model.strip() or "claude-sonnet-4-5"
        self.preferred_llm = (preferred_llm or "AUTO").strip().upper()
        self.allow_offline_fallback = allow_offline_fallback

    @property
    def has_llm_key(self) -> bool:
        return bool(self.anthropic_api_key or self.api_key)

    async def _call_claude_json(self, prompt: str) -> Any:
        """Invoke Anthropic Claude Messages API across Sonnet models and parse pure JSON."""
        import httpx

        if not self.anthropic_api_key:
            raise AIContentBrainError("Chưa cấu hình khóa ANTHROPIC_API_KEY.")

        models = list(
            dict.fromkeys(
                [
                    self.anthropic_model,
                    "claude-sonnet-4-5",
                    "claude-3-7-sonnet-latest",
                    "claude-3-5-sonnet-latest",
                ]
            )
        )
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        sys_msg = (
            "Bạn là Đạo diễn Biên kịch & Motion Graphics hàng đầu Việt Nam. "
            "Văn phong tiếng Việt tự nhiên, sắc sảo, giàu cảm xúc đời thực, không dùng văn mẫu sáo rỗng. "
            "BẮT BUỘC CHỈ TRẢ VỀ ĐÚNG 1 ĐỐI TƯỢNG JSON HỢP LỆ (không kèm lời giải thích ngoài JSON)."
        )
        last_err: Exception | None = None
        async with httpx.AsyncClient(timeout=32.0) as client:
            for m_name in models:
                try:
                    res = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json={
                            "model": m_name,
                            "max_tokens": 4096,
                            "temperature": 0.55,
                            "system": sys_msg,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    if res.status_code != 200:
                        last_err = RuntimeError(f"Claude HTTP {res.status_code}: {res.text[:220]}")
                        continue
                    blocks = res.json().get("content") or []
                    txt = "".join(
                        str(b.get("text") or "") for b in blocks if b.get("type") == "text"
                    )
                    return _extract_json(txt)
                except Exception as exc:
                    last_err = exc
                    continue
        raise AIContentBrainError(f"Gọi Claude API thất bại: {last_err}")

    async def _call_gemini_json(self, prompt: str) -> Any:
        """Unified resilient Multi-LLM JSON caller: honors `preferred_llm` (`AUTO`/`CLAUDE`/`GEMINI`)
        with automatic cross-provider failover between Anthropic Claude and Google Gemini.
        """
        prefer_claude_first = (
            self.preferred_llm in ("AUTO", "CLAUDE") and bool(self.anthropic_api_key)
        )
        if prefer_claude_first:
            try:
                return await self._call_claude_json(prompt)
            except Exception as claude_err:
                if not self.api_key:
                    raise AIContentBrainError(str(claude_err)) from claude_err

        if not self.api_key:
            if self.anthropic_api_key:
                return await self._call_claude_json(prompt)
            raise AIContentBrainError("Chưa cấu hình khóa ANTHROPIC_API_KEY hoặc GEMINI_API_KEY.")

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
        if self.has_llm_key:
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
        if self.has_llm_key:
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
        is_motion = req.visual_mode == VisualMode.MOTION_GRAPHICS
        motion_schema_instruction = (
            '4. `motion_spec`: Vì đang ở chế độ Đồ Họa Chuyển Động (Motion Graphics kiểu Remotion / Apple / Dan Koe), mỗi cảnh BẮT BUỘC đi kèm đối tượng `motion_spec` đa dạng bố cục (luân phiên KHÔNG trùng lặp liên tiếp giữa: `KINETIC_HOOK`, `STAT_COUNTER`, `BAR_CHART`, `VERSUS_SPLIT`, `STEP_FLOW`, `SPEC_SPOTLIGHT`):\n'
            '   - `template`: Một trong 6 mã trên\n'
            '   - `badge_text`: Nhãn ngắn in hoa (<= 24 ký tự, VD: "BÍ MẬT ÂM SẮC", "CẤP ĐỘ 02")\n'
            '   - `headline`: Tiêu đề đồ họa cô đọng cực sắc nét (<= 65 ký tự)\n'
            '   - `subheadline`: Dòng bổ trợ ngắn gọn (<= 95 ký tự)\n'
            '   - `stat_value` (số, VD 75) & `stat_suffix` (VD "%", " phút") nếu là `STAT_COUNTER`\n'
            '   - `items`: Mảng 3-4 chuỗi ngắn (nếu `BAR_CHART` ghi dạng `"Tên tiêu chí|92"`, nếu `STEP_FLOW`/`SPEC_SPOTLIGHT` ghi nội dung ngắn từng bước/ô)\n'
            '   - `left_title`, `right_title`, `left_points` (3 ý tốt), `right_points` (3 ý đối chiếu) nếu là `VERSUS_SPLIT`.\n\n'
            if is_motion
            else ""
        )
        motion_json_example = (
            ', "motion_spec": {"template": "STAT_COUNTER", "badge_text": "THỐNG KÊ", "headline": "...", "subheadline": "...", "stat_value": 85, "stat_suffix": "%", "items": ["Ý 1|90", "Ý 2|55"], "left_title": "Chuẩn", "right_title": "Thường", "left_points": ["..."], "right_points": ["..."]}'
            if is_motion
            else ""
        )
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
            "3. `stock_keywords`: 2-3 từ khóa tiếng Anh cụ thể khớp sát nội dung cảnh.\n"
            f"{motion_schema_instruction}"
            "Trả về JSON theo đúng cấu trúc:\n"
            '{"parts": [{"part_number": 1, "hook_banner_title": "...", "scenes": ['
            '{"duration_sec": 7, "vi_text": "Câu đọc thuyết minh tiếng Việt cuốn hút...", '
            '"image_prompt": "Cinematic portrait movie still of [consistent subject + concrete action + vivid lighting + detailed setting]...", '
            f'"stock_keywords": ["english photo keyword 1", "english photo keyword 2"]{motion_json_example}'
            "}]}]}"
        )
        data = await self._call_gemini_json(prompt)
        parts_raw = data.get("parts") or []
        if not parts_raw:
            raise AIContentBrainError("AI không trả về danh sách phân cảnh hợp lệ.")

        clips: List[ClipSpecDTO] = []
        for idx, p_obj in enumerate(parts_raw, start=1):
            part_num = int(p_obj.get("part_number") or idx)
            banner = str(p_obj.get("hook_banner_title") or f"{req.topic_title} | Phần {part_num}")
            scenes = p_obj.get("scenes") or []
            lines: List[NarrationLineDTO] = []
            cursor_ms = 0
            n_sc = max(1, len(scenes))
            for s_idx, sc in enumerate(scenes):
                dur_ms = max(3000, int(round(float(sc.get("duration_sec") or 7.0) * 1000)))
                vi_txt = str(sc.get("vi_text") or "").strip()
                if not vi_txt:
                    continue
                img_p = str(sc.get("image_prompt") or f"cinematic vertical 9:16 {req.topic_title}")
                kws = [str(k) for k in (sc.get("stock_keywords") or [req.topic_title])][:4]
                end_ms = cursor_ms + dur_ms
                m_spec = (
                    _coerce_motion_spec(
                        sc.get("motion_spec"),
                        vi_txt,
                        len(lines),
                        n_sc,
                        req.motion_theme,
                        req.topic_title,
                    )
                    if is_motion
                    else None
                )
                lines.append(
                    NarrationLineDTO(
                        seq_index=len(lines),
                        rel_start_ms=cursor_ms,
                        rel_end_ms=end_ms,
                        vi_text=vi_txt,
                        image_prompt=img_p,
                        stock_keywords=kws,
                        motion_spec=m_spec,
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
                m_spec = (
                    infer_motion_spec_for_line(
                        sentence,
                        s_idx,
                        len(all_sentences),
                        req.motion_theme,
                        req.topic_title,
                    )
                    if req.visual_mode == VisualMode.MOTION_GRAPHICS
                    else None
                )
                lines.append(
                    NarrationLineDTO(
                        seq_index=s_idx,
                        rel_start_ms=cur,
                        rel_end_ms=nxt,
                        vi_text=sentence,
                        image_prompt=f"cinematic dramatic vertical 9:16 scene about {req.topic_title}, scene {s_idx + 1}",
                        stock_keywords=[req.topic_title, "cinematic"],
                        motion_spec=m_spec,
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
        if self.has_llm_key:
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

        # Helper: detect English/foreign text (zero Vietnamese diacritics across >=14 alphabetic chars)
        _vi_mark_re = re.compile(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
            re.IGNORECASE,
        )

        def _is_foreign_non_vi(txt: str) -> bool:
            s = (txt or "").strip()
            if len(s) < 14:
                return False
            alpha_cnt = len(re.findall(r"[A-Za-z]", s))
            return alpha_cnt >= 9 and not bool(_vi_mark_re.search(s))

        is_foreign_post = raw_bundle.platform == "reddit" or _is_foreign_non_vi(
            raw_bundle.op_display_text
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

        if self.has_llm_key:
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
                "1. Nếu bài gốc hoặc bình luận bằng tiếng nước ngoài (đặc biệt Reddit tiếng Anh: AITA -> 'Mình có sai không', OP -> 'chủ bài', Edit -> 'Cập nhật'), BẮT BUỘC dịch toàn bộ `topic_title`, `op_display_text`, `op_spoken_vi_text` và mọi `display_text`, `spoken_vi_text` sang TIẾNG VIỆT ĐỜI THƯỜNG TỰ NHIÊN (xưng mình/tôi mượt mà như câu chuyện người Việt kể trên Threads/TikTok).\n"
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
                    # Anti-truncation guardrail: NEVER let LLM shorten a real long story comment,
                    # EXCEPT do NOT overwrite a valid Vietnamese translation back with raw English!
                    if matched_rc is not None:
                        orig_full = (matched_rc.display_text or matched_rc.raw_text).strip()
                        translated_from_foreign = (
                            req.expand_slang_and_translate
                            and _is_foreign_non_vi(orig_full)
                            and not _is_foreign_non_vi(disp)
                        )
                        min_keep_ratio = 0.48 if translated_from_foreign else 0.78
                        if len(orig_full) >= 85 and len(disp) < int(len(orig_full) * min_keep_ratio):
                            disp = orig_full
                        if len(orig_full) >= 85 and len(spoken) < int(len(orig_full) * min_keep_ratio):
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
                    orig_op_full = raw_bundle.op_display_text.strip()
                    op_was_translated = (
                        req.expand_slang_and_translate
                        and _is_foreign_non_vi(orig_op_full)
                        and not _is_foreign_non_vi(op_disp)
                    )
                    if (
                        len(orig_op_full) >= 85
                        and len(op_disp) < int(len(orig_op_full) * (0.48 if op_was_translated else 0.78))
                    ):
                        op_disp = orig_op_full
                    op_sp = str(data.get("op_spoken_vi_text") or op_disp).strip()
                    top_title = str(data.get("topic_title") or raw_bundle.topic_title)[:180]

                    # Ensure any remaining untranslated foreign items (e.g. injected missed_long/img) are translated to Vietnamese!
                    if req.expand_slang_and_translate:
                        to_tr_texts: List[str] = []
                        to_tr_slots: List[tuple[str, int]] = []
                        if _is_foreign_non_vi(top_title):
                            to_tr_slots.append(("title", 0))
                            to_tr_texts.append(top_title)
                        if _is_foreign_non_vi(op_disp):
                            to_tr_slots.append(("op", 0))
                            to_tr_texts.append(op_disp)
                        for c_i, vc in enumerate(voiced_cmts):
                            if _is_foreign_non_vi(vc.display_text):
                                to_tr_slots.append(("cmt", c_i))
                                to_tr_texts.append(vc.display_text)
                        if to_tr_texts:
                            tr_out = await FreeVietnameseTranslator.translate_lines(
                                to_tr_texts, source_lang="auto"
                            )
                            for (kind, idx_slot), vi_str in zip(to_tr_slots, tr_out):
                                if kind == "title":
                                    top_title = vi_str[:180]
                                elif kind == "op":
                                    op_disp = vi_str[:3000]
                                    op_sp = self._expand_slang_vi(vi_str)[:3000]
                                elif kind == "cmt":
                                    old_c = voiced_cmts[idx_slot]
                                    voiced_cmts[idx_slot] = old_c.model_copy(
                                        update={
                                            "display_text": vi_str[:4000],
                                            "spoken_vi_text": self._expand_slang_vi(vi_str)[:4000],
                                        }
                                    )
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
                        topic_title=top_title[:180],
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

        # Deterministic offline / zero-API-key curation (with automatic Vietnamese translation for Reddit/foreign posts!)
        base_cmts = list(ranked_pool[:target_n])
        fb_title = raw_bundle.topic_title
        fb_op_disp = raw_bundle.op_display_text
        did_auto_tr = False
        if req.expand_slang_and_translate and (
            is_foreign_post or any(_is_foreign_non_vi(c.display_text or c.raw_text) for c in base_cmts)
        ):
            batch_src = [
                fb_title,
                fb_op_disp,
                *[(c.display_text or c.raw_text).strip() for c in base_cmts],
            ]
            batch_vi = await FreeVietnameseTranslator.translate_lines(batch_src, source_lang="auto")
            if len(batch_vi) == len(batch_src):
                fb_title = (batch_vi[0] or fb_title)[:180]
                fb_op_disp = (batch_vi[1] or fb_op_disp)[:3000]
                base_cmts = [
                    c.model_copy(
                        update={
                            "display_text": (vi_c or c.display_text)[:4000],
                            "spoken_vi_text": self._expand_slang_vi(vi_c or c.display_text)[:4000],
                        }
                    )
                    for c, vi_c in zip(base_cmts, batch_vi[2:])
                ]
                did_auto_tr = True
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
            self._expand_slang_vi(fb_op_disp if did_auto_tr else (raw_bundle.op_spoken_vi_text or fb_op_disp))
            if req.expand_slang_and_translate
            else (raw_bundle.op_spoken_vi_text or fb_op_disp)
        ) or fb_op_disp
        fb_note = (
            f"Đã hút & tự động dịch sang tiếng Việt bài viết Reddit + {len(voiced_cmts)} bình luận tiêu biểu!"
            if did_auto_tr
            else raw_bundle.extraction_note
        )
        return raw_bundle.model_copy(
            update={
                "topic_title": fb_title[:180],
                "op_display_text": fb_op_disp[:3000],
                "op_author_handle": "@chuthot_threads" if req.anonymize_handles else raw_bundle.op_author_handle,
                "op_spoken_vi_text": op_sp[:3000],
                "op_voice_profile_id": req.host_voice_id,
                "male_voice_id": req.male_voice_id,
                "female_voice_id": req.female_voice_id,
                "comments": voiced_cmts,
                "used_api_key": False,
                "extraction_note": fb_note,
            }
        )

    async def build_threads_clips(
        self,
        bundle: ScrapedThreadBundleDTO,
        project_id: str,
        append_cta_comment: str = "",
        anonymize_handles: bool = False,
        series_parts: int = 1,
    ) -> CutPlanDTO:
        """Build timed CutPlanDTO from approved Threads OP post & replies (supports opt-in Part 1..K Series split)."""
        def _estimate_dur_ms(txt: str) -> int:
            words = max(1, len((txt or "").split()))
            return max(1850, int(round((words / 3.55) * 1000.0)) + 200)

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

        active_comments = [c for c in bundle.comments if c.selected]
        eff_parts = max(1, min(4, int(series_parts or 1), max(1, len(active_comments))))

        op_disp = bundle.op_display_text.strip()
        op_spoken = (bundle.op_spoken_vi_text or self._expand_slang_vi(op_disp) or op_disp).strip()
        op_handle = "@chuthot_threads" if anonymize_handles else (bundle.op_author_handle or "@chuthot")

        # Partition comments evenly across `eff_parts` (1 by default!)
        comment_slices: List[List[ThreadCommentItemDTO]] = []
        if eff_parts <= 1:
            comment_slices = [active_comments]
        else:
            n_c = len(active_comments)
            for p_i in range(eff_parts):
                s_i = int(round(p_i * n_c / eff_parts))
                e_i = int(round((p_i + 1) * n_c / eff_parts))
                if e_i > s_i:
                    comment_slices.append(active_comments[s_i:e_i])
            eff_parts = len(comment_slices)

        clips_out: List[ClipSpecDTO] = []
        global_cmt_rank = 0
        for part_num, part_cmts in enumerate(comment_slices, start=1):
            lines: List[NarrationLineDTO] = []
            cursor_ms = 0

            part_op_disp = (
                op_disp
                if eff_parts == 1 or part_num == 1
                else f"[Phần {part_num}/{eff_parts}] {op_disp}"
            )
            part_op_sp = (
                op_spoken
                if eff_parts == 1 or part_num == 1
                else f"Phần {part_num}. {op_spoken}"
            )
            op_dur = _estimate_dur_ms(part_op_sp)
            lines.append(
                NarrationLineDTO(
                    seq_index=0,
                    rel_start_ms=cursor_ms,
                    rel_end_ms=cursor_ms + op_dur,
                    original_text=part_op_disp,
                    vi_text=part_op_sp,
                    callout_label="",
                    voice_profile_override=bundle.op_voice_profile_id or None,
                    speaker_handle=op_handle,
                    speaker_avatar_path="" if anonymize_handles else (bundle.op_avatar_path or ""),
                    display_card_text=part_op_disp,
                    likes_display=bundle.op_likes_display or "1,8K",
                    card_image_path=(bundle.op_image_path or "") if part_num == 1 else "",
                    is_op_post=True,
                    words=_distribute_words(part_op_sp, cursor_ms, cursor_ms + op_dur),
                )
            )
            cursor_ms += op_dur + 110

            for c in part_cmts:
                global_cmt_rank += 1
                c_disp = (c.display_text or c.raw_text).strip()
                c_spoken = (c.spoken_vi_text or self._expand_slang_vi(c_disp) or c_disp).strip()
                if not c_spoken:
                    continue
                c_handle = (
                    f"@nguoila_{global_cmt_rank:02d}"
                    if anonymize_handles
                    else (c.author_handle or f"@thanhvien_{global_cmt_rank:02d}")
                )
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
                            likes_display=c.likes_display or str(max(19, 450 - global_cmt_rank * 35)),
                            card_image_path=(c.attached_image_path or "") if p_idx == 0 else "",
                            is_op_post=False,
                            words=_distribute_words(part_sp, cursor_ms, cursor_ms + c_dur),
                        )
                    )
                    cursor_ms += c_dur + (70 if p_idx < len(story_parts) - 1 else 110)

            # Cliffhanger on intermediate parts; user CTA on final part
            tail_txt = (
                f"Vẫn còn những bình luận gay cấn nhất ở Phần {part_num + 1} — vào kênh xem tiếp ngay nhé!"
                if part_num < eff_parts
                else append_cta_comment.strip()
            )
            if tail_txt:
                cta_spoken = self._expand_slang_vi(tail_txt) or tail_txt
                cta_dur = _estimate_dur_ms(cta_spoken)
                seq = len(lines)
                lines.append(
                    NarrationLineDTO(
                        seq_index=seq,
                        rel_start_ms=cursor_ms,
                        rel_end_ms=cursor_ms + cta_dur,
                        original_text=tail_txt,
                        vi_text=cta_spoken,
                        callout_label="",
                        voice_profile_override=bundle.op_voice_profile_id or None,
                        speaker_handle=op_handle,
                        speaker_avatar_path="" if anonymize_handles else (bundle.op_avatar_path or ""),
                        display_card_text=tail_txt,
                        likes_display="Xem tiếp" if part_num < eff_parts else "Ghim",
                        card_image_path="",
                        is_op_post=True,
                        words=_distribute_words(cta_spoken, cursor_ms, cursor_ms + cta_dur),
                    )
                )
                cursor_ms += cta_dur + 120

            part_title_prefix = f"[Phần {part_num}/{eff_parts}] " if eff_parts > 1 else ""
            clips_out.append(
                ClipSpecDTO(
                    clip_id=f"{project_id}_part_{part_num:02d}",
                    project_id=project_id,
                    part_number=part_num,
                    source_start_ms=0,
                    source_end_ms=max(3000, cursor_ms),
                    hook_banner_title=(f"{part_title_prefix}{bundle.topic_title}")[:120]
                    or "Thảo luận nổi bật trên Threads",
                    highlight_score=92.0,
                    lines=lines,
                    append_cta_outro=False,
                )
            )

        return CutPlanDTO(
            project_id=project_id,
            mode=ProjectMode.THREADS_TOPIC,
            clips=clips_out,
        )

    async def translate_radar_items(
        self, items: List[ViralRadarItemDTO]
    ) -> List[ViralRadarItemDTO]:
        """Auto-translate foreign Reddit radar titles & snippets into natural Vietnamese."""
        if not items:
            return []
        _vi_re = re.compile(
            r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
            re.IGNORECASE,
        )
        foreign_indices = [
            idx
            for idx, it in enumerate(items)
            if len(re.findall(r"[A-Za-z]", it.title_vi)) >= 8 and not bool(_vi_re.search(it.title_vi))
        ]
        if not foreign_indices:
            return items

        raw_titles = [items[i].title_vi for i in foreign_indices]
        try:
            vi_titles = await FreeVietnameseTranslator.translate_lines(
                raw_titles, source_lang="auto", concurrency=6
            )
        except Exception:
            vi_titles = raw_titles

        patched = list(items)
        for pos, item_idx in enumerate(foreign_indices):
            tr = (vi_titles[pos] if pos < len(vi_titles) else "").strip()
            if tr:
                patched[item_idx] = patched[item_idx].model_copy(update={"title_vi": tr[:280]})
        return patched

    async def generate_chat_story_bundle(
        self, req: ChatStoryGenerateRequestDTO
    ) -> ScrapedThreadBundleDTO:
        """Generate a realistic 2-person Messenger/Zalo/iMessage conversation bundle ready for Chat Story render."""
        idea = req.story_idea.strip()
        name_a = (req.sender_a_name.strip() or "Mình").lstrip("@")
        name_b = (req.sender_b_name.strip() or "Crush").lstrip("@")
        handle_a = f"@{name_a}"
        handle_b = f"@{name_b}"
        voice_a = req.female_voice_id if req.sender_a_is_female else req.male_voice_id
        voice_b = req.male_voice_id if req.sender_a_is_female else req.female_voice_id
        msg_total = max(4, min(18, int(req.message_count)))

        vibe_map = {
            "CRUSH_ROMANTIC": "Ngọt ngào, thả thính tinh tế, hồi hộp rung động tuổi trẻ, câu chốt bất ngờ dễ thương",
            "DRAMA_PLOT_TWIST": "Kịch tính, bắt đầu bình thường nhưng lật kèo (plot twist) căng thẳng ở 2 tin nhắn cuối",
            "FUNNY_BANTER": "Lầy lội, hài hước duyên dáng kiểu GenZ nhắn tin trêu nhau, đọc tới đâu bật cười tới đó",
            "SALES_CONSULT": "Khách nhắn hỏi thật tâm – Chủ shop tư vấn tận tình có tâm, chốt đơn mượt tự nhiên không gượng",
        }
        vibe_desc = vibe_map.get(req.story_vibe, vibe_map["CRUSH_ROMANTIC"])

        if self.has_llm_key:
            prompt = (
                "Bạn là biên kịch chuyên viết kịch bản Video Tin Nhắn Chat (Messenger / Zalo / iMessage) triệu view trên TikTok/Shorts.\n"
                f"Ý tưởng tình huống: {idea}\n"
                f"Nhân vật bên phải (người nhắn chính): {name_a}\n"
                f"Nhân vật bên trái (người đối thoại): {name_b}\n"
                f"Tông màu cảm xúc: {vibe_desc}\n"
                f"Tổng số tin nhắn qua lại: ĐÚNG {msg_total} tin nhắn (tin đầu tiên là tin mở màn kích thích tò mò ngay 2 giây đầu).\n"
                "Yêu cầu:\n"
                "- Mỗi tin nhắn ngắn gọn tự nhiên như người thật nhắn Zalo/Messenger (8–32 chữ/tin), câu đối đáp ăn miếng trả miếng hợp lý.\n"
                "- `display_text` có thể giữ nhịp điệu chat tự nhiên; `spoken_vi_text` viết tròn chữ tiếng Việt tự nhiên để AI lồng tiếng truyền cảm.\n"
                "Trả về JSON chuẩn:\n"
                "{\n"
                '  "topic_title": "Tiêu đề SEO hấp dẫn dưới 90 ký tự",\n'
                '  "messages": [\n'
                '    {"sender": "A hoặc B", "display_text": "...", "spoken_vi_text": "..."}\n'
                "  ]\n"
                "}"
            )
            try:
                parsed = await self._call_gemini_json(prompt)
                raw_msgs = parsed.get("messages") or []
                if isinstance(raw_msgs, list) and len(raw_msgs) >= 3:
                    first_m = raw_msgs[0]
                    first_is_a = str(first_m.get("sender", "A")).strip().upper() != "B"
                    op_disp = str(first_m.get("display_text") or idea).strip()
                    op_sp = str(first_m.get("spoken_vi_text") or self._expand_slang_vi(op_disp) or op_disp).strip()
                    cmts: List[ThreadCommentItemDTO] = []
                    for i, m in enumerate(raw_msgs[1:msg_total], start=1):
                        is_a = str(m.get("sender", "B" if i % 2 == 1 else "A")).strip().upper() == "A"
                        d_txt = str(m.get("display_text") or "").strip()
                        if not d_txt:
                            continue
                        s_txt = str(m.get("spoken_vi_text") or self._expand_slang_vi(d_txt) or d_txt).strip()
                        cmts.append(
                            ThreadCommentItemDTO(
                                comment_id=f"chat_{i:02d}",
                                author_handle=handle_a if is_a else handle_b,
                                display_name=name_a if is_a else name_b,
                                raw_text=d_txt,
                                display_text=d_txt,
                                spoken_vi_text=s_txt,
                                likes_count=0,
                                likes_display="Đã xem",
                                voice_profile_id=voice_a if is_a else voice_b,
                                selected=True,
                            )
                        )
                    if cmts:
                        return ScrapedThreadBundleDTO(
                            source_url="",
                            platform="chat_story",
                            topic_title=str(parsed.get("topic_title") or idea)[:160],
                            op_author_handle=handle_a if first_is_a else handle_b,
                            op_display_text=op_disp,
                            op_spoken_vi_text=op_sp,
                            op_likes_display="Đang hoạt động",
                            op_replies_display=str(len(cmts) + 1),
                            op_voice_profile_id=voice_a if first_is_a else voice_b,
                            male_voice_id=req.male_voice_id,
                            female_voice_id=req.female_voice_id,
                            comments=cmts,
                            used_api_key=True,
                            extraction_note=f"AI đã biên kịch {len(cmts) + 1} tin nhắn hội thoại giữa {name_a} & {name_b}.",
                        )
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        # Smart structured fallback dialogue tailored by vibe & idea
        if req.story_vibe == "SALES_CONSULT":
            pairs = [
                ("B", f"Shop ơi cho mình hỏi {idea} thì người mới bắt đầu dùng có hợp không ạ?"),
                ("A", "Dạ hợp cực kỳ luôn bạn ơi! Dòng này bên mình căn chỉnh sẵn hết rồi, cầm vào là cảm nhận rõ độ êm ngay."),
                ("B", "Mình sợ nhất mua online về âm bị phô hoặc khó bấm giống mấy cây giá rẻ trên mạng ấy."),
                ("A", "Chuẩn tâm lý số đông luôn ạ. Trước khi gửi bên mình đều quay video test âm thực tế từng cây gửi riêng cho bạn duyệt trước."),
                ("B", "Ồ có quay clip test riêng luôn hả shop? Phụ kiện đi kèm đã đủ dùng luôn chưa ạ?"),
                ("A", "Dạ tặng kèm trọn bộ phụ kiện chuẩn từ hộp chống sốc tới giáo trình tự học, mở hộp là tập được liền không phát sinh gì thêm!"),
                ("B", "Nghe yên tâm hẳn luôn, vậy giữ cho mình một bộ gửi về Hà Nội giúp mình nhé!"),
                ("A", "Dạ vâng ạ, để mình chọn ngay bản vân đẹp nhất quay test âm gửi bạn xem liền nha!"),
            ]
        elif req.story_vibe == "DRAMA_PLOT_TWIST":
            pairs = [
                ("A", f"Này, hỏi thật một câu nhé... chuyện {idea} hôm qua là sao vậy?"),
                ("B", "Ơ sao tự nhiên hỏi thế? Ai lại đi đồn linh tinh gì với cậu à?"),
                ("A", "Không ai đồn cả. Chiều qua tớ đứng ngay ở quầy cà phê góc đường, nhìn thấy hết từ đầu tới cuối rồi."),
                ("B", "Khoan đã... cậu nhìn thấy tớ đi chọn quà ở đó thật hả?!"),
                ("A", "Ủa... chọn quà gì cơ? Tớ tưởng hai người hẹn riêng nhau mà?"),
                ("B", "Trời đất ơi nhờ nhỏ bạn thân của cậu đi chọn quà sinh nhật bất ngờ cho cậu tuần tới đó bà tướng ạ!"),
                ("A", "Hả?! Thật luôn á?! Làm người ta suy nghĩ nguyên cả đêm không ngủ được..."),
                ("B", "Thôi lộ hết kế hoạch rồi, tối mai 7h chuẩn bị lên đồ đi ăn bù đền cho tớ đi nhé!"),
            ]
        else:
            pairs = [
                ("A", f"Ngủ chưa đấy? Tự nhiên nhớ lại chuyện {idea} cái tỉnh ngủ luôn..."),
                ("B", "Chưa ngủ nè. Mà ủa sao giờ này tự nhiên lại nhắc chuyện đó vậy?"),
                ("A", "Thì thắc mắc thật mà, hôm đó trời mưa to thế sao lại cố nán lại đợi cùng làm gì?"),
                ("B", "À... tại tiện đường về chung hướng thôi chứ có gì đâu mà hỏi kỹ thế."),
                ("A", "Nhà đằng ấy ở tận quận bên kia, ngược đường hoàn toàn mà bảo tiện đường hả? Khai thật đi!"),
                ("B", "Thì... sợ có người đứng đợi xe một mình trời tối lại lạnh, nên kiếm cớ đứng cùng thêm chút thôi."),
                ("A", "Biết ngay mà! Giấu kỹ thế thảo nào tim người ta cứ đập loạn nhịp suốt từ hôm đó tới giờ."),
                ("B", "Vậy cuối tuần này không cần đợi trời mưa nữa đâu, 7h tối mình qua đón đi uống cacao nóng nhé?"),
            ]

        selected_turns = pairs[:msg_total]
        first_side, first_txt = selected_turns[0]
        first_is_a = first_side == "A"
        cmts_fb: List[ThreadCommentItemDTO] = []
        for idx, (side, txt) in enumerate(selected_turns[1:], start=1):
            is_a = side == "A"
            sp_txt = self._expand_slang_vi(txt) or txt
            cmts_fb.append(
                ThreadCommentItemDTO(
                    comment_id=f"chat_fb_{idx:02d}",
                    author_handle=handle_a if is_a else handle_b,
                    display_name=name_a if is_a else name_b,
                    raw_text=txt,
                    display_text=txt,
                    spoken_vi_text=sp_txt,
                    likes_display="Đã xem",
                    voice_profile_id=voice_a if is_a else voice_b,
                    selected=True,
                )
            )
        return ScrapedThreadBundleDTO(
            source_url="",
            platform="chat_story",
            topic_title=idea[:140],
            op_author_handle=handle_a if first_is_a else handle_b,
            op_display_text=first_txt,
            op_spoken_vi_text=self._expand_slang_vi(first_txt) or first_txt,
            op_likes_display="Đang hoạt động",
            op_replies_display=str(len(cmts_fb) + 1),
            op_voice_profile_id=voice_a if first_is_a else voice_b,
            male_voice_id=req.male_voice_id,
            female_voice_id=req.female_voice_id,
            comments=cmts_fb,
            used_api_key=False,
            extraction_note=f"Đã dựng kịch bản {len(cmts_fb) + 1} tin nhắn đối thoại giữa {name_a} & {name_b}.",
        )

    async def score_and_optimize_hook(
        self, req: HookScoreRequestDTO
    ) -> HookScoreResultDTO:
        """Analyze 3-second retention power of an opening Hook/OP and suggest 3 stronger A/B variants."""
        hook = req.hook_text.strip()
        words = [w for w in hook.split() if w]
        est_sec = round(max(0.8, len(words) / 3.9), 1)

        if self.has_llm_key:
            prompt = (
                "Bạn là chuyên gia tối ưu tỷ lệ giữ chân 3 giây đầu (3-Second Hook Retention) trên TikTok, Reels & YouTube Shorts.\n"
                f"Câu mở đầu hiện tại: \"{hook}\"\n"
                f"Ngữ cảnh nội dung tiếp theo: \"{(req.body_context or '')[:800]}\"\n"
                "Hãy chấm điểm khắt khe trên thang 0-100 và viết lại 3 phương án Hook A/B sắc bén hơn (dưới 20 chữ, không chào hỏi rườm rà, đánh trúng tò mò ngay giây đầu tiên).\n"
                "Trả về JSON chuẩn:\n"
                "{\n"
                '  "overall_score": 78,\n'
                '  "curiosity_score": 75,\n'
                '  "pacing_3s_score": 82,\n'
                '  "emotion_score": 76,\n'
                '  "verdict_label": "Nhận định ngắn gọn 4-8 chữ",\n'
                '  "weakness_note": "Chỉ rõ điểm yếu cụ thể của câu hiện tại trong 1-2 câu",\n'
                '  "variants": [\n'
                '    {"style_label": "Gây tò mò bỏ lửng", "hook_text": "...", "spoken_vi_text": "...", "predicted_score": 92},\n'
                '    {"style_label": "Chạm thẳng cảm xúc", "hook_text": "...", "spoken_vi_text": "...", "predicted_score": 90},\n'
                '    {"style_label": "Tình huống kịch tính", "hook_text": "...", "spoken_vi_text": "...", "predicted_score": 89}\n'
                "  ]\n"
                "}"
            )
            try:
                parsed = await self._call_gemini_json(prompt)
                raw_vars = parsed.get("variants") or []
                vars_out: List[HookVariantDTO] = []
                for v in raw_vars[:3]:
                    ht = str(v.get("hook_text") or "").strip()
                    if not ht:
                        continue
                    sp = str(v.get("spoken_vi_text") or self._expand_slang_vi(ht) or ht).strip()
                    vars_out.append(
                        HookVariantDTO(
                            style_label=str(v.get("style_label") or "Biến thể Viral")[:70],
                            hook_text=ht[:1000],
                            spoken_vi_text=sp[:1000],
                            predicted_score=max(65, min(99, int(v.get("predicted_score") or 90))),
                        )
                    )
                if vars_out:
                    return HookScoreResultDTO(
                        overall_score=max(10, min(100, int(parsed.get("overall_score") or 75))),
                        curiosity_score=max(10, min(100, int(parsed.get("curiosity_score") or 75))),
                        pacing_3s_score=max(10, min(100, int(parsed.get("pacing_3s_score") or 75))),
                        emotion_score=max(10, min(100, int(parsed.get("emotion_score") or 75))),
                        estimated_intro_sec=est_sec,
                        verdict_label=str(parsed.get("verdict_label") or "Đánh giá câu mở đầu")[:110],
                        weakness_note=str(parsed.get("weakness_note") or "")[:550],
                        variants=vars_out,
                        used_api_key=True,
                    )
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        # Deterministic Vietnamese Retention Heuristic Analyzer + 3 Smart Hook Rewriters
        low = hook.lower()
        has_question = "?" in hook or any(
            kw in low for kw in ("ai từng", "sao lại", "có ai", "tại sao", "bí mật", "khoảnh khắc", "sai lầm")
        )
        has_number = bool(re.search(r"\d+", hook))
        has_slow_greeting = low.startswith(("xin chào", "chào mọi người", "hello mọi người", "hôm nay mình"))
        pacing_sc = 92 if 7 <= len(words) <= 18 else (74 if len(words) <= 25 else 56)
        if has_slow_greeting:
            pacing_sc = max(40, pacing_sc - 22)
        curiosity_sc = 88 if (has_question and has_number) else (80 if (has_question or has_number) else 62)
        emotion_sc = (
            86
            if any(
                k in low
                for k in ("khóc", "rung động", "hối hận", "bí mật", "crush", "sốc", "nhớ mãi", "suýt", "đắt giá")
            )
            else 68
        )
        overall = int(round(0.40 * curiosity_sc + 0.32 * pacing_sc + 0.28 * emotion_sc))

        issues: List[str] = []
        if has_slow_greeting:
            issues.append("Mở đầu bằng lời chào làm mất 1.5 giây vàng khiến người xem dễ lướt qua.")
        if len(words) > 22:
            issues.append(f"Câu mở đầu dài {len(words)} từ (~{est_sec}s), nên rút gọn xuống dưới 18 từ để bắt nhịp nhanh hơn.")
        if not has_question and not has_number:
            issues.append("Chưa có câu hỏi gợi tò mò hoặc con số cụ thể để neo mắt người xem trong 3 giây đầu.")
        if not issues:
            issues.append("Nhịp câu đã khá gọn; có thể đẩy mạnh độ tương phản cảm xúc để tăng tỷ lệ xem hết video.")

        verdict = (
            "🔥 Hook Giữ Chân Tốt — Sẵn sàng lên xu hướng"
            if overall >= 82
            else ("⚡ Khá Ổn — Tối ưu nhẹ để bùng nổ hơn" if overall >= 68 else "⚠️ Dễ Bị Lướt Qua — Nên đổi câu mở đầu")
        )
        core_topic = re.sub(r"^(?:topic\s*[:\-]\s*|xin chào[^,.!?]*[,.!?\s]*)", "", hook, flags=re.IGNORECASE).strip()
        core_short = core_topic.rstrip(".!?…")[:95]

        raw_variants = [
            (
                "Gây tò mò bỏ lửng (Curiosity)",
                f"90% mọi người đều từng trải qua chuyện này mà không dám thú nhận: {core_short}?",
                92,
            ),
            (
                "Chạm thẳng cảm xúc (Empathy)",
                f"Chỉ một chi tiết nhỏ thôi nhưng đủ khiến người ta nhớ suốt nhiều năm: {core_short}...",
                90,
            ),
            (
                "Hỏi xoáy kích thích bình luận",
                f"Thật lòng đi, nếu rơi vào đúng cảnh '{core_short}' thì bạn sẽ chọn im lặng hay nói thẳng?",
                89,
            ),
        ]
        variants = [
            HookVariantDTO(
                style_label=lbl,
                hook_text=ht,
                spoken_vi_text=self._expand_slang_vi(ht) or ht,
                predicted_score=sc,
            )
            for lbl, ht, sc in raw_variants
        ]
        return HookScoreResultDTO(
            overall_score=overall,
            curiosity_score=curiosity_sc,
            pacing_3s_score=pacing_sc,
            emotion_score=emotion_sc,
            estimated_intro_sec=est_sec,
            verdict_label=verdict,
            weakness_note=" ".join(issues),
            variants=variants,
            used_api_key=False,
        )

    async def generate_quiz_bundle(
        self, req: QuizGenerateRequestDTO
    ) -> ScrapedThreadBundleDTO:
        """Generate an interactive 3-2-1 Countdown Quiz / Blind Test bundle for high comment engagement."""
        topic = req.quiz_topic.strip()
        q_count = max(1, min(8, int(req.question_count or 3)))
        cd_sec = max(2, min(5, int(req.countdown_sec or 3)))

        if self.has_llm_key:
            prompt = (
                "Bạn là biên kịch chuyên tạo Video Đố Vui / Trắc Nghiệm Phản Xạ 3 Giây kéo hàng nghìn bình luận trên TikTok & YouTube Shorts.\n"
                f"Chủ đề đố vui: {topic} (Nhóm: {req.quiz_category})\n"
                f"Số câu hỏi cần tạo: ĐÚNG {q_count} câu (tăng dần độ thú vị/bất ngờ).\n"
                f"Thời gian đếm ngược mỗi câu: {cd_sec} giây.\n"
                "Yêu cầu:\n"
                "- Mỗi câu hỏi ngắn gọn súc tích, có 3 đáp án A, B, C rõ ràng.\n"
                "- Phần giải đáp nêu đáp án đúng kèm 1 câu giải thích cực thú vị dễ gây tranh luận.\n"
                "Trả về JSON chuẩn:\n"
                "{\n"
                '  "topic_title": "Tiêu đề SEO hấp dẫn dưới 95 ký tự",\n'
                '  "intro_hook": "Câu mở đầu thách đố người xem dưới 22 chữ",\n'
                '  "questions": [\n'
                '    {\n'
                '      "question_card": "Câu 1: ...?\\nA. ...\\nB. ...\\nC. ...",\n'
                '      "question_spoken": "Câu một: ... Đáp án A: ..., B: ..., hay C: ...?",\n'
                '      "answer_card": "✅ ĐÁP ÁN ĐÚNG: B. ...\\n💡 Giải thích: ...",\n'
                '      "answer_spoken": "Đáp án chính xác là B! Bởi vì ..."\n'
                "    }\n"
                "  ]\n"
                "}"
            )
            try:
                parsed = await self._call_gemini_json(prompt)
                raw_qs = parsed.get("questions") or []
                if isinstance(raw_qs, list) and raw_qs:
                    cmts: List[ThreadCommentItemDTO] = []
                    for idx, q_item in enumerate(raw_qs[:q_count], start=1):
                        q_card = str(q_item.get("question_card") or "").strip()
                        q_sp = str(q_item.get("question_spoken") or self._expand_slang_vi(q_card) or q_card).strip()
                        a_card = str(q_item.get("answer_card") or "").strip()
                        a_sp = str(q_item.get("answer_spoken") or self._expand_slang_vi(a_card) or a_card).strip()
                        if not q_card or not a_card:
                            continue
                        cmts.append(
                            ThreadCommentItemDTO(
                                comment_id=f"quiz_q_{idx:02d}",
                                author_handle=f"@Cau_Do_{idx}",
                                display_name=f"Câu đố #{idx}",
                                raw_text=q_card,
                                display_text=q_card,
                                spoken_vi_text=q_sp,
                                likes_display=f"⏱ {cd_sec}s",
                                voice_profile_id=req.host_voice_id,
                                selected=True,
                            )
                        )
                        cmts.append(
                            ThreadCommentItemDTO(
                                comment_id=f"quiz_a_{idx:02d}",
                                author_handle=f"@Dap_An_{idx}",
                                display_name=f"Đáp án #{idx}",
                                raw_text=a_card,
                                display_text=a_card,
                                spoken_vi_text=a_sp,
                                likes_display="Đáp án",
                                voice_profile_id=req.answer_voice_id,
                                selected=True,
                            )
                        )
                    if cmts:
                        intro_txt = str(
                            parsed.get("intro_hook")
                            or f"Thử thách {cd_sec} giây phản xạ về '{topic}' — Đố bạn trả lời đúng hết {len(cmts) // 2} câu!"
                        ).strip()
                        return ScrapedThreadBundleDTO(
                            source_url="",
                            platform="quiz_321",
                            topic_title=str(parsed.get("topic_title") or f"Đố vui {cd_sec}s: {topic}")[:160],
                            op_author_handle="@Thu_Thach_321",
                            op_display_text=intro_txt,
                            op_spoken_vi_text=self._expand_slang_vi(intro_txt) or intro_txt,
                            op_likes_display=f"{len(cmts) // 2} câu đố",
                            op_replies_display=f"{cd_sec}s/câu",
                            op_voice_profile_id=req.host_voice_id,
                            male_voice_id=req.answer_voice_id,
                            female_voice_id=req.host_voice_id,
                            comments=cmts,
                            used_api_key=True,
                            extraction_note=f"AI đã tạo bộ {len(cmts) // 2} câu đố kèm nhịp đếm ngược {cd_sec}-2-1!",
                        )
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        low_t = topic.lower()
        if req.quiz_category.upper() == "MUSIC_EAR" or any(
            k in low_t for k in ("đàn", "guitar", "violin", "nhạc", "âm")
        ):
            seed_qs = [
                (
                    "Câu 1: Chi tiết nào quyết định tới 70% độ vang ấm của một cây đàn Guitar / Violin gỗ tự nhiên?\nA. Màu sơn bóng bên ngoài\nB. Mặt Top gỗ thịt (Solid Wood)\nC. Bộ khóa lên dây kim loại",
                    "Câu một: Chi tiết nào quyết định tới bảy mươi phần trăm độ vang ấm của một cây đàn gỗ tự nhiên? A: Màu sơn bóng, B: Mặt Top gỗ thịt nguyên tấm, hay C: Bộ khóa lên dây?",
                    "✅ ĐÁP ÁN ĐÚNG: B. Mặt Top gỗ thịt (Solid Wood)\n💡 Mặt gỗ thịt nguyên tấm cộng hưởng trực tiếp với dao động dây đàn và càng chơi lâu tiếng càng mở!",
                    "Đáp án chuẩn là B! Mặt Top gỗ thịt nguyên tấm cộng hưởng trực tiếp với dây đàn và càng chơi lâu âm càng mở.",
                ),
                (
                    "Câu 2: Người mới tập đàn thường bỏ cuộc ở tuần thứ 2 vì lý do kinh điển nào nhất?\nA. Chưa thuộc hết nhạc lý\nB. Đàn chỉnh Action quá cao gây đau đầu ngón tay\nC. Tập mỗi ngày chỉ 15 phút",
                    "Câu hai: Người mới tập đàn hay bỏ cuộc ở tuần thứ hai vì lý do nào nhất? A: Chưa thuộc nhạc lý, B: Dây đàn quá cao gây đau tay, hay C: Chỉ tập mười lăm phút mỗi tối?",
                    "✅ ĐÁP ÁN ĐÚNG: B. Đàn để Action quá cao!\n💡 Chỉ cần căn chỉnh lại độ cao dây êm tay là tập 15–20 phút mỗi tối tiến bộ cực nhanh.",
                    "Đáp án đúng là B! Đàn căn chỉnh độ cao dây êm tay sẽ giúp bạn vượt qua hai tuần đầu nhẹ nhàng hơn rất nhiều.",
                ),
                (
                    "Câu 3: Khi bảo quản đàn gỗ vào mùa nồm ẩm miền Bắc, thói quen nào tốt nhất?\nA. Phơi đàn trực tiếp ngoài nắng gắt\nB. Để đàn trong bao/hộp kèm gói hút ẩm chuyên dụng\nC. Luôn tháo lỏng toàn bộ dây mỗi ngày",
                    "Câu ba: Mùa nồm ẩm thì bảo quản đàn gỗ thế nào là chuẩn nhất? A: Phơi ngoài nắng gắt, B: Cất trong hộp kèm gói hút ẩm, hay C: Tháo lỏng hết dây mỗi ngày?",
                    "✅ ĐÁP ÁN ĐÚNG: B. Để trong hộp kèm gói hút ẩm!\n💡 Giữ độ ẩm ổn định 45–55% giúp mặt gỗ không bị phồng rộp hay cong cần đàn.",
                    "Chính xác là B! Giữ đàn trong hộp kèm gói hút ẩm giúp gỗ luôn ổn định và chuẩn âm.",
                ),
            ]
        else:
            seed_qs = [
                (
                    f"Câu 1 ({topic[:40]}): Trong đám đông khi cả nhóm cùng bật cười, ánh mắt đầu tiên của một người thường vô thức hướng về ai?\nA. Người vừa kể câu chuyện cười đó\nB. Người mà họ có tình cảm đặc biệt nhất\nC. Nhìn xuống điện thoại trên tay",
                    "Câu một: Trong đám đông khi cả nhóm cùng bật cười, ánh mắt đầu tiên của một người vô thức hướng về ai? A: Người kể chuyện, B: Người mà họ thích nhất, hay C: Nhìn xuống điện thoại?",
                    "✅ ĐÁP ÁN ĐÚNG: B. Người họ thương thầm!\n💡 Tâm lý học hành vi chứng minh con người luôn muốn chia sẻ khoảnh khắc vui đầu tiên với người mình để ý nhất.",
                    "Đáp án chính xác là B! Theo tâm lý học, ta luôn vô thức nhìn về người mình để ý nhất ngay khi bật cười.",
                ),
                (
                    "Câu 2: Dấu hiệu tinh tế nào cho thấy đối phương thực sự để tâm đến cuộc trò chuyện với bạn?\nA. Trả lời bằng những từ ngắn gọn 1 chữ\nB. Nhớ chính xác một chi tiết nhỏ bạn từng kể từ nhiều tuần trước\nC. Chỉ nhắn tin khi cần nhờ vả",
                    "Câu hai: Dấu hiệu nào chứng tỏ người ấy thực sự để tâm đến bạn? A: Nhắn cụt một chữ, B: Nhớ rõ chi tiết nhỏ bạn từng kể từ lâu, hay C: Chỉ nhắn khi nhờ việc?",
                    "✅ ĐÁP ÁN ĐÚNG: B. Nhớ chi tiết nhỏ xíu bạn từng nói!\n💡 Người bận mấy cũng sẽ nhớ rất kỹ sở thích nhỏ của người họ trân trọng.",
                    "Đáp án đúng là B! Chỉ khi thật sự để tâm, người ta mới nhớ từng sở thích nhỏ bạn vô tình nhắc tới.",
                ),
                (
                    "Câu 3: Khoảng thời gian nào trong ngày con người dễ nhắn ra những lời thật lòng nhất mà ban ngày hay giấu kín?\nA. 8 giờ sáng đầu tuần\nB. 12 giờ trưa giờ nghỉ\nC. Sau 11 giờ đêm khi không gian tĩnh lặng",
                    "Câu ba: Khung giờ nào con người dễ nói thật lòng mình nhất? A: Tám giờ sáng, B: Mười hai giờ trưa, hay C: Sau mười một giờ đêm?",
                    "✅ ĐÁP ÁN ĐÚNG: C. Sau 11 giờ đêm!\n💡 Khi cơ thể mệt nhẹ và xung quanh yên tĩnh, rào cản lý trí hạ xuống khiến cảm xúc thật dễ lên tiếng nhất.",
                    "Chuẩn xác là C! Sau mười một giờ đêm là lúc cảm xúc thật lên tiếng rõ nhất.",
                ),
            ]

        cmts_fb: List[ThreadCommentItemDTO] = []
        for idx in range(q_count):
            q_c, q_s, a_c, a_s = seed_qs[idx % len(seed_qs)]
            if idx >= len(seed_qs):
                q_c = re.sub(r"^Câu \d+", f"Câu {idx + 1}", q_c)
            cmts_fb.append(
                ThreadCommentItemDTO(
                    comment_id=f"quiz_fb_q_{idx + 1:02d}",
                    author_handle=f"@Cau_Do_{idx + 1}",
                    display_name=f"Câu đố #{idx + 1}",
                    raw_text=q_c,
                    display_text=q_c,
                    spoken_vi_text=q_s,
                    likes_display=f"⏱ {cd_sec}s",
                    voice_profile_id=req.host_voice_id,
                    selected=True,
                )
            )
            cmts_fb.append(
                ThreadCommentItemDTO(
                    comment_id=f"quiz_fb_a_{idx + 1:02d}",
                    author_handle=f"@Dap_An_{idx + 1}",
                    display_name=f"Đáp án #{idx + 1}",
                    raw_text=a_c,
                    display_text=a_c,
                    spoken_vi_text=a_s,
                    likes_display="Đáp án",
                    voice_profile_id=req.answer_voice_id,
                    selected=True,
                )
            )

        intro_fb = f"Thử thách phản xạ {cd_sec} giây về '{topic[:65]}' — Đố bạn trả lời đúng được mấy câu?"
        return ScrapedThreadBundleDTO(
            source_url="",
            platform="quiz_321",
            topic_title=f"Đố vui {cd_sec}s: {topic[:110]}",
            op_author_handle="@Thu_Thach_321",
            op_display_text=intro_fb,
            op_spoken_vi_text=self._expand_slang_vi(intro_fb) or intro_fb,
            op_likes_display=f"{q_count} câu đố",
            op_replies_display=f"{cd_sec}s/câu",
            op_voice_profile_id=req.host_voice_id,
            male_voice_id=req.answer_voice_id,
            female_voice_id=req.host_voice_id,
            comments=cmts_fb,
            used_api_key=False,
            extraction_note=f"Đã tạo bộ {q_count} câu đố phản xạ {cd_sec}-2-1 kèm giải thích đáp án!",
        )

    async def refine_motion_scene(self, req: MotionSceneRefineRequestDTO) -> Dict[str, Any]:
        """Claude Artifact-style natural language single-scene editor: rewrites `MotionSceneSpecDTO`
        (and optionally `vi_text`) from a short Vietnamese prompt.
        """
        instr = req.user_instruction.strip()
        vi_txt = req.vi_text.strip()
        cur_json = req.current_spec.model_dump() if req.current_spec else {}

        if self.has_llm_key:
            prompt = (
                "Bạn là Đạo diễn Motion Graphics (kiểu Claude Artifacts / Remotion / Apple Keynote).\n"
                "Người dùng đang chỉnh sửa trực tiếp 1 phân cảnh đồ họa chuyển động bằng ngôn ngữ tự nhiên.\n"
                f"- Lời dẫn hiện tại (`vi_text`): {vi_txt}\n"
                f"- Cấu hình đồ họa hiện tại (`current_spec`): {json.dumps(cur_json, ensure_ascii=False)}\n"
                f"- Yêu cầu chỉnh sửa của người dùng: {instr}\n\n"
                "Các `template` hợp lệ:\n"
                "- `KINETIC_HOOK`: Chữ động lớn nhấn từ khóa + vòng sóng đồng tâm\n"
                "- `STAT_COUNTER`: Con số khổng lồ chạy tăng dần (`stat_value`, `stat_suffix`) + đồng hồ vòng cung\n"
                "- `BAR_CHART`: Biểu đồ thanh ngang (`items` dạng `[\"Tiêu chí A|95\", \"Tiêu chí B|52\"]`)\n"
                "- `VERSUS_SPLIT`: Bảng đối đầu 2 cột (`left_title`, `right_title`, `left_points`, `right_points`)\n"
                "- `STEP_FLOW`: Sơ đồ tiến trình từng bước đánh số 01-02-03 (`items`)\n"
                "- `SPEC_SPOTLIGHT`: Lưới thẻ thông số Bento sang trọng (`items`)\n\n"
                "Trả về JSON chuẩn:\n"
                "{\n"
                '  "vi_text": "Giữ nguyên lời dẫn (hoặc tinh chỉnh nếu người dùng yêu cầu sửa lời)",\n'
                '  "note": "Mô tả ngắn 1 câu tiếng Việt về thay đổi vừa áp dụng",\n'
                '  "motion_spec": {\n'
                '    "template": "VERSUS_SPLIT",\n'
                '    "badge_text": "...",\n'
                '    "headline": "...",\n'
                '    "subheadline": "...",\n'
                '    "stat_value": 85,\n'
                '    "stat_prefix": "",\n'
                '    "stat_suffix": "%",\n'
                '    "items": ["..."],\n'
                '    "left_title": "...",\n'
                '    "right_title": "...",\n'
                '    "left_points": ["..."],\n'
                '    "right_points": ["..."]\n'
                "  }\n"
                "}"
            )
            try:
                parsed = await self._call_gemini_json(prompt)
                new_vi = str(parsed.get("vi_text") or vi_txt).strip()
                new_spec = _coerce_motion_spec(
                    parsed.get("motion_spec"),
                    new_vi,
                    0,
                    5,
                    req.motion_theme,
                )
                return {
                    "vi_text": new_vi,
                    "motion_spec": new_spec.model_dump(),
                    "note": str(parsed.get("note") or "AI đã cập nhật hoạt ảnh phân cảnh theo yêu cầu!"),
                    "used_api_key": True,
                }
            except Exception:
                if not self.allow_offline_fallback:
                    raise

        # Instant deterministic Vietnamese NLP command parser (works 100% offline in <5ms!)
        low_i = instr.lower()
        base = req.current_spec or infer_motion_spec_for_line(vi_txt, 1, 5, req.motion_theme)

        if any(k in low_i for k in ("so sánh", "đối đầu", "2 cột", "hai cột", "vs", "versus", "khác nhau")):
            tpl = MotionSceneTemplate.VERSUS_SPLIT
            # Extract `A và B` or `A vs B` if mentioned
            vs_m = re.search(r"(?:giữa|cột)\s+([^,.;]+?)\s+(?:và|vs|với)\s+([^,.;]+)", instr, re.IGNORECASE)
            lt = vs_m.group(1).strip()[:36] if vs_m else (base.left_title or "Phương án Chuẩn")
            rt = vs_m.group(2).strip()[:36] if vs_m else (base.right_title or "Phổ thông")
            updated = base.model_copy(
                update={
                    "template": tpl,
                    "theme": req.motion_theme,
                    "badge_text": "SO SÁNH TRỰC QUAN",
                    "left_title": lt,
                    "right_title": rt,
                    "left_points": base.left_points or ["Hiệu quả vượt trội rõ rệt", "Độ ổn định lâu dài", "Trải nghiệm tối ưu"],
                    "right_points": base.right_points or ["Hạn chế về chiều sâu", "Nhanh chững lại", "Khó tối ưu"],
                }
            )
            note = f"Đã chuyển phân cảnh sang Bảng So Sánh 2 Cột ({lt} vs {rt})."
        elif any(k in low_i for k in ("biểu đồ", "cột", "chart", "thanh")):
            updated = base.model_copy(
                update={
                    "template": MotionSceneTemplate.BAR_CHART,
                    "theme": req.motion_theme,
                    "badge_text": "BIỂU ĐỒ ĐỐI CHIẾU",
                    "items": (
                        base.items
                        if (base.items and "|" in base.items[0])
                        else ["Mức tối ưu|95", "Mức tiêu chuẩn|68", "Mức cơ bản|40"]
                    ),
                }
            )
            note = "Đã chuyển phân cảnh sang Biểu Đồ Thanh Chuyển Động."
        elif any(k in low_i for k in ("con số", "phần trăm", "%", "counter", "đếm")) or re.search(r"\b\d+\s*%", low_i):
            num_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(%|lần|phút|giây|x)?", low_i)
            val = float(num_m.group(1).replace(",", ".")) if num_m else base.stat_value
            suf = (num_m.group(2) or "%") if num_m else base.stat_suffix
            updated = base.model_copy(
                update={
                    "template": MotionSceneTemplate.STAT_COUNTER,
                    "theme": req.motion_theme,
                    "badge_text": "CON SỐ ẤN TƯỢNG",
                    "stat_value": val,
                    "stat_suffix": suf,
                }
            )
            note = f"Đã chuyển sang Đồng Hồ Đếm Số Liệu ({val:g}{suf})."
        elif any(k in low_i for k in ("bước", "lộ trình", "quy trình", "sơ đồ", "flow", "cấp độ")):
            updated = base.model_copy(
                update={
                    "template": MotionSceneTemplate.STEP_FLOW,
                    "theme": req.motion_theme,
                    "badge_text": "LỘ TRÌNH TỪNG BƯỚC",
                }
            )
            note = "Đã chuyển phân cảnh sang Sơ Đồ Lộ Trình Từng Bước."
        elif any(k in low_i for k in ("bento", "thông số", "spotlight", "ô thẻ")):
            updated = base.model_copy(
                update={
                    "template": MotionSceneTemplate.SPEC_SPOTLIGHT,
                    "theme": req.motion_theme,
                    "badge_text": "ĐIỂM SÁNG CỐT LÕI",
                }
            )
            note = "Đã chuyển sang Lưới Thẻ Thông Số Bento."
        else:
            updated = base.model_copy(
                update={
                    "template": MotionSceneTemplate.KINETIC_HOOK,
                    "theme": req.motion_theme,
                    "headline": instr[:120] if len(instr) > 12 else (base.headline or vi_txt[:110]),
                }
            )
            note = "Đã cập nhật chữ động Kinetic cho phân cảnh."

        return {
            "vi_text": vi_txt,
            "motion_spec": updated.model_dump(),
            "note": note,
            "used_api_key": False,
        }


