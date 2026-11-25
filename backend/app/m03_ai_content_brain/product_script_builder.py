"""Natural Human Copywriting Engine (Artisan / Consultant / Minimal) for Product Showcase (M03)."""

import asyncio
import io
import json
from pathlib import Path
import re
from typing import Any, List
from PIL import Image, ImageOps

from app.m00_core_contracts import (
    ClipSpecDTO,
    CopywritingTone,
    CutPlanDTO,
    NarrationLineDTO,
    ProductCategory,
    ProductReviewPromptDTO,
    ProjectMode,
    SalesScriptAngle,
    SUPPORTED_VIDEO_EXTENSIONS,
    WordTimestampDTO,
)

from .tiktok_compliance import TikTokShopComplianceChecker

EMOJI_BULLET_CLEAN_RE = re.compile(r"^[•\-*✨🎁📍🚚🎻👗🔥💎✅👉\s]+")
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

ANGLE_ROTATION = (
    SalesScriptAngle.EXPERT_SPEC_REVIEW,
    SalesScriptAngle.BEGINNER_CONSULT,
    SalesScriptAngle.UNBOXING_AND_GIFT,
    SalesScriptAngle.PRICE_COMPARISON_DEAL,
)

TONE_INSTRUCTIONS = {
    CopywritingTone.ARTISAN_STORYTELLER: (
        "VĂN PHONG NGHỆ NHÂN / NGƯỜI CHƠI ĐÀN CHIA SẺ CHÂN THÀNH: Viết câu văn mềm mại, ấm áp, giàu cảm xúc "
        "như một nghệ nhân hoặc người chơi lâu năm đang cầm sản phẩm trên tay trò chuyện với người xem. "
        "Tuyệt đối KHÔNG liệt kê khô khan kiểu gạch đầu dòng, KHÔNG dùng dấu hai chấm (:), KHÔNG để từ tiếng Anh trong ngoặc đơn "
        "như '(Solid Wood)' hay '(Ebony)' (hãy diễn đạt tự nhiên thành 'gỗ thịt nguyên tấm', 'gỗ mun đen mịn'). "
        "Không gào thét bán hàng lố ('siêu phẩm chấn động'), hãy thuyết phục bằng sự tinh tế và trải nghiệm thật."
    ),
    CopywritingTone.MODERN_CONSULTANT: (
        "VĂN PHONG CHUYÊN VIÊN TƯ VẤN THỰC TẾ, GỌN GÀNG: Câu văn ngắn gọn, mạch lạc, đi thẳng vào lợi ích sử dụng thực tế "
        "cho người mua, thân thiện dễ hiểu, chuyển ý tự nhiên giữa các câu, không đọc ký hiệu hay dấu ngoặc kỹ thuật."
    ),
    CopywritingTone.LUXURY_MINIMAL: (
        "VĂN PHONG TỐI GIẢN SANG TRỌNG (ÍT LỜI, TINH TẾ): Viết ít câu hơn (chỉ 4 đến 6 câu ngắn chắt lọc khoảng 10-16 chữ mỗi câu), "
        "ngôn từ thanh lịch như phim giới thiệu thương hiệu thủ công cao cấp, chừa khoảng thở cho âm nhạc và hình ảnh."
    ),
}

ANGLE_INSTRUCTIONS = {
    SalesScriptAngle.EXPERT_SPEC_REVIEW: (
        "Trọng tâm nội dung: Đi từ vẻ đẹp hoàn thiện bên ngoài đến chiều sâu vật liệu chế tác và cảm giác trải nghiệm thực tế."
    ),
    SalesScriptAngle.BEGINNER_CONSULT: (
        "Trọng tâm nội dung: Giúp người mới yên tâm chọn đúng mẫu dễ làm quen, bền bỉ và đã có sẵn đầy đủ phụ kiện đồng bộ."
    ),
    SalesScriptAngle.UNBOXING_AND_GIFT: (
        "Trọng tâm nội dung: Tạo thiện cảm về sự chu đáo khi sản phẩm đi kèm trọn bộ phụ kiện thiết yếu và hỗ trợ kiểm tra tận tâm."
    ),
    SalesScriptAngle.PRICE_COMPARISON_DEAL: (
        "Trọng tâm nội dung: Nêu bật giá trị vượt trội trong tầm ngân sách và điểm khác biệt tinh tế giữa các phiên bản để khách dễ chọn."
    ),
}

CANDIDATE_VISION_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
)


def _words_for_span(text: str, start_ms: int, end_ms: int) -> List[WordTimestampDTO]:
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


def _encode_thumbnail_jpeg(media_path: Path, max_side: int = 512) -> bytes:
    """Encode either an image file OR a mid-clip frame from a short video into compact JPEG bytes."""
    if media_path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
        import cv2

        cap = cv2.VideoCapture(str(media_path))
        try:
            n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if n_frames > 4:
                cap.set(cv2.CAP_PROP_POS_FRAMES, n_frames // 3)
            ok, frame_bgr = cap.read()
        finally:
            cap.release()
        if ok and frame_bgr is not None:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb)
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=78)
            return buf.getvalue()
        # Fallback neutral frame if video container has no decodable frame
        fallback_im = Image.new("RGB", (320, 320), (24, 28, 36))
        buf = io.BytesIO()
        fallback_im.save(buf, format="JPEG", quality=75)
        return buf.getvalue()

    with Image.open(media_path) as raw:
        im = ImageOps.exif_transpose(raw).convert("RGB")
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=78)
        return buf.getvalue()


def _polish_spoken_vietnamese(text: str) -> str:
    """Clean technical punctuation, parenthetical English jargon, and colons so TTS flows naturally."""
    s = EMOJI_BULLET_CLEAN_RE.sub("", text or "").strip()
    # Replace common musical/apparel parenthetical terms with natural spoken equivalents
    replacements = (
        (r"\(\s*solid\s*wood\s*\)", "nguyên tấm tự nhiên"),
        (r"\(\s*ebony\s*\)", "đen mịn cao cấp"),
        (r"\bmặt\s*top\s*:\s*", "Phần mặt đàn làm từ "),
        (r"\blưng\s*và\s*hông\s*:\s*", "kết hợp lưng và hông bằng "),
        (r"\bmặt\s*phím\s*:\s*", "Mặt phím chế tác từ "),
        (r"\bbộ\s*khóa\s*peg\s*:\s*", "đi cùng dàn khóa chỉnh dây bằng "),
        (r"\bgiữ\s*dây\s*:\s*", "Phần đuôi giữ dây có tùy chọn "),
        (r"\btặng\s*trọn\s*bộ\s*phụ\s*kiện\s*:\s*", "Khi nhận đàn bạn đã có sẵn trọn bộ gồm "),
        (r"\bhỗ\s*trợ\s*:\s*", "Đặc biệt cửa hàng luôn hỗ trợ "),
        (r"\bchất\s*liệu\s*:\s*", "Chất liệu sử dụng "),
        (r"\bthiết\s*kế\s*:\s*", "Phom dáng được chăm chút với "),
        (r"\bđường\s*may\s*:\s*", "Từng đường kim mũi chỉ "),
        (r"\bưu\s*đãi\s*:\s*", "Đi kèm quyền lợi "),
    )
    for pat, rep in replacements:
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)

    # Remove remaining parenthetical English snippets & replace colons/semicolons with smooth commas
    s = re.sub(r"\([A-Za-z0-9\s\-/]+\)", "", s)
    s = s.replace(":", ",").replace(";", ",")
    s = re.sub(r"\s*,\s*,+", ", ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,.-")
    if s and s[-1] not in ".!?":
        s += "."
    return s


class ProductSalesScriptBuilder:
    """Builds natural, soulful Vietnamese product scripts (1..4 variants) across all uploaded photos."""

    @classmethod
    async def build(
        cls,
        req: ProductReviewPromptDTO,
        demo_duration_ms: int,
        api_key: str,
        model_name: str,
        allow_fallback: bool = True,
    ) -> CutPlanDTO:
        safe_desc = TikTokShopComplianceChecker.check_and_sanitize(req.raw_description).sanitized_text
        safe_cta = TikTokShopComplianceChecker.check_and_sanitize(req.call_to_action).sanitized_text
        clean_req = req.model_copy(update={"raw_description": safe_desc, "call_to_action": safe_cta})

        if api_key.strip():
            try:
                return await asyncio.to_thread(
                    cls._build_via_gemini_vision_sync,
                    clean_req,
                    demo_duration_ms,
                    api_key.strip(),
                    model_name,
                )
            except Exception:
                if not allow_fallback:
                    raise

        return cls.build_offline_conversion_plan(clean_req, demo_duration_ms)

    @classmethod
    def _resolve_angles_for_variants(cls, req: ProductReviewPromptDTO) -> List[SalesScriptAngle]:
        start_idx = ANGLE_ROTATION.index(req.sales_angle)
        return [
            ANGLE_ROTATION[(start_idx + i) % len(ANGLE_ROTATION)]
            for i in range(req.variant_count)
        ]

    @classmethod
    def _build_via_gemini_vision_sync(
        cls,
        req: ProductReviewPromptDTO,
        demo_duration_ms: int,
        api_key: str,
        model_name: str,
    ) -> CutPlanDTO:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=api_key)
        parts: List[Any] = []
        valid_imgs = [p for p in req.image_paths if p.exists()][:12]

        for idx, img_p in enumerate(valid_imgs):
            note_hint = (
                f" ({req.photo_notes[idx]})"
                if idx < len(req.photo_notes) and req.photo_notes[idx].strip()
                else ""
            )
            parts.append(f"Ảnh #{idx}{note_hint}:")
            parts.append(
                types.Part.from_bytes(
                    data=_encode_thumbnail_jpeg(img_p),
                    mime_type="image/jpeg",
                )
            )

        tone_guide = TONE_INSTRUCTIONS[req.copywriting_tone]
        angles = cls._resolve_angles_for_variants(req)
        angles_desc = "\n".join(
            f"- Phiên bản {i + 1}: {ANGLE_INSTRUCTIONS[ang]} (Mở đầu bằng Ảnh #{i % max(len(valid_imgs), 1)})."
            for i, ang in enumerate(angles)
        )

        demo_note = (
            f"\nCó 1 đoạn âm thanh/video thực tế dài {round(demo_duration_ms / 1000, 1)}s. "
            "Trước câu kết mỗi phiên bản, hãy viết 1 câu chuyển mượt mời người nghe cảm nhận chất âm/hình ảnh thực tế ngay sau đây."
            if demo_duration_ms > 0
            else ""
        )

        num_imgs = max(len(valid_imgs), 1)
        scene_target = (
            "4 đến 6 câu súc tích"
            if req.copywriting_tone == CopywritingTone.LUXURY_MINIMAL
            else f"{min(max(6, num_imgs), 10)} câu mượt mà"
        )
        compare_instruction = (
            f"\n- ĐẶC BIỆT: Bật chế độ so sánh trực quan 2 phiên bản '{req.comparison_left_label}' và "
            f"'{req.comparison_right_label}' — hãy dành ít nhất 1 câu phân biệt tinh tế ưu điểm riêng của 2 bản này."
            if req.comparison_enabled
            else ""
        )
        prompt_txt = (
            "Bạn là người biên tập lời bình video giới thiệu nhạc cụ và sản phẩm thủ công tinh tế bậc nhất.\n"
            f"{tone_guide}\n"
            "TUYỆT ĐỐI KHÔNG dùng các từ sáo rỗng hay vi phạm chính sách như 'siêu phẩm chấn động', 'số 1', 'cam kết 100%', 'kết bạn Zalo'.\n"
            f"Tên sản phẩm: {req.product_name}\n"
            f"Thông tin gốc:\n{req.raw_description}\n"
            f"Lời mời kết bài: {req.call_to_action}\n"
            f"Số ảnh thực tế: {num_imgs} ảnh (đánh số 0..{num_imgs - 1}). Hãy phân bổ lần lượt qua các ảnh để khoe trọn các góc chụp.{demo_note}\n\n"
            f"Hãy viết đúng {len(angles)} phiên bản lời bình ({scene_target}, tổng thời lượng đọc khoảng {req.target_duration_sec}s):\n"
            f"{angles_desc}{compare_instruction}\n\n"
            "Trả về JSON chuẩn:\n"
            '{"variants": [{"part_number": 1, "hook_banner_title": "Tên sản phẩm ngắn gọn tinh tế (không thêm chữ Bản #1)", '
            '"scenes": [{"image_index": 0, "duration_sec": 5.0, '
            '"vi_text": "Câu lời bình tiếng Việt tự nhiên, truyền cảm, liền mạch..."}]}]}'
        )
        parts.append(prompt_txt)

        eff_primary = (
            "gemini-3-flash-preview"
            if not model_name or "gemini-2.5" in model_name
            else model_name
        )
        models_to_try = list(dict.fromkeys([eff_primary, *CANDIDATE_VISION_MODELS]))
        payload = None
        last_exc: Exception | None = None
        for m_try in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=m_try,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        temperature=0.6,
                        response_mime_type="application/json",
                    ),
                )
                raw_txt = (resp.text or "{}").strip()
                m = JSON_FENCE_RE.search(raw_txt)
                if m:
                    raw_txt = m.group(1).strip()
                payload = json.loads(raw_txt)
                if payload:
                    break
            except Exception as exc:
                last_exc = exc
                continue

        if not payload:
            raise RuntimeError(f"Gemini Vision unavailable: {last_exc}")

        variants_raw = payload.get("variants") or []
        if not variants_raw and payload.get("scenes"):
            variants_raw = [payload]
        if not variants_raw:
            raise ValueError("Empty product variants")

        clips: List[ClipSpecDTO] = []
        for v_idx, v_obj in enumerate(variants_raw[: req.variant_count], start=1):
            raw_banner = str(v_obj.get("hook_banner_title") or req.product_name).strip()
            clean_banner = re.sub(r"\s*\|\s*Bản\s*#?\d+", "", raw_banner, flags=re.IGNORECASE).strip()
            scenes = v_obj.get("scenes") or []
            if scenes:
                clips.append(
                    cls._assemble_single_clip(
                        req=req,
                        part_num=v_idx,
                        banner=clean_banner or req.product_name,
                        scenes=scenes,
                        num_imgs=num_imgs,
                        demo_duration_ms=demo_duration_ms,
                    )
                )
        if not clips:
            raise ValueError("No valid clips")
        return CutPlanDTO(project_id=req.project_id, mode=ProjectMode.PRODUCT_SHOWCASE, clips=clips)

    @classmethod
    def build_offline_conversion_plan(
        cls, req: ProductReviewPromptDTO, demo_duration_ms: int = 0
    ) -> CutPlanDTO:
        """Craft natural, flowing human narration offline (zero bullet colons or raw jargon)."""
        num_imgs = max(len(req.image_paths), 1)
        raw_lines = [
            EMOJI_BULLET_CLEAN_RE.sub("", ln).strip()
            for ln in (req.raw_description or "").splitlines()
            if EMOJI_BULLET_CLEAN_RE.sub("", ln).strip()
        ]
        polished_points = [
            _polish_spoken_vietnamese(ln)
            for ln in raw_lines
            if not (ln.isupper() and ln.endswith(":")) and len(ln) >= 6
        ]

        angles = cls._resolve_angles_for_variants(req)
        clips: List[ClipSpecDTO] = []

        for v_idx, ang in enumerate(angles, start=1):
            if ang == SalesScriptAngle.BEGINNER_CONSULT:
                if req.copywriting_tone == CopywritingTone.LUXURY_MINIMAL:
                    hook = f"Khởi đầu trọn vẹn và dễ làm quen ngay từ những nốt đầu tiên cùng {req.product_name}."
                else:
                    hook = (
                        f"Nếu bạn đang tìm một lựa chọn dễ làm quen, âm chuẩn và dùng bền lâu dài "
                        f"thì {req.product_name} là gợi ý rất đáng trải nghiệm."
                    )
            elif ang == SalesScriptAngle.UNBOXING_AND_GIFT:
                hook = (
                    f"Không cần sắm lẻ từng món, trọn bộ {req.product_name} đã được chuẩn bị chu đáo "
                    "để bạn mở hộp là sẵn sàng sử dụng ngay."
                )
            elif ang == SalesScriptAngle.PRICE_COMPARISON_DEAL:
                hook = (
                    f"Trong tầm giá hợp lý, {req.product_name} nổi bật nhờ cấu hình thực chất "
                    "và độ hoàn thiện vượt mong đợi."
                )
            elif req.copywriting_tone == CopywritingTone.LUXURY_MINIMAL:
                hook = f"Vẻ đẹp mộc mạc và chuẩn mực chế tác tinh tế trên {req.product_name}."
            elif req.copywriting_tone == CopywritingTone.MODERN_CONSULTANT:
                hook = f"Cùng điểm nhanh những chi tiết đáng giá nhất làm nên chất lượng của {req.product_name}."
            else:
                # ARTISAN_STORYTELLER + EXPERT_SPEC_REVIEW
                if req.product_category == ProductCategory.MUSICAL_INSTRUMENT:
                    hook = (
                        f"Với những ai yêu âm thanh mộc tự nhiên, cầm trên tay mẫu {req.product_name} "
                        "sẽ cảm nhận ngay sự chỉn chu trong từng thớ gỗ."
                    )
                elif req.product_category == ProductCategory.FASHION_APPAREL:
                    hook = (
                        f"Một thiết kế đẹp không chỉ nằm ở kiểu dáng, mà còn ở cảm giác thoải mái tự nhiên khi khoác lên người mẫu {req.product_name}."
                    )
                else:
                    hook = f"Sự tỉ mỉ trong từng chi tiết nhỏ chính là điều tạo nên thiện cảm ngay từ cái nhìn đầu tiên ở {req.product_name}."

            spoken_beats: List[str] = [hook]
            pts = list(polished_points[:8])
            if ang == SalesScriptAngle.UNBOXING_AND_GIFT and len(pts) > 2:
                gift_pts = [p for p in pts if any(k in p.lower() for k in ("tặng", "phụ kiện", "vĩ", "sách", "quyền lợi"))]
                rest_pts = [p for p in pts if p not in gift_pts]
                pts = gift_pts + rest_pts

            if req.copywriting_tone == CopywritingTone.LUXURY_MINIMAL:
                spoken_beats.extend(pts[:3])
            else:
                spoken_beats.extend(pts if pts else [
                    f"{req.product_name} sở hữu chất liệu chọn lọc kỹ lưỡng cùng độ hoàn thiện đồng đều.",
                    "Sản phẩm đã bao gồm đầy đủ phụ kiện cần thiết để bạn sẵn sàng trải nghiệm ngay.",
                ])

            if req.comparison_enabled and req.comparison_left_label and req.comparison_right_label:
                spoken_beats.append(
                    f"Bạn có thể linh hoạt lựa chọn giữa {req.comparison_left_label} và "
                    f"{req.comparison_right_label} tùy theo gu thẩm mỹ và nhu cầu trải nghiệm riêng."
                )

            if demo_duration_ms > 0:
                spoken_beats.append(
                    "Mời bạn lắng nghe và cảm nhận trực tiếp ngay sau đây."
                )
            spoken_beats.append(_polish_spoken_vietnamese(req.call_to_action))

            avg_sec = max(4.2, req.target_duration_sec / max(len(spoken_beats), 1))
            img_offset = (v_idx - 1) % num_imgs
            scenes = [
                {
                    "image_index": (i + img_offset) % num_imgs,
                    "duration_sec": round(avg_sec, 1),
                    "vi_text": txt,
                }
                for i, txt in enumerate(spoken_beats)
            ]
            clips.append(
                cls._assemble_single_clip(
                    req=req,
                    part_num=v_idx,
                    banner=req.product_name,
                    scenes=scenes,
                    num_imgs=num_imgs,
                    demo_duration_ms=demo_duration_ms,
                )
            )

        return CutPlanDTO(project_id=req.project_id, mode=ProjectMode.PRODUCT_SHOWCASE, clips=clips)

    @staticmethod
    def _assemble_single_clip(
        req: ProductReviewPromptDTO,
        part_num: int,
        banner: str,
        scenes: List[dict],
        num_imgs: int,
        demo_duration_ms: int,
    ) -> ClipSpecDTO:
        lines: List[NarrationLineDTO] = []
        cursor_ms = 0
        insert_demo_at = max(1, len(scenes) - 1) if demo_duration_ms > 0 else -1

        for idx, sc in enumerate(scenes):
            if idx == insert_demo_at:
                demo_dur = min(max(demo_duration_ms, 3000), 25000)
                demo_end = cursor_ms + demo_dur
                demo_caption = "Trải nghiệm thực tế"
                lines.append(
                    NarrationLineDTO(
                        seq_index=len(lines),
                        rel_start_ms=cursor_ms,
                        rel_end_ms=demo_end,
                        vi_text=demo_caption,
                        matched_image_index=0,
                        is_real_demo_slot=True,
                        callout_label="",
                        words=_words_for_span(demo_caption, cursor_ms, demo_end),
                    )
                )
                cursor_ms = demo_end

            raw_vi = str(sc.get("vi_text") or "").strip()
            if not raw_vi:
                continue
            vi_txt = _polish_spoken_vietnamese(
                TikTokShopComplianceChecker.check_and_sanitize(raw_vi).sanitized_text
            )
            dur_ms = max(3200, int(round(float(sc.get("duration_sec") or 5.2) * 1000)))
            img_idx = int(
                sc.get("image_index") if sc.get("image_index") is not None else (idx % num_imgs)
            )
            img_idx = max(0, min(num_imgs - 1, img_idx))
            user_note = (
                req.photo_notes[img_idx].strip()[:65]
                if img_idx < len(req.photo_notes) and req.photo_notes[img_idx].strip()
                else ""
            )
            end_ms = cursor_ms + dur_ms

            lines.append(
                NarrationLineDTO(
                    seq_index=len(lines),
                    rel_start_ms=cursor_ms,
                    rel_end_ms=end_ms,
                    vi_text=vi_txt,
                    matched_image_index=img_idx,
                    is_real_demo_slot=False,
                    callout_label=user_note,
                    words=_words_for_span(vi_txt, cursor_ms, end_ms),
                )
            )
            cursor_ms = end_ms

        return ClipSpecDTO(
            clip_id=f"{req.project_id}_part_{part_num:02d}",
            project_id=req.project_id,
            part_number=part_num,
            source_start_ms=0,
            source_end_ms=max(cursor_ms, 4000),
            hook_banner_title=banner[:90],
            highlight_score=95.0,
            lines=lines,
            append_cta_outro=False,
        )
