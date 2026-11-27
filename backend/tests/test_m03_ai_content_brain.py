"""Unit & I/O Contract Tests for Module M03 (`m03_ai_content_brain`)."""

from pathlib import Path
import pytest

from app.m00_core_contracts import (
    BriefExpandRequestDTO,
    CopywritingTone,
    CutConfigDTO,
    CutStrategy,
    ProductCategory,
    ProductReviewPromptDTO,
    ProjectMode,
    RawTranscriptSegmentDTO,
    SalesScriptAngle,
    TopicPromptDTO,
    TranscriptResultDTO,
)
from app.m03_ai_content_brain import (
    FreeVietnameseTranslator,
    GeminiContentBrainService,
    TikTokShopComplianceChecker,
)


@pytest.mark.asyncio
async def test_m03_free_vietnamese_translator_translates_chinese() -> None:
    """Verify foreign Chinese lines translate into Vietnamese without any API key."""
    out = await FreeVietnameseTranslator.translate_lines(
        ["豬排是蠻厚實的", "然後面衣也酥脆"], source_lang="zh"
    )
    assert len(out) == 2
    assert out[0] != "豬排是蠻厚實的"


@pytest.mark.asyncio
async def test_m03_topic_script_generation_contract() -> None:
    """Verify TopicPromptDTO produces unified CutPlanDTO matching M04 & M05 input."""
    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    req = TopicPromptDTO(
        project_id="proj_topic_01",
        topic_title="3 Bí Mật Tâm Lý Học Đám Đông",
        key_points="Hiệu ứng hào quang\nTâm lý bầy đàn\nCách giữ tỉnh táo",
        target_duration_sec=75,
        part_count=2,
    )
    plan = await brain.build_topic_clips(req)

    assert plan.mode == ProjectMode.TOPIC_VIDEO
    assert len(plan.clips) == 2
    assert plan.clips[0].part_number == 1
    assert plan.clips[0].duration_ms >= 60000
    assert len(plan.clips[0].lines) >= 4
    assert plan.clips[0].lines[0].image_prompt != ""

    seo = await brain.build_seo(plan.clips[0])
    assert "#Shorts" in seo.yt_shorts_title
    assert len(seo.tiktok_hashtags) >= 3


@pytest.mark.asyncio
async def test_m03_smart_cutter_splits_65_to_120s_without_mid_sentence_cuts() -> None:
    """Prove M02 TranscriptResultDTO splits cleanly into 65-120s parts at sentence boundaries."""
    segments = []
    # Build 210 seconds (3m30s) of dialogue in 10-second sentences -> should yield 2 or 3 parts
    for i in range(21):
        s_ms = i * 10000 + 200
        e_ms = (i + 1) * 10000 - 400
        punct = "!" if i in (8, 16) else "."
        segments.append(
            RawTranscriptSegmentDTO(
                seq_index=i,
                start_ms=s_ms,
                end_ms=e_ms,
                raw_text=f"Câu thoại kịch tính số {i + 1} của bộ phim{punct}",
            )
        )

    tr = TranscriptResultDTO(media_id="med_01", detected_language="vi", segments=segments)
    cfg = CutConfigDTO(
        cut_strategy=CutStrategy.SEQUENTIAL_PARTS,
        min_clip_sec=65,
        max_clip_sec=120,
        series_title="Tổng Tài Trở Lại",
    )

    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    plan = await brain.translate_and_split_movie(
        transcript=tr,
        config=cfg,
        project_id="proj_movie_01",
        total_duration_ms=210000,
    )

    assert plan.mode == ProjectMode.MOVIE_CLIPPER
    assert len(plan.clips) >= 2
    assert 65000 <= plan.clips[0].duration_ms <= 120500
    assert "Phần 1" in plan.clips[0].hook_banner_title
    # First clip should snap right after cliffhanger index 8 ("!") at ~90s
    assert plan.clips[0].lines[-1].vi_text.endswith("!")


@pytest.mark.asyncio
async def test_m03_product_showcase_script_and_demo_slot_contract(tmp_path: Path) -> None:
    """Verify Violin Avaro S2 specs + photos + demo duration produce valid PRODUCT_SHOWCASE CutPlanDTO."""
    img1 = tmp_path / "violin_1.jpg"
    img2 = tmp_path / "violin_2.jpg"
    img1.write_bytes(b"fake")
    img2.write_bytes(b"fake")

    req = ProductReviewPromptDTO(
        project_id="prd_violin_01",
        product_name="Đàn Violin Avaro S2 & S2S",
        product_category=ProductCategory.MUSICAL_INSTRUMENT,
        raw_description=(
            "✨ CHI TIẾT CẤU HÌNH AVARO S2:\n"
            "• Mặt top: Gỗ thịt (Solid Wood).\n"
            "• Lưng và hông: Gỗ Maple cao cấp.\n"
            "• Mặt phím: Gỗ mun (Ebony).\n"
            "🎁 Tặng kèm vĩ kéo, nhựa thông, kê vai KPE."
        ),
        image_paths=[img1, img2],
        target_duration_sec=45,
    )
    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    plan = await brain.build_product_review_clips(req, demo_duration_ms=5000)

    assert plan.mode == ProjectMode.PRODUCT_SHOWCASE
    assert len(plan.clips) == 1
    lines = plan.clips[0].lines
    assert len(lines) >= 4
    demo_lines = [ln for ln in lines if ln.is_real_demo_slot]
    assert len(demo_lines) == 1
    assert demo_lines[0].rel_end_ms - demo_lines[0].rel_start_ms == 5000

    seo = await brain.build_seo(plan.clips[0], mode_label=ProjectMode.PRODUCT_SHOWCASE.value)
    assert "#reviewsanpham" in seo.tiktok_hashtags
    assert seo.pinned_comment != ""


@pytest.mark.asyncio
async def test_m03_tiktok_shop_compliance_and_multi_variant_ab_angles(tmp_path: Path) -> None:
    """Verify TikTok Shop policy sanitizer and multi-variant A/B angle script generation."""
    risky = "Đàn số 1 Việt Nam, cam kết 100%, nhắn Zalo hoặc chuyển khoản trước để giữ hàng!"
    rep = TikTokShopComplianceChecker.check_and_sanitize(risky)
    assert not rep.is_safe
    assert rep.safety_score < 100
    assert len(rep.issues) >= 3
    assert "số 1 việt nam" not in rep.sanitized_text.lower()

    img1 = tmp_path / "p1.jpg"
    img2 = tmp_path / "p2.jpg"
    img3 = tmp_path / "p3.jpg"
    img1.write_bytes(b"1")
    img2.write_bytes(b"2")
    img3.write_bytes(b"3")

    req = ProductReviewPromptDTO(
        project_id="prd_ab_01",
        product_name="Violin Avaro S2S",
        product_category=ProductCategory.MUSICAL_INSTRUMENT,
        sales_angle=SalesScriptAngle.BEGINNER_CONSULT,
        variant_count=3,
        raw_description="• Mặt gỗ thịt Solid Wood.\n• Tặng kèm vĩ kéo và kê vai.",
        image_paths=[img1, img2, img3],
        photo_notes=["Mặt Gỗ Thịt Solid", "Vân Lưng Maple", "Trọn Bộ Phụ Kiện"],
        target_duration_sec=35,
    )
    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    plan = await brain.build_product_review_clips(req, demo_duration_ms=0)
    assert len(plan.clips) == 3
    # Opening Hook lines across the 3 variants should have distinct copy & rotated starting photos
    assert plan.clips[0].lines[0].vi_text != plan.clips[1].lines[0].vi_text
    assert plan.clips[0].lines[0].matched_image_index != plan.clips[1].lines[0].matched_image_index
    assert plan.clips[0].lines[0].callout_label != ""


@pytest.mark.asyncio
async def test_m03_uc13_natural_copywriting_tones_strip_colons_and_jargon(tmp_path: Path) -> None:
    """Verify UC-13 CopywritingTone produces natural spoken Vietnamese without colons or '| Bản #1'."""
    imgs = [tmp_path / f"v_{i}.jpg" for i in range(4)]
    for im in imgs:
        im.write_bytes(b"img")

    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    for tone in (
        CopywritingTone.ARTISAN_STORYTELLER,
        CopywritingTone.MODERN_CONSULTANT,
        CopywritingTone.LUXURY_MINIMAL,
    ):
        req = ProductReviewPromptDTO(
            project_id=f"prd_tone_{tone.value.lower()}",
            product_name="Đàn Violin Avaro S2 & S2S",
            product_category=ProductCategory.MUSICAL_INSTRUMENT,
            copywriting_tone=tone,
            raw_description=(
                "• Mặt top: Gỗ thịt (Solid Wood).\n"
                "• Lưng và hông: Gỗ Maple cao cấp.\n"
                "• Mặt phím: Gỗ mun (Ebony).\n"
                "• Bộ khóa Peg: Gỗ cao cấp 100%."
            ),
            image_paths=imgs,
            target_duration_sec=35,
        )
        plan = await brain.build_product_review_clips(req, demo_duration_ms=0)
        clip = plan.clips[0]
        assert "Bản #" not in clip.hook_banner_title
        for ln in clip.lines:
            assert ":" not in ln.vi_text
            assert "(Solid Wood)" not in ln.vi_text
            assert "(Ebony)" not in ln.vi_text
            assert ln.callout_label == ""


@pytest.mark.asyncio
async def test_m03_expand_short_brief_topic_and_product_contracts() -> None:
    """Verify short title/brief expands into full structured Topic & Product briefs matching DTO contracts."""
    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)

    topic_res = await brain.expand_short_brief(
        BriefExpandRequestDTO(
            mode=ProjectMode.TOPIC_VIDEO,
            raw_title="Tin nhắn lúc 2 giờ sáng",
            short_brief="Nhận được tin nhắn từ tương lai dặn đừng mở cửa phòng",
            target_duration_sec=80,
            part_count=1,
        )
    )
    assert len(topic_res.refined_title) >= 10
    assert len(topic_res.expanded_description.splitlines()) >= 5
    assert topic_res.recommended_voice_id == "edge_bong_dem_horror"
    assert topic_res.recommended_bgm_id == "bgm_drama_tension"
    assert topic_res.visual_direction != ""

    prod_res = await brain.expand_short_brief(
        BriefExpandRequestDTO(
            mode=ProjectMode.PRODUCT_SHOWCASE,
            raw_title="Violin Avaro S2",
            short_brief="Đàn gỗ thịt tự nhiên cho người mới tập, âm ấm",
            product_category=ProductCategory.MUSICAL_INSTRUMENT,
            target_duration_sec=55,
        )
    )
    assert len(prod_res.refined_title) >= 10
    assert "Avaro S2" in prod_res.expanded_description
    assert prod_res.recommended_sales_angle == SalesScriptAngle.EXPERT_SPEC_REVIEW
    assert prod_res.recommended_cta != ""





