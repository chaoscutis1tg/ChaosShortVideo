"""Floating Threads / Social Post & Comment RGBA Card Renderer (`m04_visual_producer`).

Renders crisp 1080p transparent PNG overlays with circular avatar, @handle, verified tick,
multi-line Vietnamese typography, embedded post/comment photo attachments, thread connector
line, and clean authentic engagement metrics (without artificial 'Bình luận #X' badges).
"""

import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.m00_core_contracts import (
    AssetType,
    ClipSpecDTO,
    ExportAspectRatio,
    MotionEffect,
    NarrationLineDTO,
    ProgressCallback,
    SceneVisualItemDTO,
    ThreadsCardTheme,
    VisualAssetListDTO,
    resolve_aspect_dimensions,
)

AVATAR_PALETTE = [
    ((14, 165, 233), (37, 99, 235)),
    ((16, 185, 129), (5, 150, 105)),
    ((245, 158, 11), (217, 119, 6)),
    ((168, 85, 247), (124, 58, 237)),
    ((236, 72, 153), (225, 29, 72)),
    ((20, 184, 166), (8, 145, 178)),
]


def _load_card_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        ]
        if bold
        else [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    )
    for fp in candidates:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_pixel_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width_px: int,
    max_lines: int = 10,
) -> List[str]:
    """Wrap multi-paragraph Vietnamese text accurately by rendered pixel width."""
    paragraphs = [p.strip() for p in (text or "").splitlines() if p.strip()]
    if not paragraphs:
        return [""]

    lines: List[str] = []
    for p_idx, para in enumerate(paragraphs):
        words = para.split()
        cur: List[str] = []
        for w in words:
            trial = " ".join(cur + [w])
            bb = draw.textbbox((0, 0), trial, font=font)
            if cur and (bb[2] - bb[0]) > max_width_px:
                lines.append(" ".join(cur))
                cur = [w]
                if len(lines) >= max_lines:
                    break
            else:
                cur.append(w)
        if len(lines) >= max_lines:
            break
        if cur:
            lines.append(" ".join(cur))
        if p_idx < len(paragraphs) - 1 and len(lines) < max_lines:
            lines.append("")

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


def _prepare_rounded_card_photo(
    img_path: Path,
    max_w: int,
    max_h: int,
    radius: int = 24,
    border_col: tuple[int, int, int, int] = (148, 163, 184, 110),
) -> Optional[Image.Image]:
    """Load and format an attached post/comment image into a crisp rounded RGBA block."""
    if not img_path.exists() or not img_path.is_file():
        return None
    try:
        with Image.open(img_path) as raw_im:
            im = ImageOps.exif_transpose(raw_im).convert("RGBA")
        iw, ih = im.size
        if iw < 16 or ih < 16:
            return None

        # Fit smoothly inside `(max_w, max_h)`; if very tall portrait, center-crop gently to 5:6 first
        aspect = iw / float(ih)
        if aspect < 0.72:
            target_h = int(round(iw / 0.78))
            y_trim = max(0, (ih - target_h) // 2)
            im = im.crop((0, y_trim, iw, min(ih, y_trim + target_h)))
            iw, ih = im.size

        scale = min(max_w / float(iw), max_h / float(ih))
        nw = max(120, int(round(iw * scale)))
        nh = max(100, int(round(ih * scale)))
        resized = im.resize((nw, nh), Image.Resampling.LANCZOS)

        mask = Image.new("L", (nw, nh), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([(0, 0), (nw - 1, nh - 1)], radius=radius, fill=255)

        framed = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
        framed.paste(resized, (0, 0), mask)
        fd = ImageDraw.Draw(framed)
        fd.rounded_rectangle(
            [(0, 0), (nw - 1, nh - 1)], radius=radius, outline=border_col, width=2
        )
        return framed
    except Exception:
        return None


def _draw_heart_icon(
    draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple[int, int, int, int]
) -> None:
    """Draw a clean vector heart icon at `(x, y)` without relying on emoji fonts."""
    r = max(4, size // 4)
    draw.ellipse([(x, y), (x + 2 * r, y + 2 * r)], fill=color)
    draw.ellipse([(x + int(1.6 * r), y), (x + int(3.6 * r), y + 2 * r)], fill=color)
    draw.polygon(
        [
            (x + int(0.15 * r), y + int(1.45 * r)),
            (x + int(3.45 * r), y + int(1.45 * r)),
            (x + int(1.8 * r), y + int(3.55 * r)),
        ],
        fill=color,
    )


def _draw_bubble_icon(
    draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple[int, int, int, int]
) -> None:
    draw.rounded_rectangle([(x, y), (x + size, y + int(size * 0.78))], radius=7, outline=color, width=3)
    draw.polygon(
        [(x + 6, y + int(size * 0.78)), (x + 14, y + int(size * 0.78)), (x + 5, y + size)],
        fill=color,
    )


def _draw_repost_icon(
    draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple[int, int, int, int]
) -> None:
    draw.rounded_rectangle(
        [(x, y + 3), (x + size, y + int(size * 0.82))], radius=6, outline=color, width=3
    )


class ThreadsCardVisualRenderer:
    """Builds transparent RGBA PNG floating cards for OP Thread post & replies (with attached images)."""

    @classmethod
    def render_single_card_png(
        cls,
        line: NarrationLineDTO,
        out_png: Path,
        card_theme: ThreadsCardTheme = ThreadsCardTheme.DARK_THREADS,
        anonymize_handles: bool = False,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        comment_rank: int = 1,
        total_comments: int = 1,
    ) -> Path:
        """Render a single transparent `canvas_w x canvas_h` RGBA PNG containing the floating card."""
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        probe_draw = ImageDraw.Draw(canvas)

        raw_handle = (line.speaker_handle or "@threads_user").strip()
        if not raw_handle.startswith("@"):
            raw_handle = f"@{raw_handle}"
        if anonymize_handles:
            raw_handle = "@chuthot" if line.is_op_post else f"@nguoila_{comment_rank:02d}"

        has_card_img = bool(line.card_image_path and Path(line.card_image_path).exists())
        body_text = (line.display_card_text or line.original_text or line.vi_text).strip()
        char_len = len(body_text)
        body_font_px = (
            35 if has_card_img and char_len > 80 else (39 if char_len <= 95 else (34 if char_len <= 210 else 29))
        )
        line_spacing = int(round(body_font_px * 1.40))

        f_handle = _load_card_font(31, bold=True)
        f_time = _load_card_font(24, bold=False)
        f_body = _load_card_font(body_font_px, bold=line.is_op_post and char_len <= 110 and not has_card_img)
        f_meta = _load_card_font(25, bold=True)
        f_avatar = _load_card_font(29, bold=True)

        card_w = int(canvas_w * 0.88)
        card_x = (canvas_w - card_w) // 2
        text_left_pad = 122
        text_right_pad = 44
        max_text_w = card_w - text_left_pad - text_right_pad

        max_allowed_lines = 6 if has_card_img else 11
        wrapped_lines = _wrap_pixel_lines(
            probe_draw, body_text, f_body, max_text_w, max_lines=max_allowed_lines
        )
        body_h = max(line_spacing, len(wrapped_lines) * line_spacing)

        # Theme colors
        if card_theme == ThreadsCardTheme.LIGHT_THREADS:
            bg_fill = (255, 255, 255, 248)
            border_col = (212, 220, 232, 245)
            txt_primary = (15, 23, 42, 255)
            txt_muted = (100, 116, 139, 255)
            thread_line_col = (214, 222, 234, 255)
            photo_border = (203, 213, 225, 220)
        elif card_theme == ThreadsCardTheme.FROSTED_GLASS:
            bg_fill = (17, 24, 39, 206)
            border_col = (125, 211, 252, 165)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (186, 230, 253, 215)
            thread_line_col = (56, 189, 248, 135)
            photo_border = (125, 211, 252, 145)
        else:
            bg_fill = (16, 18, 22, 244)
            border_col = (52, 58, 70, 235)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (148, 163, 184, 255)
            thread_line_col = (63, 71, 86, 255)
            photo_border = (71, 85, 105, 210)

        # Prepare optional attached post/comment photo
        card_photo_im: Optional[Image.Image] = None
        photo_block_h = 0
        if has_card_img:
            max_photo_h = min(int(canvas_h * 0.34), max(260, int(canvas_h * 0.58) - body_h))
            card_photo_im = _prepare_rounded_card_photo(
                Path(line.card_image_path),
                max_w=max_text_w,
                max_h=max_photo_h,
                radius=24,
                border_col=photo_border,
            )
            if card_photo_im is not None:
                photo_block_h = card_photo_im.height + 20

        header_h = 96
        footer_h = 82
        card_h = min(int(canvas_h * 0.78), header_h + body_h + photo_block_h + footer_h + 20)
        card_y = max(int(canvas_h * 0.11), (canvas_h - card_h) // 2 - int(canvas_h * 0.03))

        # 1. Soft Ambient Drop Shadow
        shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            [(card_x + 4, card_y + 14), (card_x + card_w + 4, card_y + card_h + 14)],
            radius=38,
            fill=(0, 0, 0, 145),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=20))
        canvas = Image.alpha_composite(canvas, shadow)

        # 2. Main Rounded Threads Card Surface
        card_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_layer)
        cd.rounded_rectangle(
            [(card_x, card_y), (card_x + card_w, card_y + card_h)],
            radius=36,
            fill=bg_fill,
            outline=border_col,
            width=2,
        )

        # 3. Circular Initials Avatar + Signature Vertical Thread Connector Line
        av_size = 66
        av_x = card_x + 34
        av_y = card_y + 28
        h_digest = int(hashlib.md5(raw_handle.encode("utf-8")).hexdigest()[:6], 16)
        c_top, c_bot = AVATAR_PALETTE[h_digest % len(AVATAR_PALETTE)]
        cd.ellipse([(av_x, av_y), (av_x + av_size, av_y + av_size)], fill=(*c_top, 255))
        cd.ellipse(
            [(av_x + 3, av_y + 3), (av_x + av_size - 3, av_y + av_size - 3)],
            fill=(*c_bot, 255),
        )
        initials = raw_handle.lstrip("@")[:2].upper() or "TH"
        bb_av = cd.textbbox((0, 0), initials, font=f_avatar)
        cd.text(
            (
                av_x + (av_size - (bb_av[2] - bb_av[0])) // 2,
                av_y + (av_size - (bb_av[3] - bb_av[1])) // 2 - 4,
            ),
            initials,
            font=f_avatar,
            fill=(255, 255, 255, 255),
        )

        # Vertical thread stem below avatar
        stem_x = av_x + av_size // 2
        stem_y0 = av_y + av_size + 12
        stem_y1 = card_y + card_h - 36
        if stem_y1 > stem_y0 + 16:
            cd.line([(stem_x, stem_y0), (stem_x, stem_y1)], fill=thread_line_col, width=4)

        # 4. Clean Authentic Threads Header (@handle + verified check + subtle relative time — NO 'Bình luận #X' badge!)
        tx_x = card_x + text_left_pad
        ty_handle = card_y + 33
        disp_handle = raw_handle.lstrip("@")[:26] if card_theme == ThreadsCardTheme.LIGHT_THREADS else raw_handle[:27]
        cd.text((tx_x, ty_handle), disp_handle, font=f_handle, fill=txt_primary)
        bb_h = cd.textbbox((tx_x, ty_handle), disp_handle, font=f_handle)

        # Blue verified tick on OP or high-like comments
        if line.is_op_post or "K" in (line.likes_display or ""):
            vx = bb_h[2] + 10
            vy = ty_handle + 7
            cd.ellipse([(vx, vy), (vx + 25, vy + 25)], fill=(14, 165, 233, 255))
            cd.line(
                [(vx + 7, vy + 13), (vx + 11, vy + 18), (vx + 19, vy + 8)],
                fill=(255, 255, 255, 255),
                width=3,
            )

        # Subtle authentic timestamp & 3-dots on top right (just like real Threads UI)
        rel_time_txt = "3 giờ" if line.is_op_post else f"{max(5, 58 - comment_rank * 6)} phút"
        bb_t = cd.textbbox((0, 0), rel_time_txt, font=f_time)
        tw = bb_t[2] - bb_t[0]
        dots_x = card_x + card_w - 42
        cd.text((dots_x - tw - 22, ty_handle + 5), rel_time_txt, font=f_time, fill=txt_muted)
        for dx in (-8, 0, 8):
            cd.ellipse(
                [(dots_x + dx - 2, ty_handle + 18), (dots_x + dx + 2, ty_handle + 22)],
                fill=txt_muted,
            )

        # 5. Wrapped Comment Body Text
        cur_y = card_y + header_h
        for w_ln in wrapped_lines:
            if not w_ln:
                cur_y += int(line_spacing * 0.45)
                continue
            cd.text((tx_x, cur_y), w_ln, font=f_body, fill=txt_primary)
            cur_y += line_spacing

        # 6. Embedded Post / Comment Photo Attachment (if present)
        if card_photo_im is not None:
            photo_y = cur_y + 12
            card_layer.alpha_composite(card_photo_im, dest=(tx_x, photo_y))
            cur_y = photo_y + card_photo_im.height + 8

        # 7. Bottom Engagement Action Bar (Heart + Likes, Reply Bubble, Repost)
        bar_y = card_y + card_h - 54
        _draw_heart_icon(cd, tx_x, bar_y + 4, 28, (244, 63, 94, 255))
        likes_txt = line.likes_display or ("1,6K" if line.is_op_post else "218")
        cd.text((tx_x + 36, bar_y - 1), likes_txt, font=f_meta, fill=txt_muted)
        bb_lk = cd.textbbox((tx_x + 36, bar_y - 1), likes_txt, font=f_meta)

        bx_reply = bb_lk[2] + 34
        _draw_bubble_icon(cd, bx_reply, bar_y + 4, 26, txt_muted)
        _draw_repost_icon(cd, bx_reply + 52, bar_y + 3, 28, txt_muted)

        canvas = Image.alpha_composite(canvas, card_layer)
        canvas.save(out_png, format="PNG")
        return out_png

    @classmethod
    async def build_clip_cards(
        cls,
        clip: ClipSpecDTO,
        out_dir: Path,
        card_theme: ThreadsCardTheme = ThreadsCardTheme.DARK_THREADS,
        anonymize_handles: bool = False,
        aspect_ratio: ExportAspectRatio = ExportAspectRatio.RATIO_9_16,
        on_progress: Optional[ProgressCallback] = None,
    ) -> VisualAssetListDTO:
        """Render all transparent RGBA card PNGs aligned to each narration line in `clip`."""
        cards_dir = out_dir / clip.clip_id / "threads_cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        canvas_w, canvas_h = resolve_aspect_dimensions(aspect_ratio)

        non_op_total = max(1, sum(1 for ln in clip.lines if not ln.is_op_post))
        items: List[SceneVisualItemDTO] = []
        cmt_counter = 0

        for idx, ln in enumerate(clip.lines):
            if not ln.is_op_post:
                cmt_counter += 1
            dur_ms = max(500, ln.rel_end_ms - ln.rel_start_ms)
            png_path = cards_dir / f"card_{idx:04d}.png"
            await asyncio.to_thread(
                cls.render_single_card_png,
                line=ln,
                out_png=png_path,
                card_theme=card_theme,
                anonymize_handles=anonymize_handles,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                comment_rank=max(1, cmt_counter),
                total_comments=non_op_total,
            )
            items.append(
                SceneVisualItemDTO(
                    seq_index=ln.seq_index,
                    asset_path=png_path,
                    asset_type=AssetType.IMAGE,
                    duration_ms=dur_ms,
                    motion_effect=MotionEffect.ZOOM_IN,
                )
            )
            if on_progress:
                pct = round(((idx + 1) / max(len(clip.lines), 1)) * 100.0, 1)
                on_progress(
                    "GENERATING_ASSETS",
                    pct,
                    f"Đã thiết kế thẻ Threads {idx + 1}/{len(clip.lines)}",
                )

        return VisualAssetListDTO(clip_id=clip.clip_id, items=items)
