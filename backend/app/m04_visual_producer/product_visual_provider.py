"""Luxury Product Photo & Multi-Clip Showcase Composer (M04).

Supports:
- 100% media coverage across interleaved photos & close-up video clips
- OpenCV GrabCut Studio Subject Cutout (`studio_cutout_enabled`)
- Side-by-side Split-Screen A vs B Comparison (`comparison_split_enabled`)
- Customer Feedback Social Proof floating cards (`feedback_image_paths`)
- Acoustic Soundwave flagging for real instrument audio/video demos
"""

import asyncio
from pathlib import Path
import subprocess
from typing import List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.m00_core_contracts import (
    AssetType,
    ClipSpecDTO,
    ExportAspectRatio,
    MotionEffect,
    NarrationLineDTO,
    ProductFramingStyle,
    ProgressCallback,
    SceneVisualItemDTO,
    SUPPORTED_VIDEO_EXTENSIONS,
    TARGET_FPS,
    VisualAssetListDTO,
    VisualProducerError,
    resolve_aspect_dimensions,
)


def _load_plate_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        (
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        )
        if bold
        else (
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        )
    )
    for fp in candidates:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                continue
    return ImageFont.load_default()


def extract_studio_subject_rgba(pil_img: Image.Image) -> Image.Image:
    """Isolate central product subject (e.g. Violin, Guitar, Apparel) from cluttered room
    backgrounds using downscaled OpenCV GrabCut + edge-color prior + feathered alpha.
    """
    rgba = pil_img.convert("RGBA")
    # If image already contains a meaningful transparent background, preserve it directly!
    alpha_extrema = rgba.getchannel("A").getextrema()
    if alpha_extrema and alpha_extrema[0] < 30:
        return rgba

    rgb_np = np.array(rgba.convert("RGB"))
    orig_h, orig_w = rgb_np.shape[:2]
    if orig_w < 32 or orig_h < 32:
        return rgba

    max_side = 420
    scale = min(1.0, max_side / float(max(orig_w, orig_h)))
    work_w = max(24, int(round(orig_w * scale)))
    work_h = max(24, int(round(orig_h * scale)))
    small_bgr = cv2.resize(
        cv2.cvtColor(rgb_np, cv2.COLOR_RGB2BGR), (work_w, work_h), interpolation=cv2.INTER_AREA
    )

    mask = np.full((work_h, work_w), cv2.GC_PR_BGD, dtype=np.uint8)
    rx = max(2, int(work_w * 0.06))
    ry = max(2, int(work_h * 0.04))
    rw = max(8, work_w - 2 * rx)
    rh = max(8, work_h - 2 * ry)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(
            small_bgr,
            mask,
            (rx, ry, rw, rh),
            bgd_model,
            fgd_model,
            3,
            cv2.GC_INIT_WITH_RECT,
        )
        fg_bin = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        # Ensure foreground covers a reasonable area (12%..94%); otherwise keep clean full card
        fg_ratio = float(np.count_nonzero(fg_bin)) / float(work_w * work_h)
        if fg_ratio < 0.10 or fg_ratio > 0.96:
            return rgba

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_clean = cv2.morphologyEx(fg_bin, cv2.MORPH_CLOSE, kernel)
        alpha_full = cv2.resize(fg_clean, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        alpha_smooth = cv2.GaussianBlur(alpha_full, (5, 5), 0)

        out_np = np.dstack((rgb_np, alpha_smooth))
        return Image.fromarray(out_np, mode="RGBA")
    except Exception:
        return rgba


def _build_velvet_spotlight_backdrop(canvas_w: int, canvas_h: int) -> Image.Image:
    """Create luxury smoked-obsidian velvet backdrop with warm amber luthier spotlight."""
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (12, 14, 19, 255))
    glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = canvas_w // 2, canvas_h // 2
    r_max = int(min(canvas_w, canvas_h) * 0.48)
    gd.ellipse(
        [(cx - r_max, cy - r_max), (cx + r_max, cy + r_max)],
        fill=(78, 56, 34, 105),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=95))
    return Image.alpha_composite(canvas, glow)


class ProductPhotoShowcaseProvider:
    """Composes real product photos & interleaved short clips onto uncropped studio plates."""

    @classmethod
    def create_studio_cutout_file(cls, src_img: Path, dst_png: Path) -> Path:
        """Run Studio Subject Cutout on a single uploaded photo and save transparent PNG."""
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_img) as raw:
            oriented = ImageOps.exif_transpose(raw)
            cutout = extract_studio_subject_rgba(oriented)
            cutout.save(dst_png, format="PNG")
        return dst_png

    @classmethod
    async def build_showcase_visuals(
        cls,
        clip: ClipSpecDTO,
        image_paths: List[Path],
        out_dir: Path,
        demo_clip_path: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        framing_style: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD,
        aspect_ratio: ExportAspectRatio = ExportAspectRatio.RATIO_9_16,
        show_photo_callouts: bool = False,
        studio_cutout_enabled: bool = False,
        comparison_split_enabled: bool = False,
        comparison_label_a: str = "",
        comparison_label_b: str = "",
        feedback_image_paths: Optional[List[Path]] = None,
        demo_audio_wav: Optional[Path] = None,
        soundwave_enabled: bool = True,
    ) -> VisualAssetListDTO:
        valid_media = [p for p in image_paths if p.exists()]
        if not valid_media:
            raise VisualProducerError("Không tìm thấy tệp ảnh hoặc video sản phẩm hợp lệ nào.")

        valid_feedback = [p for p in (feedback_image_paths or []) if p.exists()]
        photo_only_list = [
            p for p in valid_media if p.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS
        ]

        canvas_w, canvas_h = resolve_aspect_dimensions(aspect_ratio)
        vis_dir = out_dir / clip.clip_id / "product_visuals"
        vis_dir.mkdir(parents=True, exist_ok=True)

        demo_is_video = (
            demo_clip_path is not None
            and demo_clip_path.exists()
            and demo_clip_path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        )
        has_demo_wave = bool(
            soundwave_enabled and demo_audio_wav is not None and demo_audio_wav.exists()
        )

        # Build visual beat plan guaranteeing 100% of uploaded photos & clips appear sequentially!
        beat_plan = cls._build_full_photo_beat_plan(clip.lines, len(valid_media))

        # Inject optional A/B Split Comparison & Customer Feedback beats without altering total duration_ms!
        beat_plan = cls._inject_special_beats_preserving_duration(
            beat_plan=beat_plan,
            enable_compare=bool(comparison_split_enabled and len(photo_only_list) >= 2),
            enable_feedback=bool(valid_feedback),
        )

        items: List[SceneVisualItemDTO] = []
        total = max(len(beat_plan), 1)

        for idx, (beat_kind, media_idx, dur_ms, callout_txt) in enumerate(beat_plan):
            if beat_kind == "DEMO":
                if demo_is_video and demo_clip_path is not None:
                    framed_mp4 = vis_dir / f"prod_demo_{idx:04d}.mp4"
                    await asyncio.to_thread(
                        cls._frame_demo_video,
                        demo_clip_path,
                        framed_mp4,
                        dur_ms,
                        canvas_w,
                        canvas_h,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=idx,
                            asset_path=framed_mp4,
                            asset_type=AssetType.VIDEO,
                            duration_ms=dur_ms,
                            motion_effect=MotionEffect.NONE,
                            show_soundwave=has_demo_wave,
                            soundwave_audio_path=demo_audio_wav if has_demo_wave else None,
                        )
                    )
                else:
                    # Audio-only real acoustic test (.mp3/.wav): show hero photo + live golden soundwave!
                    hero_img = photo_only_list[0] if photo_only_list else valid_media[0]
                    plate_png = vis_dir / f"prod_acoustic_{idx:04d}.png"
                    await asyncio.to_thread(
                        cls.compose_uncropped_plate,
                        hero_img,
                        plate_png,
                        "",
                        framing_style,
                        canvas_w,
                        canvas_h,
                        studio_cutout_enabled,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=idx,
                            asset_path=plate_png,
                            asset_type=AssetType.IMAGE,
                            duration_ms=dur_ms,
                            motion_effect=MotionEffect.NONE,
                            show_soundwave=has_demo_wave,
                            soundwave_audio_path=demo_audio_wav if has_demo_wave else None,
                        )
                    )
            elif beat_kind == "COMPARE" and len(photo_only_list) >= 2:
                comp_png = vis_dir / f"prod_compare_{idx:04d}.png"
                await asyncio.to_thread(
                    cls.compose_split_comparison_plate,
                    photo_only_list[0],
                    photo_only_list[1],
                    comp_png,
                    comparison_label_a or "Phiên bản A",
                    comparison_label_b or "Phiên bản B",
                    canvas_w,
                    canvas_h,
                    studio_cutout_enabled,
                )
                items.append(
                    SceneVisualItemDTO(
                        seq_index=idx,
                        asset_path=comp_png,
                        asset_type=AssetType.IMAGE,
                        duration_ms=dur_ms,
                        motion_effect=MotionEffect.ZOOM_IN,
                    )
                )
            elif beat_kind == "FEEDBACK" and valid_feedback:
                fb_png = vis_dir / f"prod_feedback_{idx:04d}.png"
                backdrop_ref = photo_only_list[0] if photo_only_list else valid_feedback[0]
                await asyncio.to_thread(
                    cls.compose_feedback_proof_plate,
                    valid_feedback[:2],
                    backdrop_ref,
                    fb_png,
                    canvas_w,
                    canvas_h,
                )
                items.append(
                    SceneVisualItemDTO(
                        seq_index=idx,
                        asset_path=fb_png,
                        asset_type=AssetType.IMAGE,
                        duration_ms=dur_ms,
                        motion_effect=MotionEffect.ZOOM_IN,
                    )
                )
            else:
                chosen_media = valid_media[media_idx % len(valid_media)]
                if chosen_media.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    framed_clip = vis_dir / f"prod_clip_{idx:04d}.mp4"
                    await asyncio.to_thread(
                        cls._frame_demo_video,
                        chosen_media,
                        framed_clip,
                        dur_ms,
                        canvas_w,
                        canvas_h,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=idx,
                            asset_path=framed_clip,
                            asset_type=AssetType.VIDEO,
                            duration_ms=dur_ms,
                            motion_effect=MotionEffect.NONE,
                        )
                    )
                else:
                    plate_png = vis_dir / f"prod_plate_{idx:04d}.png"
                    eff_callout = callout_txt if show_photo_callouts else ""
                    await asyncio.to_thread(
                        cls.compose_uncropped_plate,
                        chosen_media,
                        plate_png,
                        eff_callout,
                        framing_style,
                        canvas_w,
                        canvas_h,
                        studio_cutout_enabled,
                    )
                    plate_motions = (
                        MotionEffect.ZOOM_IN,
                        MotionEffect.PAN_RIGHT,
                        MotionEffect.ZOOM_OUT,
                        MotionEffect.PAN_LEFT,
                        MotionEffect.PAN_UP,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=idx,
                            asset_path=plate_png,
                            asset_type=AssetType.IMAGE,
                            duration_ms=dur_ms,
                            motion_effect=plate_motions[idx % len(plate_motions)],
                        )
                    )

            if on_progress:
                pct = round(((idx + 1) / total) * 100.0, 1)
                on_progress(
                    "GENERATING_ASSETS",
                    pct,
                    f"Đã dàn trang cảnh sản phẩm ({idx + 1}/{total})",
                )

        return VisualAssetListDTO(clip_id=clip.clip_id, items=items)

    @staticmethod
    def _inject_special_beats_preserving_duration(
        beat_plan: List[Tuple[str, int, int, str]],
        enable_compare: bool,
        enable_feedback: bool,
    ) -> List[Tuple[str, int, int, str]]:
        """Split a spacious normal beat to insert COMPARE and/or FEEDBACK plates while keeping
        exact millisecond total duration AND keeping 100% of original MEDIA beats intact!
        """
        out = list(beat_plan)
        for special_kind, prefer_end in (("COMPARE", False), ("FEEDBACK", True)):
            if special_kind == "COMPARE" and not enable_compare:
                continue
            if special_kind == "FEEDBACK" and not enable_feedback:
                continue

            # Find a MEDIA beat >= 2800ms to split cleanly in half
            candidates = [
                i for i, b in enumerate(out) if b[0] == "MEDIA" and b[2] >= 2600
            ]
            if not candidates:
                # Fallback: pick longest MEDIA beat
                media_idxs = [i for i, b in enumerate(out) if b[0] == "MEDIA"]
                if not media_idxs:
                    continue
                target_i = max(media_idxs, key=lambda idx: out[idx][2])
                if out[target_i][2] < 1600:
                    continue
            else:
                target_i = candidates[-1] if prefer_end else candidates[len(candidates) // 2]

            kind, m_idx, orig_dur, tag = out[target_i]
            first_dur = max(800, int(orig_dur * 0.52))
            second_dur = max(800, orig_dur - first_dur)
            # Adjust so first_dur + second_dur == orig_dur strictly
            first_dur = orig_dur - second_dur
            out[target_i : target_i + 1] = [
                (kind, m_idx, first_dur, tag),
                (special_kind, 0, second_dur, ""),
            ]
        return out

    @staticmethod
    def _build_full_photo_beat_plan(
        lines: List[NarrationLineDTO], num_imgs: int
    ) -> List[Tuple[str, int, int, str]]:
        """Return list of `(beat_kind, media_idx, duration_ms, callout_label)` ensuring 100% of
        uploaded media (`0..num_imgs-1`) are showcased across the spoken timeline.
        """
        non_demo_lines = [ln for ln in lines if not ln.is_real_demo_slot]
        if num_imgs <= len(non_demo_lines):
            result: List[Tuple[str, int, int, str]] = []
            seq_cursor = 0
            for ln in lines:
                dur = max(800, ln.rel_end_ms - ln.rel_start_ms)
                if ln.is_real_demo_slot:
                    result.append(("DEMO", 0, dur, ""))
                else:
                    if seq_cursor < num_imgs:
                        pick = seq_cursor
                        seq_cursor += 1
                    else:
                        pick = (
                            ln.matched_image_index
                            if ln.matched_image_index is not None
                            else (seq_cursor % num_imgs)
                        )
                        seq_cursor += 1
                    result.append(("MEDIA", pick % num_imgs, dur, ln.callout_label))
            return result

        blocks: List[Tuple[bool, int, List[NarrationLineDTO]]] = []
        cur_spoken: List[NarrationLineDTO] = []
        for ln in lines:
            dur = max(800, ln.rel_end_ms - ln.rel_start_ms)
            if ln.is_real_demo_slot:
                if cur_spoken:
                    blocks.append(
                        (
                            False,
                            sum(max(800, x.rel_end_ms - x.rel_start_ms) for x in cur_spoken),
                            cur_spoken,
                        )
                    )
                    cur_spoken = []
                blocks.append((True, dur, [ln]))
            else:
                cur_spoken.append(ln)
        if cur_spoken:
            blocks.append(
                (
                    False,
                    sum(max(800, x.rel_end_ms - x.rel_start_ms) for x in cur_spoken),
                    cur_spoken,
                )
            )

        total_spoken_ms = max(1, sum(b[1] for b in blocks if not b[0]))
        spoken_block_indices = [i for i, b in enumerate(blocks) if not b[0]]
        img_cursor = 0
        plan: List[Tuple[str, int, int, str]] = []

        for b_i, (is_demo, b_dur_ms, b_lines) in enumerate(blocks):
            if is_demo:
                plan.append(("DEMO", 0, b_dur_ms, ""))
                continue
            is_last_spoken = b_i == spoken_block_indices[-1]
            if is_last_spoken:
                n_photos_here = max(1, num_imgs - img_cursor)
            else:
                n_photos_here = max(1, int(round(num_imgs * (b_dur_ms / float(total_spoken_ms)))))
                n_photos_here = min(n_photos_here, max(1, num_imgs - img_cursor - 1))

            base_ms = max(900, b_dur_ms // n_photos_here)
            rem_ms = b_dur_ms - base_ms * (n_photos_here - 1)
            note_lookup = {
                (ln.matched_image_index or 0): ln.callout_label
                for ln in b_lines
                if ln.callout_label
            }
            for k in range(n_photos_here):
                d_k = max(800, rem_ms if k == n_photos_here - 1 else base_ms)
                p_idx = img_cursor % num_imgs
                plan.append(("MEDIA", p_idx, d_k, note_lookup.get(p_idx, "")))
                img_cursor += 1

        return plan

    @staticmethod
    def compose_uncropped_plate(
        src_img: Path,
        dst_png: Path,
        callout_label: str = "",
        framing_style: ProductFramingStyle = ProductFramingStyle.BLURRED_STUDIO_CARD,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        studio_cutout_enabled: bool = False,
    ) -> Path:
        """Compose a product photo onto `(canvas_w, canvas_h)` in the chosen luxury style."""
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_img) as raw:
            fg = ImageOps.exif_transpose(raw).convert("RGBA")

        has_pre_alpha = fg.getchannel("A").getextrema()[0] < 30
        use_cutout = studio_cutout_enabled or has_pre_alpha
        if studio_cutout_enabled and not has_pre_alpha:
            fg = extract_studio_subject_rgba(fg)
            use_cutout = fg.getchannel("A").getextrema()[0] < 30

        if use_cutout:
            # Isolated Subject Studio Mode: Place cutout cleanly over Velvet Obsidian + Warm Spotlight
            canvas = _build_velvet_spotlight_backdrop(canvas_w, canvas_h)
            max_fg_w = int(canvas_w * 0.88)
            max_fg_h = int(canvas_h * 0.76)
            scale = min(max_fg_w / max(fg.width, 1), max_fg_h / max(fg.height, 1))
            new_w = max(1, int(round(fg.width * scale)))
            new_h = max(1, int(round(fg.height * scale)))
            fg_scaled = fg.resize((new_w, new_h), Image.Resampling.LANCZOS)

            x_pos = (canvas_w - new_w) // 2
            y_pos = (canvas_h - new_h) // 2 - int(canvas_h * 0.03)

            # Soft silhouette drop shadow derived from the subject's own alpha channel!
            alpha_ch = fg_scaled.getchannel("A")
            sil = Image.new("RGBA", (new_w + 48, new_h + 48), (0, 0, 0, 0))
            black_layer = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 175))
            sil.paste(black_layer, (24, 28), alpha_ch)
            sil = sil.filter(ImageFilter.GaussianBlur(radius=18))
            canvas.alpha_composite(sil, (max(0, x_pos - 24), max(0, y_pos - 16)))
            canvas.alpha_composite(fg_scaled, (x_pos, y_pos))
        elif framing_style == ProductFramingStyle.FULL_BLEED_LUXURY:
            fitted = ImageOps.fit(
                fg.convert("RGB"), (canvas_w, canvas_h), method=Image.Resampling.LANCZOS
            ).convert("RGBA")
            grad = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grad)
            fade_h = int(canvas_h * 0.28)
            for y in range(fade_h):
                alpha = int(145 * (y / max(fade_h - 1, 1)) ** 1.4)
                gd.line(
                    [(0, canvas_h - fade_h + y), (canvas_w, canvas_h - fade_h + y)],
                    fill=(8, 10, 14, alpha),
                )
            canvas = Image.alpha_composite(fitted, grad)
            x_pos, y_pos, new_w = 32, 32, canvas_w - 64
        else:
            if framing_style == ProductFramingStyle.VELVET_DARK_LUXURY:
                canvas = _build_velvet_spotlight_backdrop(canvas_w, canvas_h)
            else:
                bg = fg.convert("RGB")
                bg_ratio = max(canvas_w / max(bg.width, 1), canvas_h / max(bg.height, 1))
                bg_resized = bg.resize(
                    (max(1, int(bg.width * bg_ratio)), max(1, int(bg.height * bg_ratio))),
                    Image.Resampling.BILINEAR,
                )
                left = max(0, (bg_resized.width - canvas_w) // 2)
                top = max(0, (bg_resized.height - canvas_h) // 2)
                bg_cropped = bg_resized.crop((left, top, left + canvas_w, top + canvas_h))
                bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(radius=34))
                dark_tint = Image.new("RGBA", (canvas_w, canvas_h), (10, 13, 18, 132))
                canvas = Image.alpha_composite(bg_blurred.convert("RGBA"), dark_tint)

            max_fg_w = int(canvas_w * 0.90)
            max_fg_h = int(canvas_h * 0.74)
            scale = min(max_fg_w / max(fg.width, 1), max_fg_h / max(fg.height, 1))
            new_w = max(1, int(round(fg.width * scale)))
            new_h = max(1, int(round(fg.height * scale)))
            fg_scaled = fg.resize((new_w, new_h), Image.Resampling.LANCZOS)

            mask = Image.new("L", (new_w, new_h), 0)
            ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (new_w, new_h)], radius=24, fill=255)

            x_pos = (canvas_w - new_w) // 2
            y_pos = (canvas_h - new_h) // 2 - int(canvas_h * 0.03)

            shadow = Image.new("RGBA", (new_w + 40, new_h + 40), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                [(20, 20), (new_w + 20, new_h + 20)], radius=26, fill=(0, 0, 0, 160)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=15))
            canvas.alpha_composite(shadow, (max(0, x_pos - 20), max(0, y_pos - 12)))

            fg_card = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
            fg_card.paste(fg_scaled, (0, 0), mask)
            if framing_style == ProductFramingStyle.VELVET_DARK_LUXURY:
                ImageDraw.Draw(fg_card).rounded_rectangle(
                    [(1, 1), (new_w - 2, new_h - 2)],
                    radius=24,
                    outline=(212, 175, 55, 115),
                    width=2,
                )
            canvas.alpha_composite(fg_card, (x_pos, y_pos))

        clean_tag = callout_label.strip()
        if clean_tag:
            draw = ImageDraw.Draw(canvas)
            font = _load_plate_font(28)
            bb = draw.textbbox((0, 0), clean_tag, font=font)
            tw = bb[2] - bb[0]
            pill_w = min(new_w - 24, tw + 40)
            px = x_pos + 16
            py = y_pos + 16
            draw.rounded_rectangle(
                [(px, py), (px + pill_w, py + 48)],
                radius=24,
                fill=(15, 19, 26, 205),
                outline=(212, 175, 55, 190),
                width=2,
            )
            draw.text((px + 20, py + 7), clean_tag[:42], font=font, fill=(248, 250, 252, 255))

        canvas.convert("RGB").save(dst_png, format="PNG")
        return dst_png

    @staticmethod
    def compose_split_comparison_plate(
        img_left: Path,
        img_right: Path,
        dst_png: Path,
        label_left: str,
        label_right: str,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        studio_cutout_enabled: bool = False,
    ) -> Path:
        """Render a luxury side-by-side Split-Screen Comparison plate (e.g. Avaro S2 vs S2S)."""
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = _build_velvet_spotlight_backdrop(canvas_w, canvas_h)
        draw = ImageDraw.Draw(canvas)

        pad_outer = 28
        gap = 20
        col_w = (canvas_w - pad_outer * 2 - gap) // 2
        col_h = int(canvas_h * 0.66)
        top_y = int(canvas_h * 0.14)

        for idx, (img_p, lbl) in enumerate(((img_left, label_left), (img_right, label_right))):
            col_x = pad_outer + idx * (col_w + gap)
            # Subtle dark glass showcase frame
            draw.rounded_rectangle(
                [(col_x, top_y), (col_x + col_w, top_y + col_h)],
                radius=22,
                fill=(18, 21, 28, 225),
                outline=(212, 175, 55, 145),
                width=2,
            )
            with Image.open(img_p) as raw:
                im = ImageOps.exif_transpose(raw).convert("RGBA")
            if studio_cutout_enabled:
                im = extract_studio_subject_rgba(im)

            inner_w = col_w - 20
            inner_h = col_h - 86
            sc = min(inner_w / max(im.width, 1), inner_h / max(im.height, 1))
            nw = max(1, int(round(im.width * sc)))
            nh = max(1, int(round(im.height * sc)))
            im_sc = im.resize((nw, nh), Image.Resampling.LANCZOS)
            ix = col_x + (col_w - nw) // 2
            iy = top_y + 14 + (inner_h - nh) // 2
            canvas.alpha_composite(im_sc, (ix, iy))

            # Version Label Pill at bottom of each column
            clean_lbl = (lbl or f"Phiên bản {idx + 1}").strip()[:24]
            f_lbl = _load_plate_font(26, bold=True)
            bb = draw.textbbox((0, 0), clean_lbl, font=f_lbl)
            tw = bb[2] - bb[0]
            py = top_y + col_h - 60
            draw.rounded_rectangle(
                [(col_x + 14, py), (col_x + col_w - 14, py + 46)],
                radius=23,
                fill=(12, 15, 21, 240),
                outline=(212, 175, 55, 200),
                width=2,
            )
            tx = max(col_x + 20, col_x + (col_w - tw) // 2)
            draw.text((tx, py + 8), clean_lbl, font=f_lbl, fill=(254, 243, 199, 255))

        canvas.convert("RGB").save(dst_png, format="PNG")
        return dst_png

    @staticmethod
    def compose_feedback_proof_plate(
        feedback_imgs: List[Path],
        backdrop_img: Path,
        dst_png: Path,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
    ) -> Path:
        """Render 1 or 2 customer review/Zalo feedback screenshots as floating luxury cards."""
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(backdrop_img) as raw_bg:
            bg_rgb = ImageOps.exif_transpose(raw_bg).convert("RGB")
        bg_fit = ImageOps.fit(bg_rgb, (canvas_w, canvas_h), method=Image.Resampling.BILINEAR)
        bg_blur = bg_fit.filter(ImageFilter.GaussianBlur(radius=38))
        canvas = Image.alpha_composite(
            bg_blur.convert("RGBA"), Image.new("RGBA", (canvas_w, canvas_h), (10, 12, 18, 175))
        )
        draw = ImageDraw.Draw(canvas)

        header_txt = "Phản Hồi Thực Tế Từ Khách Hàng"
        f_hdr = _load_plate_font(34, bold=True)
        bb = draw.textbbox((0, 0), header_txt, font=f_hdr)
        hw = bb[2] - bb[0]
        hy = int(canvas_h * 0.11)
        draw.text(((canvas_w - hw) // 2, hy), header_txt, font=f_hdr, fill=(254, 243, 199, 255))

        count = min(len(feedback_imgs), 2)
        avail_h = int(canvas_h * 0.66)
        slot_h = avail_h if count == 1 else (avail_h - 28) // 2
        max_w = int(canvas_w * 0.88)
        cur_y = hy + 68

        for fb_path in feedback_imgs[:2]:
            with Image.open(fb_path) as r_fb:
                fb = ImageOps.exif_transpose(r_fb).convert("RGBA")
            sc = min(max_w / max(fb.width, 1), slot_h / max(fb.height, 1))
            nw = max(1, int(round(fb.width * sc)))
            nh = max(1, int(round(fb.height * sc)))
            fb_sc = fb.resize((nw, nh), Image.Resampling.LANCZOS)

            mask = Image.new("L", (nw, nh), 0)
            ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (nw, nh)], radius=20, fill=255)
            fx = (canvas_w - nw) // 2
            fy = cur_y + (slot_h - nh) // 2

            card = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
            card.paste(fb_sc, (0, 0), mask)
            ImageDraw.Draw(card).rounded_rectangle(
                [(1, 1), (nw - 2, nh - 2)], radius=20, outline=(212, 175, 55, 185), width=2
            )
            canvas.alpha_composite(card, (fx, fy))
            cur_y += slot_h + 28

        canvas.convert("RGB").save(dst_png, format="PNG")
        return dst_png

    @staticmethod
    def _frame_demo_video(
        src_vid: Path, dst_mp4: Path, dur_ms: int, canvas_w: int, canvas_h: int
    ) -> None:
        dur_sec = max(dur_ms / 1000.0, 1.0)
        fg_w = int(canvas_w * 0.92)
        fg_h = int(canvas_h * 0.76)
        vf = (
            f"[0:v]fps={TARGET_FPS},split=2[bg0][fg0];"
            f"[bg0]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},gblur=sigma=24,eq=brightness=-0.14[bg];"
            f"[fg0]scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-stream_loop",
            "-1",
            "-t",
            f"{dur_sec:.3f}",
            "-i",
            str(src_vid),
            "-filter_complex",
            vf,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(dst_mp4),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not dst_mp4.exists():
            raise VisualProducerError(f"Dựng khung clip sản phẩm thất bại: {proc.stderr}")
