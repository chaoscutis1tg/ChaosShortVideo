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
        for _ in range(80):
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
        assert len(tracks) == 4
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

        for _ in range(110):
            proj_detail = client.get(f"/api/projects/{pid}").json()
            if proj_detail["state"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)

        assert proj_detail["state"] == "COMPLETED", proj_detail.get("error_message")

        # Download & inspect .ZIP bundle
        zip_res = client.get(f"/api/projects/{pid}/download-zip")
        assert zip_res.status_code == 200
        with zipfile.ZipFile(BytesIO(zip_res.content), "r") as zf:
            names = set(zf.namelist())
            assert "Video_Part_01.mp4" in names
            assert "Anh_Bia_Part_01.jpg" in names
            assert "SEO_TikTok_YouTubeShorts.txt" in names





