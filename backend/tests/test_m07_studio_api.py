"""Integration, End-to-End API & Architectural Boundary Tests for Module M07."""

import ast
from pathlib import Path
import subprocess
import time
from fastapi.testclient import TestClient

from app.m00_core_contracts import StudioSettings
from app.m07_studio_api import create_studio_app

SIBLING_MODULES = {
    "m01_media_ingest",
    "m02_asr_transcription",
    "m03_ai_content_brain",
    "m04_visual_producer",
    "m05_voice_audio_mixer",
    "m06_nvenc_compositor",
}


def test_strict_no_cross_module_imports_in_m01_to_m06() -> None:
    """Enforce AGENTS.md Rule #2: Modules M01..M06 must NEVER import each other or M07."""
    app_root = Path(__file__).resolve().parents[1] / "app"
    forbidden_targets = SIBLING_MODULES | {"m07_studio_api"}

    for mod_name in SIBLING_MODULES:
        mod_dir = app_root / mod_name
        assert mod_dir.exists(), f"Missing module folder: {mod_name}"
        for py_file in mod_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                imported_names: list[str] = []
                if isinstance(node, ast.Import):
                    imported_names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_names.append(node.module)

                for imp in imported_names:
                    for other in forbidden_targets - {mod_name}:
                        assert other not in imp, (
                            f"Architectural violation in {py_file.name}: "
                            f"{mod_name} is forbidden from importing {other} ('{imp}')"
                        )


def test_m07_end_to_end_movie_review_and_render_workflow(tmp_path: Path) -> None:
    """Verify full Movie Clipper lifecycle: Ingest -> SRT ASR -> Review -> Render MP4 + SEO."""
    # 1. Create synthetic 1280x720 episode + foreign SRT
    ep_mp4 = tmp_path / "ep_test.mp4"
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
            "testsrc=size=1280x720:rate=30:duration=3.0",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=400:sample_rate=44100:duration=3.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(ep_mp4),
        ],
        check=True,
    )
    srt_path = tmp_path / "ep_test.srt"
    srt_path.write_text(
        "1\n00:00:00,300 --> 00:00:02,500\nChủ tịch tập đoàn đã chính thức xuất hiện!\n",
        encoding="utf-8",
    )

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test.db",
        gemini_api_key="",
        prefer_nvenc_gpu=True,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        status_res = client.get("/api/system/status")
        assert status_res.status_code == 200
        assert "nvenc_available" in status_res.json()

        voices_res = client.get("/api/voices")
        assert voices_res.status_code == 200
        assert len(voices_res.json()) >= 3

        # Start Movie workflow in Review Mode (`auto_one_click=False`)
        start_res = client.post(
            "/api/movie/start",
            json={
                "project_name": "Phim Ngắn Tổng Tài",
                "source_type": "LOCAL_FILE",
                "path_or_url": str(ep_mp4),
                "external_srt_path": str(srt_path),
                "auto_one_click": False,
            },
        )
        assert start_res.status_code == 200
        pid = start_res.json()["project_id"]

        # Wait briefly for background review preparation
        proj_detail = {}
        for _ in range(30):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("AWAITING_REVIEW", "FAILED"):
                break
            time.sleep(0.2)

        assert proj_detail["state"] == "AWAITING_REVIEW"
        assert len(proj_detail["clips"]) == 1

        # Trigger final GPU Render + SEO Packaging
        render_res = client.post(f"/api/projects/{pid}/render", json={})
        assert render_res.status_code == 200

        for _ in range(60):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.25)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")
        clip_out = proj_detail["clips"][0]
        assert Path(clip_out["output_mp4_path"]).exists()
        assert clip_out["seo"] is not None
        assert "#Shorts" in clip_out["seo"]["yt_shorts_title"]


def test_m07_end_to_end_product_showcase_with_demo_and_badges(tmp_path: Path) -> None:
    """Verify full Mode 3 Product Showcase: Batch Upload -> Acoustic Demo -> Sales Badges -> MP4."""
    from PIL import Image

    photo_a = tmp_path / "avaro_front.jpg"
    photo_b = tmp_path / "avaro_back.jpg"
    Image.new("RGB", (1000, 1300), (195, 115, 42)).save(photo_a, format="JPEG")
    Image.new("RGB", (1200, 900), (155, 88, 34)).save(photo_b, format="JPEG")

    demo_mp4 = tmp_path / "violin_acoustic_test.mp4"
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
            "testsrc=size=720x1280:rate=30:duration=3.2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=3.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(demo_mp4),
        ],
        check=True,
    )

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_prd.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        with open(photo_a, "rb") as fa, open(photo_b, "rb") as fb:
            up_res = client.post(
                "/api/uploads/batch",
                data={"category": "product_photo"},
                files=[
                    ("files", ("avaro_front.jpg", fa, "image/jpeg")),
                    ("files", ("avaro_back.jpg", fb, "image/jpeg")),
                ],
            )
        assert up_res.status_code == 200
        uploaded_items = up_res.json()
        assert len(uploaded_items) == 2

        start_res = client.post(
            "/api/product/start",
            json={
                "product_name": "Violin Avaro S2",
                "product_category": "MUSICAL_INSTRUMENT",
                "raw_description": "• Mặt top gỗ thịt Solid Wood.\n• Tặng trọn bộ phụ kiện.",
                "image_paths": [it["local_path"] for it in uploaded_items],
                "demo_clip_path": str(demo_mp4),
                "target_duration_sec": 20,
                "voice_profile_id": "local_vais_studio",
                "layout_config": {
                    "sales_badge_enabled": True,
                    "sales_price_or_offer": "Tặng Trọn Bộ Phụ Kiện",
                    "sales_contact_info": "Test Đàn Hà Nội • Inbox Nghe Âm Mộc",
                    "qr_code_content": "https://www.sonmusic.vn",
                    "qr_code_label": "Quét xem đàn",
                },
                "photo_notes": ["Mặt Gỗ Thịt Solid", "Lưng Gỗ Maple"],
                "auto_one_click": True,
            },
        )
        assert start_res.status_code == 200
        pid = start_res.json()["project_id"]

        proj_detail = {}
        for _ in range(140):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")
        clip_out = proj_detail["clips"][0]
        assert Path(clip_out["output_mp4_path"]).exists()
        assert Path(clip_out["cover_jpg_path"]).exists()
        assert clip_out["seo"] is not None
        assert clip_out["seo"]["pinned_comment"] != ""
        assert "#reviewsanpham" in clip_out["seo"]["tiktok_hashtags_json"]

        # Verify Product Templates & Compliance Check endpoints
        tpls = client.get("/api/product/templates").json()
        assert len(tpls) >= 2
        saved_tpl = client.post(
            "/api/product/templates",
            json={
                "product_name": "Guitar Acoustic Gỗ Thịt",
                "product_category": "MUSICAL_INSTRUMENT",
                "raw_description": "Âm vang sáng rõ",
            },
        ).json()
        assert saved_tpl["template_id"].startswith("tpl_")
        comp = client.post(
            "/api/product/compliance-check",
            json={"text": "Cam kết 100% rẻ nhất thị trường"},
        ).json()
        assert not comp["is_safe"]


def test_m07_multi_gpu_bgm_pause_resume_delete_and_temp_cleanup(tmp_path: Path) -> None:
    """Verify Multi-GPU discovery, BGM library, Pause/Resume/Cancel/Delete, and Temp Cleaner."""
    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_ctrl.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        # 1. Multi-GPU & Storage status + device switch
        st = client.get("/api/system/status").json()
        assert isinstance(st["gpus"], list)
        assert "disk_free_gb" in st["storage"]

        sw = client.post("/api/system/gpu-select", json={"device_id": "auto"})
        assert sw.status_code == 200
        assert sw.json()["preferred_device"] == "auto"

        # 2. Built-in copyright-free BGM library
        bgm_res = client.get("/api/bgm")
        assert bgm_res.status_code == 200
        tracks = bgm_res.json()
        assert len(tracks) >= 4
        assert Path(tracks[0]["wav_path"]).exists()

        # 3. Start Topic in Review Mode -> Pause/Cancel/Delete + Cleanup Temp
        t_res = client.post(
            "/api/topic/start",
            json={
                "topic_title": "Khám Phá Vũ Trụ Sâu Thẳm",
                "target_duration_sec": 35,
                "bgm_preset_id": "bgm_lofi_story",
                "auto_one_click": False,
            },
        )
        assert t_res.status_code == 200
        pid = t_res.json()["project_id"]

        for _ in range(30):
            d = client.get(f"/api/projects/{pid}").json()
            if d["state"] in ("AWAITING_REVIEW", "FAILED"):
                break
            time.sleep(0.15)
        assert d["state"] == "AWAITING_REVIEW"

        # Create dummy orphan temp folder & verify cleanup frees it safely
        orphan = tmp_path / "work" / "old_completed_job"
        orphan.mkdir(parents=True, exist_ok=True)
        (orphan / "scratch.bin").write_bytes(b"0" * 65536)
        clean_res = client.post("/api/system/cleanup-temp").json()
        assert clean_res["removed_folders"] >= 1
        assert not orphan.exists()

        # Pause -> Cancel -> Delete project
        p_res = client.post(f"/api/projects/{pid}/pause")
        assert p_res.status_code == 200
        assert p_res.json()["state"] == "PAUSED"

        c_res = client.post(f"/api/projects/{pid}/cancel")
        assert c_res.status_code == 200
        assert c_res.json()["state"] == "CANCELLED"

        del_res = client.delete(f"/api/projects/{pid}")
        assert del_res.status_code == 200
        assert client.get(f"/api/projects/{pid}").status_code == 404


def test_m07_uc13_clean_luxury_violin_capcut_slide_45_and_quick_re_edit(tmp_path: Path) -> None:
    """Verify UC-13 clean frame (show_top_banner=False), CapCut transitions, 4:5 & 1:1 export, and Quick Re-Edit."""
    from PIL import Image

    photos = []
    for idx in range(4):
        p = tmp_path / f"violin_lux_{idx + 1}.jpg"
        Image.new("RGB", (960, 1280), (165 - idx * 15, 95, 42 + idx * 10)).save(p, format="JPEG")
        photos.append(str(p))

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_uc13.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        start_res = client.post(
            "/api/product/start",
            json={
                "product_name": "Đàn Violin Avaro S2S",
                "product_category": "MUSICAL_INSTRUMENT",
                "copywriting_tone": "ARTISAN_STORYTELLER",
                "raw_description": "• Mặt top: Gỗ thịt (Solid Wood).\n• Mặt phím: Gỗ mun (Ebony).",
                "image_paths": photos,
                "target_duration_sec": 18,
                "voice_profile_id": "local_vais_studio",
                "subtitle_style": "CINEMA",
                "layout_config": {
                    "aspect_ratio": "4:5",
                    "transition_style": "CAPCUT_SMOOTH_SLIDE",
                    "product_framing": "VELVET_DARK_LUXURY",
                    "show_top_banner": False,
                    "sales_badge_enabled": False,
                    "show_photo_callouts": False,
                },
                "auto_one_click": True,
            },
        )
        assert start_res.status_code == 200
        pid = start_res.json()["project_id"]

        proj_detail = {}
        for _ in range(90):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")
        out_mp4 = Path(proj_detail["clips"][0]["output_mp4_path"])
        assert out_mp4.exists()

        probe_45 = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                str(out_mp4),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert probe_45.stdout.strip() == "1080x1350"

        # Quick Re-Edit & Re-Render on COMPLETED project -> switch to 1:1 STATIC_LOOKBOOK & reversed photos
        re_res = client.post(
            f"/api/projects/{pid}/render",
            json={
                "voice_profile_id": "local_vais_studio",
                "bgm_preset_id": "bgm_luxury_acoustic",
                "audio_config": {
                    "enable_narration": True,
                    "keep_original_audio": False,
                    "bgm_volume": 0.06,
                    "subtitle_style": "NONE",
                },
                "layout_config": {
                    "aspect_ratio": "1:1",
                    "transition_style": "STATIC_LOOKBOOK",
                    "product_framing": "BLURRED_STUDIO_CARD",
                    "show_top_banner": False,
                    "sales_badge_enabled": False,
                    "show_photo_callouts": False,
                },
                "image_paths_override": list(reversed(photos)),
            },
        )
        assert re_res.status_code == 200

        for _ in range(90):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")
        probe_11 = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                str(out_mp4),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert probe_11.stdout.strip() == "1080x1080"


def test_m07_uc14_scraper_brandkit_cutout_soundwave_outro_and_zip(tmp_path: Path) -> None:
    """Verify UC-14 HTML scraper, 13 voices + pitch/speed, Brand Kit, Cutout, Soundwave, Outro & ZIP."""
    from io import BytesIO
    import wave
    import zipfile
    from PIL import Image
    from app.m01_media_ingest import ProductWebScraper

    # 1. Verify ProductWebScraper HTML & JSON-LD parsing
    sample_html = """
    <html><head>
      <meta property="og:image" content="/uploads/violin_main.jpg" />
      <script type="application/ld+json">
        {"@type": "Product", "name": "Violin Avaro S2S Solid", "offers": {"price": "3500000", "priceCurrency": "VND"}}
      </script>
    </head><body>
      <div class="woocommerce-product-details__short-description">
        <ul>
          <li>Mặt đàn gỗ thịt tự nhiên nguyên tấm cho âm vang ấm</li>
          <li>Mặt phím gỗ mun Ebony cao cấp bền bỉ</li>
        </ul>
      </div>
      <div class="product-gallery">
        <img data-large_image="https://shop.example.com/img/detail_1.jpg" src="/logo.png" />
      </div>
    </body></html>
    """
    t_name, t_desc, t_price, t_imgs = ProductWebScraper.parse_html_metadata(
        sample_html, "https://shop.example.com/p/avaro-s2s"
    )
    assert t_name == "Violin Avaro S2S Solid"
    assert "Mặt đàn gỗ thịt" in t_desc
    assert "3500000" in t_price
    assert len(t_imgs) == 2

    # 2. Prepare photos + acoustic audio WAV demo
    p1 = tmp_path / "v_s2.jpg"
    im = Image.new("RGB", (900, 1200), (230, 230, 230))
    im.paste((170, 90, 35), (220, 160, 680, 1040))
    im.save(p1, format="JPEG")

    p2 = tmp_path / "v_s2s.jpg"
    im2 = Image.new("RGB", (900, 1200), (220, 220, 220))
    im2.paste((135, 70, 28), (220, 160, 680, 1040))
    im2.save(p2, format="JPEG")

    acoustic_wav = tmp_path / "violin_tone.wav"
    with wave.open(str(acoustic_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x20\x12\x20\x12" * (44100 * 2))

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_uc14.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        # Check 13 expressive voices + custom speed/pitch preview
        v_list = client.get("/api/voices").json()
        assert len(v_list) >= 13
        prev_res = client.post(
            "/api/voices/preview",
            json={
                "profile_id": "local_vais_studio",
                "sample_text": "Thử độ trầm ấm và tốc độ giọng đọc.",
                "speed_rate": 0.96,
                "pitch_hz": -1.8,
            },
        )
        assert prev_res.status_code == 200
        assert prev_res.json()["audio_url"].endswith(".wav")

        # Save & load Brand Kit
        bk_save = client.post(
            "/api/brand-kit",
            json={
                "brand_name": "Sơn Music Violin",
                "showroom_address": "Showroom Hà Nội",
                "hotline_or_web": "www.sonmusic.vn",
                "subtitle_pos_y": 0.78,
                "subtitle_font_size": 46,
                "outro_card_enabled": True,
            },
        )
        assert bk_save.status_code == 200
        bk_loaded = client.get("/api/brand-kit").json()
        assert bk_loaded["brand_name"] == "Sơn Music Violin"
        assert bk_loaded["subtitle_pos_y"] == 0.78

        # Single-photo Studio Cutout preview
        cut_res = client.post("/api/product/preview-cutout", json={"local_path": str(p1)})
        assert cut_res.status_code == 200
        assert Path(cut_res.json()["local_path"]).exists()

        # Run full Product Showcase in Review mode -> set per-line voice override -> Render with Soundwave + Outro -> Download ZIP!
        st_res = client.post(
            "/api/product/start",
            json={
                "product_name": "Violin Avaro S2 & S2S",
                "product_category": "MUSICAL_INSTRUMENT",
                "copywriting_tone": "ARTISAN_STORYTELLER",
                "raw_description": "• Mặt top gỗ thịt Solid Wood.\n• Giữ dây kim loại bản S2 và gỗ bản S2S.",
                "image_paths": [str(p1), str(p2)],
                "comparison_enabled": True,
                "comparison_left_label": "Bản S2",
                "comparison_right_label": "Bản S2S",
                "demo_clip_path": str(acoustic_wav),
                "target_duration_sec": 16,
                "voice_profile_id": "local_vais_studio",
                "voice_speed_global": 1.02,
                "voice_pitch_global": -1.2,
                "auto_one_click": False,
            },
        )
        assert st_res.status_code == 200
        pid = st_res.json()["project_id"]

        proj_detail = {}
        for _ in range(40):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("AWAITING_REVIEW", "FAILED"):
                break
            time.sleep(0.2)
        assert proj_detail["state"] == "AWAITING_REVIEW"

        # Apply per-line voice speed/pitch override + Luxury Outro Card + Soundwave
        clip0 = proj_detail["clips"][0]
        patched_lines = []
        for idx, ln in enumerate(clip0["lines"]):
            patched_lines.append(
                {
                    "seq_index": ln["seq_index"],
                    "rel_start_ms": ln["rel_start_ms"],
                    "rel_end_ms": ln["rel_end_ms"],
                    "original_text": ln["original_text"] or "",
                    "vi_text": ln["vi_narration_text"],
                    "matched_image_index": ln["matched_image_index"],
                    "is_real_demo_slot": bool(ln["is_real_demo_slot"]),
                    "callout_label": "",
                    "voice_speed_override": 0.94 if idx == 0 else None,
                    "voice_pitch_override": -2.0 if idx == 0 else None,
                }
            )

        r_res = client.post(
            f"/api/projects/{pid}/render",
            json={
                "voice_profile_id": "local_vais_studio",
                "bgm_preset_id": "bgm_luxury_acoustic",
                "audio_config": {
                    "enable_narration": True,
                    "keep_original_audio": False,
                    "bgm_volume": 0.05,
                    "subtitle_style": "CINEMA",
                    "subtitle_pos_y": 0.78,
                    "subtitle_font_size": 46,
                },
                "layout_config": {
                    "aspect_ratio": "9:16",
                    "transition_style": "CAPCUT_DISSOLVE",
                    "product_framing": "VELVET_DARK_LUXURY",
                    "show_top_banner": False,
                    "sales_badge_enabled": False,
                    "studio_cutout_enabled": True,
                    "soundwave_enabled": True,
                    "comparison_split_enabled": True,
                    "comparison_label_a": "Bản S2",
                    "comparison_label_b": "Bản S2S",
                    "subtitle_pos_y": 0.78,
                    "subtitle_font_size": 46,
                    "outro_card_enabled": True,
                    "outro_brand_title": "Sơn Music Violin",
                    "outro_subtitle": "Showroom Hà Nội",
                    "outro_contact_line": "www.sonmusic.vn",
                    "outro_duration_ms": 2000,
                },
                "clips": [
                    {
                        "clip_id": clip0["clip_id"],
                        "part_number": clip0["part_number"],
                        "source_start_ms": clip0["start_ms"],
                        "source_end_ms": clip0["end_ms"],
                        "hook_banner_title": clip0["hook_banner_title"],
                        "append_cta_outro": False,
                        "lines": patched_lines,
                    }
                ],
            },
        )
        assert r_res.status_code == 200

        for _ in range(200):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")

        # Download & inspect .ZIP bundle
        zip_res = client.get(f"/api/projects/{pid}/download-zip")
        assert zip_res.status_code == 200
        assert f"ChaosShortVideo_{pid}.zip" in zip_res.headers.get("content-disposition", "")
        with zipfile.ZipFile(BytesIO(zip_res.content), "r") as zf:
            names = set(zf.namelist())
            assert "Video_Part_01.mp4" in names
            assert "Anh_Bia_Part_01.jpg" in names
            assert "SEO_TikTok_YouTubeShorts.txt" in names


def test_m07_uc15_nvenc_trimmer_cover_snapshot_lanqr_and_backup(tmp_path: Path) -> None:
    """Verify UC-15: NVENC detection, Media Trimmer, True 1080p Snapshot, Cover Studio, LAN QR & Backup ZIP."""
    from io import BytesIO
    import wave
    import zipfile
    from PIL import Image

    # Prepare sample photo + 4.0s acoustic WAV
    sample_jpg = tmp_path / "violin_hero.jpg"
    im = Image.new("RGB", (900, 1200), (225, 220, 210))
    im.paste((165, 88, 32), (240, 180, 660, 1020))
    im.save(sample_jpg, format="JPEG")

    raw_wav = tmp_path / "long_acoustic.wav"
    with wave.open(str(raw_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x18\x0e\x18\x0e" * (44100 * 4))

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_uc15.db",
        gemini_api_key="",
        prefer_nvenc_gpu=True,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        # 1. Verify Hardware NVENC Status & LAN QR PNG endpoint (Items 1 & 7)
        st = client.get("/api/system/status").json()
        assert "nvenc_available" in st

        qr_res = client.get("/api/system/lan-qr?url=http://192.168.1.200:8000")
        assert qr_res.status_code == 200
        assert qr_res.headers["content-type"] == "image/png"
        assert len(qr_res.content) > 200

        # 2. Upload WAV & Trim best highlight 1.0s -> 2.8s (Item 3)
        with open(raw_wav, "rb") as f_wav:
            up_res = client.post(
                "/api/uploads/file",
                data={"category": "product_demo"},
                files={"file": ("long_acoustic.wav", f_wav, "audio/wav")},
            )
        assert up_res.status_code == 200
        up_json = up_res.json()
        assert up_json["duration_ms"] >= 3800

        trim_res = client.post(
            "/api/media/trim",
            json={"local_path": up_json["local_path"], "start_ms": 1000, "end_ms": 2800},
        )
        assert trim_res.status_code == 200
        trim_json = trim_res.json()
        assert 1500 <= trim_json["duration_ms"] <= 2100
        assert Path(trim_json["local_path"]).exists()

        # 3. True 1080p Frame Snapshot & Cover Studio Preview (Items 4 & 5)
        with open(sample_jpg, "rb") as f_img:
            img_up = client.post(
                "/api/uploads/file",
                data={"category": "product_photo"},
                files={"file": ("violin_hero.jpg", f_img, "image/jpeg")},
            ).json()

        snap_video = client.post(
            "/api/preview/render-frame",
            json={
                "active_tab": "product",
                "sample_media_url": img_up["media_url"],
                "banner_title": "Violin Gỗ Thịt S2S",
                "sample_subtitle": "Âm vang dày ấm tự nhiên.",
                "preview_as_cover": False,
                "layout_config": {
                    "aspect_ratio": "9:16",
                    "product_framing": "VELVET_DARK_LUXURY",
                    "subtitle_pos_y": 0.80,
                    "subtitle_font_size": 50,
                },
            },
        )
        assert snap_video.status_code == 200
        assert snap_video.json()["width"] == 1080
        assert snap_video.json()["height"] == 1920

        snap_cover = client.post(
            "/api/preview/render-frame",
            json={
                "active_tab": "product",
                "sample_media_url": img_up["media_url"],
                "banner_title": "Test Âm Violin S2S",
                "preview_as_cover": True,
                "layout_config": {
                    "aspect_ratio": "9:16",
                    "cover_style": "BOLD_HOOK",
                    "cover_headline": "Test Âm Violin S2S",
                    "cover_badge_text": "Nghe Thử Âm Mộc",
                },
            },
        )
        assert snap_cover.status_code == 200
        assert snap_cover.json()["image_url"].endswith(".jpg")

        # 4. Store Backup Export & Restore .ZIP (Item 8)
        client.post(
            "/api/brand-kit",
            json={
                "brand_name": "Chaos Luthier Studio",
                "showroom_address": "Hà Nội",
                "hotline_or_web": "www.sonmusic.vn",
                "outro_card_enabled": True,
            },
        )
        client.post(
            "/api/product/templates",
            json={
                "template_id": "tpl_custom_s2s",
                "product_name": "Đàn Violin Avaro S2S Tuyển Chọn",
                "product_category": "MUSICAL_INSTRUMENT",
                "raw_description": "Gỗ thịt tự nhiên lâu năm.",
            },
        )
        exp_res = client.get("/api/system/backup-export")
        assert exp_res.status_code == 200
        assert "ChaosShortVideo_StoreBackup.zip" in exp_res.headers.get("content-disposition", "")

        with zipfile.ZipFile(BytesIO(exp_res.content), "r") as zf:
            assert "manifest.json" in zf.namelist()

        # Delete template, then restore from backup ZIP and confirm it comes back!
        client.delete("/api/product/templates/tpl_custom_s2s")
        imp_res = client.post(
            "/api/system/backup-import",
            files={"file": ("ChaosShortVideo_StoreBackup.zip", exp_res.content, "application/zip")},
        )
        assert imp_res.status_code == 200
        assert imp_res.json()["templates_restored"] >= 1
        assert imp_res.json()["brand_kit_restored"] == 1
        tpl_ids = {t["template_id"] for t in client.get("/api/product/templates").json()}
        assert "tpl_custom_s2s" in tpl_ids

        # 5. AI Short Brief Analyzer & Expander (`POST /api/brain/expand-brief`)
        exp_topic = client.post(
            "/api/brain/expand-brief",
            json={
                "mode": "TOPIC_VIDEO",
                "raw_title": "4 cấp độ chơi đàn Guitar",
                "short_brief": "Làm sao biết mình đang ở trình độ nào từ mới tập bấm hợp âm tới solo",
                "target_duration_sec": 75,
                "part_count": 1,
            },
        )
        assert exp_topic.status_code == 200
        exp_data = exp_topic.json()
        assert len(exp_data["refined_title"]) >= 8
        assert len(exp_data["expanded_description"]) >= 40
        assert exp_data["recommended_voice_id"] != ""
        assert exp_data["recommended_bgm_id"] != ""

        # 6. Parent Project Groups (`Dự án cha -> Dự án con`)
        grp_res = client.post(
            "/api/project-groups",
            json={
                "name": "Series Giải Mã Lịch Sử Cổ Đại",
                "description": "Chuỗi video ngắn 60-90s cho kênh YouTube Shorts",
                "color_tag": "#10b981",
            },
        )
        assert grp_res.status_code == 200
        gid = grp_res.json()["group_id"]
        groups_list = client.get("/api/project-groups").json()
        assert any(g["group_id"] == gid for g in groups_list)
        client.delete(f"/api/project-groups/{gid}")


def test_m07_uc16_threads_extract_bg_library_multivoice_and_floating_cards(tmp_path: Path) -> None:
    """Verify UC-16 Threads & Comment Studio: teen-code expansion, BG Video Library, multi-voice Pop SFX & looped 9:16 card render."""
    bg_mp4 = tmp_path / "chill_bg_2s.mp4"
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
            "testsrc=size=720x1280:rate=30:duration=2.0",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=320:sample_rate=44100:duration=2.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(bg_mp4),
        ],
        check=True,
    )

    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_threads.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)

    with TestClient(studio_app) as client:
        # 1. Extract & Curate pasted Threads post + teen-code expansion + strict 2 main voices (Nam & Nữ)
        cmt_photo = tmp_path / "guitar_fingers.jpg"
        from PIL import Image as _PILImage

        _PILImage.new("RGB", (800, 600), (210, 145, 95)).save(cmt_photo, format="JPEG")

        ext_res = client.post(
            "/api/threads/extract",
            json={
                "post_url": "",
                "raw_pasted_text": (
                    "@minhanh: Mn ơi 26 tuổi mới tập đàn Guitar thì có muộn ko ạ? 🙂\n\n"
                    "@tuankiet: Ko hề muộn nha b, tập 20 phút mỗi tối là chơi đc ngay! =))\n\n"
                    "@linhchi: Chơi đàn thì chấp nhận xấu tay nhaa 🤣\n\n"
                    "@hoangnam: Đi làm cty về tập đàn cực kỳ xả stress luôn."
                ),
                "max_comments": 3,
                "filter_vibe": "FUNNY_VIRAL",
                "expand_slang_and_translate": True,
                "anonymize_handles": False,
                "multi_voice_cast": True,
                "host_voice_id": "threads_nu_chinh",
                "male_voice_id": "threads_nam_chinh",
                "female_voice_id": "threads_nu_chinh",
            },
        )
        assert ext_res.status_code == 200
        bundle = ext_res.json()
        assert "mọi người" in bundle["op_spoken_vi_text"].lower()
        assert "không" in bundle["op_spoken_vi_text"].lower()
        assert "=))" not in bundle["comments"][0]["spoken_vi_text"]
        assert len(bundle["comments"]) == 3

        # Assert STRICTLY ONLY the 2 main voices (threads_nam_chinh & threads_nu_chinh) are used!
        assigned_voices = {c["voice_profile_id"] for c in bundle["comments"]}
        assert assigned_voices.issubset({"threads_nam_chinh", "threads_nu_chinh"})
        assert bundle["comments"][0]["voice_profile_id"] == "threads_nam_chinh"
        assert bundle["comments"][1]["voice_profile_id"] == "threads_nu_chinh"

        # Attach a real comment photo on Comment #2 and switch to pre-bundled offline voice for fast unit test
        bundle["comments"][1]["attached_image_path"] = str(cmt_photo)
        bundle["op_voice_profile_id"] = "local_vais_studio"
        for c_item in bundle["comments"]:
            c_item["voice_profile_id"] = "local_vais_studio"

        # 2. Upload Background Video to persistent Kho Video Nền
        with open(bg_mp4, "rb") as f_bg:
            up_bg = client.post(
                "/api/threads/bg-videos/upload",
                data={"title": "Lái xe đêm mưa chill", "category_tag": "Chill"},
                files={"file": ("chill_bg_2s.mp4", f_bg, "video/mp4")},
            )
        assert up_bg.status_code == 200
        saved_bg = up_bg.json()
        assert saved_bg["bg_id"].startswith("bg_")
        lib_list = client.get("/api/threads/bg-videos").json()
        assert len(lib_list) == 1

        # 3. True 1080p Threads Card Snapshot preview
        snap_th = client.post(
            "/api/preview/render-frame",
            json={
                "active_tab": "threads",
                "banner_title": "Thảo luận Threads",
                "sample_subtitle": "Học đàn Guitar tuổi 26 hoàn toàn không muộn!",
                "layout_config": {"threads_card_theme": "FROSTED_GLASS", "threads_bg_dim": 0.32},
            },
        )
        assert snap_th.status_code == 200
        assert snap_th.json()["width"] == 1080

        # 4. Run full end-to-end THREADS_TOPIC render (2s BG video auto-loops across OP + 2 comments!)
        start_th = client.post(
            "/api/threads/start",
            json={
                "bundle": bundle,
                "bg_source_type": "LOCAL_FILE",
                "bg_path_or_url": saved_bg["local_path"],
                "keep_bg_audio": True,
                "bg_audio_volume": 0.10,
                "append_cta_comment": "",
                "enable_card_pop_sfx": True,
                "voice_profile_id": "local_vais_studio",
                "voice_speed_global": 1.25,
                "bgm_preset_id": "bgm_lofi_story",
                "bgm_volume": 0.05,
                "subtitle_style": "NONE",
                "layout_config": {
                    "aspect_ratio": "9:16",
                    "show_top_banner": False,
                    "threads_card_theme": "LIGHT_THREADS",
                    "threads_anonymize_handles": False,
                    "threads_bg_dim": 0.30,
                },
                "auto_one_click": True,
            },
        )
        assert start_th.status_code == 200
        thr_pid = start_th.json()["project_id"]

        thr_detail = {}
        for _ in range(140):
            thr_detail = client.get(f"/api/projects/{thr_pid}").json()
            if thr_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert thr_detail["state"] == "COMPLETED", thr_detail.get("error_message")
        assert thr_detail["mode"] == "THREADS_TOPIC"
        thr_clip = thr_detail["clips"][0]
        out_mp4 = Path(thr_clip["output_mp4_path"])
        assert out_mp4.exists() and out_mp4.stat().st_size > 4096
        assert Path(thr_clip["cover_jpg_path"]).exists()
        assert thr_clip["seo"] is not None


import pytest


@pytest.mark.asyncio
async def test_m03_m05_m07_smart_sfx_keyword_highlight_reddit_vi_and_publish_tracker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify:
    1. Smart Keyword Highlight injects gold/cyan `.ass` tags on numbers & impact words (`3 năm`, `bí mật`).
    2. Micro-SFX synthesizers produce clean stereo WAVs (`shimmer`, `whoosh`, `click`).
    3. English Reddit bundle auto-translates to Vietnamese even without a Gemini API key.
    4. `/api/projects/{id}/publish-status` and `/api/topic/batch-start` persist & enqueue cleanly.
    """
    from app.m00_core_contracts import (
        ScrapedThreadBundleDTO,
        SubtitleStyle,
        ThreadCommentItemDTO,
        ThreadsExtractRequestDTO,
        WordTimestampDTO,
    )
    from app.m03_ai_content_brain.free_translator import FreeVietnameseTranslator
    from app.m03_ai_content_brain.gemini_service import GeminiContentBrainService
    from app.m05_voice_audio_mixer.ass_subtitle_builder import (
        ASSSubtitleBuilder,
        TimedSubtitleEvent,
    )
    from app.m05_voice_audio_mixer.audio_mixer import (
        _build_hook_shimmer_sfx_wav,
        _build_photo_click_sfx_wav,
        _build_soft_whoosh_sfx_wav,
    )

    # 1. Smart Keyword Highlight on ASS subtitles
    ass_out = tmp_path / "kw_test.ass"
    ASSSubtitleBuilder.build_ass_file(
        events=[
            TimedSubtitleEvent(
                start_ms=0,
                end_ms=3200,
                text="Mình giữ bí mật này suốt 3 năm trời không ai biết.",
                words=[
                    WordTimestampDTO(word="Mình", start_ms=0, end_ms=400),
                    WordTimestampDTO(word="giữ", start_ms=400, end_ms=800),
                    WordTimestampDTO(word="bí", start_ms=800, end_ms=1100),
                    WordTimestampDTO(word="mật", start_ms=1100, end_ms=1500),
                    WordTimestampDTO(word="3", start_ms=1500, end_ms=1900),
                    WordTimestampDTO(word="năm", start_ms=1900, end_ms=2500),
                ],
            )
        ],
        style=SubtitleStyle.CINEMA,
        out_ass_path=ass_out,
        smart_keyword_highlight=True,
    )
    ass_txt = ass_out.read_text(encoding="utf-8-sig")
    assert "{\\c&H0024D8FF&}3{\\c&HFFFFFF&}" in ass_txt
    assert "{\\c&H0024D8FF&}năm{\\c&HFFFFFF&}" in ass_txt

    # 2. Micro-SFX WAV synthesis
    for fn, name in (
        (_build_hook_shimmer_sfx_wav, "shimmer.wav"),
        (_build_soft_whoosh_sfx_wav, "whoosh.wav"),
        (_build_photo_click_sfx_wav, "click.wav"),
    ):
        p = fn(tmp_path / name)
        assert p.exists() and p.stat().st_size > 1024

    # 3. Auto-translate English Reddit bundle -> Vietnamese without Gemini API key
    async def _fake_tr(texts, source_lang="auto", concurrency=8):
        return [f"Bản dịch tiếng Việt tự nhiên: {t[:40]}" for t in texts]

    monkeypatch.setattr(FreeVietnameseTranslator, "translate_lines", _fake_tr)
    brain = GeminiContentBrainService(api_key="", allow_offline_fallback=True)
    en_reddit = ScrapedThreadBundleDTO(
        source_url="https://www.reddit.com/r/AskReddit/comments/abc123/test/",
        platform="reddit",
        topic_title="What small habit changed your life completely?",
        op_author_handle="@curious_op",
        op_display_text="What small daily habit under ten minutes changed your life completely?",
        op_spoken_vi_text="What small daily habit under ten minutes changed your life completely?",
        comments=[
            ThreadCommentItemDTO(
                comment_id="rd_1",
                author_handle="@guitar_guy",
                raw_text="Practicing acoustic guitar for fifteen minutes every night before bed.",
                display_text="Practicing acoustic guitar for fifteen minutes every night before bed.",
                spoken_vi_text="Practicing acoustic guitar for fifteen minutes every night before bed.",
            )
        ],
    )
    curated_vi = await brain.curate_threads_bundle(
        raw_bundle=en_reddit,
        req=ThreadsExtractRequestDTO(
            post_url=en_reddit.source_url,
            max_comments=1,
            expand_slang_and_translate=True,
        ),
        available_voice_ids=["threads_nu_chinh", "threads_nam_chinh"],
    )
    assert "Bản dịch tiếng Việt" in curated_vi.topic_title
    assert "Bản dịch tiếng Việt" in curated_vi.op_display_text
    assert "Bản dịch tiếng Việt" in curated_vi.comments[0].display_text

    # 4. Publish Status Tracker & Batch Topic Queue API
    test_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_pub_batch.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=test_settings)
    with TestClient(studio_app) as client:
        batch_res = client.post(
            "/api/topic/batch-start",
            json={
                "items": [
                    "Mẹo tập hợp âm chặn Guitar | Cách đặt ngón cái không bị mỏi cổ tay",
                    "Cách bảo quản đàn Violin mùa nồm ẩm | Giữ hộp đàn khô ráo chuẩn âm",
                ],
                "target_duration_sec": 35,
                "rotate_lofi_bgm": True,
                "auto_one_click": False,
            },
        )
        assert batch_res.status_code == 200
        b_data = batch_res.json()
        assert b_data["queued_count"] == 2
        first_pid = b_data["project_ids"][0]

        pub_res = client.post(
            f"/api/projects/{first_pid}/publish-status",
            json={
                "published_channels": ["TIKTOK", "YOUTUBE_SHORTS"],
                "published_note": "Đã lên lịch 20h tối nay",
            },
        )
        assert pub_res.status_code == 200
        assert pub_res.json()["published_channels"] == ["TIKTOK", "YOUTUBE_SHORTS"]

        p_list = client.get("/api/projects").json()
        matched = next(p for p in p_list if p["id"] == first_pid)
        assert matched["published_channels"] == ["TIKTOK", "YOUTUBE_SHORTS"]
        assert matched["published_note"] == "Đã lên lịch 20h tối nay"


@pytest.mark.asyncio
async def test_m07_real_progress_console_logs_and_tts_circuit_breaker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify:
    1. Live Console ring-buffer (`live_progress['logs']`) records every real stage (`[TTS`, `[Threads Card`,
       `[Dựng 9:16]`, `[FFmpeg]`, `[SEO]`) with strictly monotonic overall percentages reaching 100.0%.
    2. `GeminiEmotionalTTSProvider` trips its 90s quota/timeout circuit-breaker and falls back immediately
       without hanging on `429 RESOURCE_EXHAUSTED`.
    """
    from app.m00_core_contracts import AudioChunkDTO, VoiceProfileDTO, VoiceTier, WordTimestampDTO
    from app.m05_voice_audio_mixer.tts_providers import (
        EdgeTTSProvider,
        GeminiEmotionalTTSProvider,
        write_synthetic_speech_placeholder,
    )

    # 1. Verify GeminiEmotionalTTSProvider quota circuit-breaker never hangs
    GeminiEmotionalTTSProvider._quota_cooldown_until = 0.0
    fake_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_prog.db",
        gemini_api_key="AIza_fake_test_key_for_circuit_breaker",
        prefer_nvenc_gpu=False,
    )

    class _InstantFallbackEdge(EdgeTTSProvider):
        async def synthesize(self, text: str, profile: VoiceProfileDTO, out_wav_path: Path) -> AudioChunkDTO:
            dur = write_synthetic_speech_placeholder(out_wav_path, text, 1.0)
            return AudioChunkDTO(
                audio_path=out_wav_path,
                duration_ms=dur,
                word_timestamps=[WordTimestampDTO(word="Thử", start_ms=0, end_ms=dur)],
            )

    gem_tts = GeminiEmotionalTTSProvider(edge_fallback=_InstantFallbackEdge(), settings=fake_settings)
    calls = {"gemini": 0}

    def _raise_429(enhanced: str, profile: VoiceProfileDTO, out_wav_path: Path) -> int:
        calls["gemini"] += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for gemini-2.5-flash-preview-tts")

    monkeypatch.setattr(gem_tts, "_call_gemini_tts_sync", _raise_429)
    prof = VoiceProfileDTO(
        profile_id="gem_test",
        display_name="Nữ Cảm Xúc",
        tier=VoiceTier.GEMINI_EMOTIONAL,
        voice_id_or_sample_path="Kore",
    )
    c1 = await gem_tts.synthesize("Câu thứ nhất kiểm tra ngắt mạch.", prof, tmp_path / "tts_cb_1.wav")
    c2 = await gem_tts.synthesize("Câu thứ hai bỏ qua ngay không treo.", prof, tmp_path / "tts_cb_2.wav")
    assert c1.audio_path.exists() and c2.audio_path.exists()
    assert calls["gemini"] == 1  # Second sentence skipped Gemini immediately via cooldown!
    GeminiEmotionalTTSProvider._quota_cooldown_until = 0.0

    # 2. Verify full end-to-end Real Progress Bar & Live Console logs on THREADS_TOPIC
    bg_mp4 = tmp_path / "console_bg.mp4"
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
            "testsrc=size=360x640:rate=30:duration=1.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=320:sample_rate=44100:duration=1.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(bg_mp4),
        ],
        check=True,
    )

    real_settings = StudioSettings(
        workspace_root=tmp_path,
        assets_dir=tmp_path / "assets",
        work_dir=tmp_path / "work",
        outputs_dir=tmp_path / "outputs",
        sqlite_db_path=tmp_path / "work" / "test_prog.db",
        gemini_api_key="",
        prefer_nvenc_gpu=False,
    )
    studio_app = create_studio_app(custom_settings=real_settings)
    with TestClient(studio_app) as client:
        ext = client.post(
            "/api/threads/extract",
            json={
                "post_url": "",
                "raw_pasted_text": (
                    "@crush_story: Những hành động nhỏ của Crush khiến tim đập loạn nhịp\n\n"
                    "@ban_tre_1: Nhớ nhất lúc trời mưa bạn ấy nghiêng ô về phía mình suốt cả quãng đường."
                ),
                "max_comments": 1,
                "expand_slang_and_translate": True,
                "host_voice_id": "local_vais_studio",
                "male_voice_id": "local_vais_studio",
                "female_voice_id": "local_vais_studio",
            },
        ).json()
        ext["op_voice_profile_id"] = "local_vais_studio"
        for item in ext["comments"]:
            item["voice_profile_id"] = "local_vais_studio"

        st = client.post(
            "/api/threads/start",
            json={
                "bundle": ext,
                "bg_source_type": "LOCAL_FILE",
                "bg_path_or_url": str(bg_mp4),
                "voice_profile_id": "local_vais_studio",
                "voice_speed_global": 1.3,
                "bgm_preset_id": "",
                "subtitle_style": "NONE",
                "auto_one_click": True,
            },
        )
        assert st.status_code == 200
        pid = st.json()["project_id"]

        detail = {}
        for _ in range(120):
            detail = client.get(f"/api/projects/{pid}").json()
            if detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.25)

        assert detail["state"] == "COMPLETED", detail.get("error_message")
        live = detail.get("live_progress") or {}
        assert live.get("percent") == 100.0
        logs = live.get("logs") or []
        assert len(logs) >= 6

        joined_msgs = "\n".join(entry.get("text", "") for entry in logs)
        assert "[TTS 1/" in joined_msgs
        assert "[Threads Card" in joined_msgs
        assert "[Dựng 9:16]" in joined_msgs
        assert "[FFmpeg" in joined_msgs
        assert "[SEO]" in joined_msgs

        pcts = [float(entry.get("percent", 0.0)) for entry in logs]
        assert pcts == sorted(pcts), f"Expected strictly non-decreasing progress percentages, got {pcts}"
        assert pcts[-1] == 100.0










