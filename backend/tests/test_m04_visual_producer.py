"""Unit & I/O Contract Tests for Module M04 (`m04_visual_producer`)."""

from pathlib import Path
from PIL import Image
import pytest

from app.m00_core_contracts import (
    AssetType,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    ClipSpecDTO,
    ExportAspectRatio,
    NarrationLineDTO,
    ProductFramingStyle,
    VisualMode,
)
from app.m04_visual_producer import (
    AIImageKenBurnsProvider,
    ProductPhotoShowcaseProvider,
    VisualProducerFacade,
)


@pytest.mark.asyncio
async def test_m04_visual_producer_offline_and_stock_fallback_contract(tmp_path: Path) -> None:
    """Verify M04 produces valid 1080x1920 VisualAssetListDTO and falls back cleanly on Stock miss."""
    clip = ClipSpecDTO(
        clip_id="clip_vis_01",
        project_id="proj_v1",
        part_number=1,
        source_start_ms=0,
        source_end_ms=10000,
        hook_banner_title="Bí Ẩn Đại Dương | Phần 1",
        lines=[
            NarrationLineDTO(
                seq_index=0,
                rel_start_ms=0,
                rel_end_ms=5000,
                vi_text="Dưới đáy rãnh Mariana có những sinh vật phát sáng kỳ lạ.",
                image_prompt="deep ocean bioluminescent creature vertical 9:16",
                stock_keywords=["ocean", "deep sea"],
            ),
            NarrationLineDTO(
                seq_index=1,
                rel_start_ms=5000,
                rel_end_ms=10000,
                vi_text="Áp suất ở đây lớn gấp hàng nghìn lần mặt đất.",
                image_prompt="submarine exploring dark trench 9:16",
                stock_keywords=["submarine"],
            ),
        ],
    )

    offline_ai = AIImageKenBurnsProvider(allow_remote_fetch=False)
    producer = VisualProducerFacade(ai_image_provider=offline_ai, pexels_api_key="", pixabay_api_key="")

    # Test HYBRID mode (scene 0 uses AI image, scene 1 tries Stock -> auto falls back to AI image)
    visual_list = await producer.produce(clip, VisualMode.HYBRID, out_dir=tmp_path)

    assert visual_list.clip_id == "clip_vis_01"
    assert len(visual_list.items) == 2
    for item in visual_list.items:
        assert item.asset_type == AssetType.IMAGE
        assert item.asset_path.exists()
        assert item.duration_ms == 5000
        with Image.open(item.asset_path) as im:
            assert im.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


@pytest.mark.asyncio
async def test_m04_product_photo_showcase_uncropped_plate_contract(tmp_path: Path) -> None:
    """Verify horizontal & vertical product photos compose onto 1080x1920 plates without chopping."""
    img_wide = tmp_path / "violin_case_wide.jpg"
    Image.new("RGB", (1600, 900), (180, 110, 45)).save(img_wide, format="JPEG")
    img_tall = tmp_path / "violin_tall.jpg"
    Image.new("RGB", (900, 1500), (140, 80, 30)).save(img_tall, format="JPEG")

    clip = ClipSpecDTO(
        clip_id="prd_clip_01",
        project_id="prd_01",
        part_number=1,
        source_start_ms=0,
        source_end_ms=8000,
        hook_banner_title="Violin Avaro S2",
        append_cta_outro=False,
        lines=[
            NarrationLineDTO(
                seq_index=0,
                rel_start_ms=0,
                rel_end_ms=4000,
                vi_text="Mặt top gỗ thịt cho âm vang dày ấm.",
                matched_image_index=0,
            ),
            NarrationLineDTO(
                seq_index=1,
                rel_start_ms=4000,
                rel_end_ms=8000,
                vi_text="Lưng và hông gỗ Maple vân cực đẹp.",
                matched_image_index=1,
            ),
        ],
    )
    facade = VisualProducerFacade()
    vis_list = await facade.produce_product_showcase(
        clip=clip, image_paths=[img_wide, img_tall], out_dir=tmp_path
    )
    assert len(vis_list.items) == 2
    for it in vis_list.items:
        assert it.asset_path.exists()
        with Image.open(it.asset_path) as out_im:
            assert out_im.size == (CANVAS_WIDTH, CANVAS_HEIGHT)


@pytest.mark.asyncio
async def test_m04_uc13_hundred_percent_photo_coverage_velvet_framing_and_45_aspect(
    tmp_path: Path,
) -> None:
    """Verify 8 uploaded photos across 4 spoken lines render all 8 photos on 1080x1350 (4:5) Velvet plates."""
    eight_photos = []
    for idx in range(8):
        p = tmp_path / f"violin_detail_{idx + 1}.jpg"
        Image.new("RGB", (1100, 1400), (120 + idx * 12, 75 + idx * 8, 35)).save(p, format="JPEG")
        eight_photos.append(p)

    clip = ClipSpecDTO(
        clip_id="prd_full_cov_01",
        project_id="prd_cov",
        part_number=1,
        source_start_ms=0,
        source_end_ms=16000,
        hook_banner_title="Violin Avaro S2S",
        append_cta_outro=False,
        lines=[
            NarrationLineDTO(
                seq_index=i,
                rel_start_ms=i * 4000,
                rel_end_ms=(i + 1) * 4000,
                vi_text=f"Chi tiết chế tác số {i + 1} vô cùng tinh xảo.",
                matched_image_index=i,
                callout_label="Nhãn ẩn mặc định",
            )
            for i in range(4)
        ],
    )

    facade = VisualProducerFacade()
    vis_list = await facade.produce_product_showcase(
        clip=clip,
        image_paths=eight_photos,
        out_dir=tmp_path,
        framing_style=ProductFramingStyle.VELVET_DARK_LUXURY,
        aspect_ratio=ExportAspectRatio.RATIO_4_5,
        show_photo_callouts=False,
    )
    assert len(vis_list.items) == 8
    assert sum(it.duration_ms for it in vis_list.items) == 16000
    for it in vis_list.items:
        assert it.asset_path.exists()
        with Image.open(it.asset_path) as out_im:
            assert out_im.size == (1080, 1350)


@pytest.mark.asyncio
async def test_m04_uc14_multiclip_cutout_split_ab_feedback_and_soundwave(tmp_path: Path) -> None:
    """Verify UC-14 interleaved video+photo, GrabCut cutout, Split A/B, Feedback & Soundwave flag."""
    import subprocess
    import wave

    # Photo 1 & Photo 2 with distinct central object for GrabCut
    p1 = tmp_path / "s2.jpg"
    im1 = Image.new("RGB", (800, 1100), (235, 235, 235))
    im1.paste((165, 85, 30), (220, 150, 580, 950))
    im1.save(p1, format="JPEG")

    p2 = tmp_path / "s2s.jpg"
    im2 = Image.new("RGB", (800, 1100), (225, 225, 225))
    im2.paste((130, 65, 25), (210, 140, 590, 960))
    im2.save(p2, format="JPEG")

    fb = tmp_path / "customer_fb.jpg"
    Image.new("RGB", (720, 500), (30, 40, 55)).save(fb, format="JPEG")

    closeup_mp4 = tmp_path / "closeup_maple.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x960:rate=30:duration=2.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(closeup_mp4),
        ],
        check=True,
    )

    demo_wav = tmp_path / "acoustic_test.wav"
    with wave.open(str(demo_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x10\x08\x10\x08" * 44100)

    clip = ClipSpecDTO(
        clip_id="prd_uc14_01",
        project_id="prd_uc14",
        part_number=1,
        source_start_ms=0,
        source_end_ms=15000,
        hook_banner_title="Violin S2 & S2S",
        append_cta_outro=False,
        lines=[
            NarrationLineDTO(seq_index=0, rel_start_ms=0, rel_end_ms=4000, vi_text="Mở màn S2."),
            NarrationLineDTO(seq_index=1, rel_start_ms=4000, rel_end_ms=8000, vi_text="Cận vân gỗ."),
            NarrationLineDTO(
                seq_index=2,
                rel_start_ms=8000,
                rel_end_ms=11000,
                vi_text="Tiếng đàn mộc.",
                is_real_demo_slot=True,
            ),
            NarrationLineDTO(seq_index=3, rel_start_ms=11000, rel_end_ms=15000, vi_text="Bản S2S & đánh giá."),
        ],
    )

    facade = VisualProducerFacade()
    vis_list = await facade.produce_product_showcase(
        clip=clip,
        image_paths=[p1, closeup_mp4, p2],
        out_dir=tmp_path,
        demo_clip_path=demo_wav,
        studio_cutout_enabled=True,
        comparison_split_enabled=True,
        comparison_label_a="Bản S2",
        comparison_label_b="Bản S2S",
        feedback_image_paths=[fb],
        demo_audio_wav=demo_wav,
        soundwave_enabled=True,
    )
    # 3 media items + 1 demo slot + 1 split comparison + 1 feedback card = 6 items totaling 15000ms!
    assert len(vis_list.items) == 6
    assert sum(it.duration_ms for it in vis_list.items) == 15000
    assert any(it.asset_type == AssetType.VIDEO for it in vis_list.items)
    assert any(it.show_soundwave and it.soundwave_audio_path == demo_wav for it in vis_list.items)




