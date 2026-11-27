"""Floating Threads / Social Post & Comment RGBA Card Renderer (`m04_visual_producer`).

Renders crisp 1080p transparent PNG overlays with circular avatar, @handle, verified tick,
multi-line Vietnamese typography, thread connector line, and engagement metrics.
"""

import asyncio
import hashlib
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
    max_lines: int = 11,
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
    """Builds transparent RGBA PNG floating cards for OP Thread post & replies."""

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

        body_text = (line.display_card_text or line.original_text or line.vi_text).strip()
        char_len = len(body_text)
        body_font_px = 39 if char_len <= 95 else (34 if char_len <= 210 else 29)
        line_spacing = int(round(body_font_px * 1.42))

        f_handle = _load_card_font(31, bold=True)
        f_badge = _load_card_font(23, bold=True)
        f_body = _load_card_font(body_font_px, bold=line.is_op_post and char_len <= 110)
        f_meta = _load_card_font(25, bold=True)
        f_avatar = _load_card_font(29, bold=True)

        card_w = int(canvas_w * 0.88)
        card_x = (canvas_w - card_w) // 2
        text_left_pad = 122
        text_right_pad = 44
        max_text_w = card_w - text_left_pad - text_right_pad

        wrapped_lines = _wrap_pixel_lines(probe_draw, body_text, f_body, max_text_w, max_lines=11)
        body_h = max(line_spacing, len(wrapped_lines) * line_spacing)
        header_h = 98
        footer_h = 84
        card_h = min(int(canvas_h * 0.68), header_h + body_h + footer_h + 24)
        # Position floating card comfortably in upper-center eye-level zone
        card_y = max(int(canvas_h * 0.16), (canvas_h - card_h) // 2 - int(canvas_h * 0.04))

        # Theme colors
        if card_theme == ThreadsCardTheme.LIGHT_THREADS:
            bg_fill = (255, 255, 255, 246)
            border_col = (203, 213, 225, 245)
            txt_primary = (15, 23, 42, 255)
            txt_muted = (100, 116, 139, 255)
            thread_line_col = (203, 213, 225, 255)
        elif card_theme == ThreadsCardTheme.FROSTED_GLASS:
            bg_fill = (17, 24, 39, 204)
            border_col = (125, 211, 252, 165)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (186, 230, 253, 220)
            thread_line_col = (56, 189, 248, 135)
        else:
            bg_fill = (16, 18, 22, 242)
            border_col = (52, 58, 70, 235)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (148, 163, 184, 255)
            thread_line_col = (63, 71, 86, 255)

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
            outline=(14, 165, 233, 215) if line.is_op_post else border_col,
            width=3 if line.is_op_post else 2,
        )

        # 3. Circular Initials Avatar + Signature Vertical Thread Connector Line
        av_size = 66
        av_x = card_x + 34
        av_y = card_y + 30
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

        # 4. Author Handle + Verified Badge + Top-Right Role Pill
        tx_x = card_x + text_left_pad
        ty_handle = card_y + 34
        cd.text((tx_x, ty_handle), raw_handle[:26], font=f_handle, fill=txt_primary)
        bb_h = cd.textbbox((tx_x, ty_handle), raw_handle[:26], font=f_handle)

        # Blue verified tick on OP or popular comments
        if line.is_op_post or "K" in (line.likes_display or ""):
            vx = bb_h[2] + 10
            vy = ty_handle + 7
            cd.ellipse([(vx, vy), (vx + 26, vy + 26)], fill=(14, 165, 233, 255))
            cd.line([(vx + 7, vy + 14), (vx + 12, vy + 19), (vx + 20, vy + 8)], fill=(255, 255, 255, 255), width=3)

        role_txt = (
            "Chủ đề gốc • Threads"
            if line.is_op_post
            else (line.callout_label or f"Bình luận #{comment_rank}/{max(1, total_comments)}")
        )
        bb_r = cd.textbbox((0, 0), role_txt, font=f_badge)
        rw = (bb_r[2] - bb_r[0]) + 28
        rx = card_x + card_w - rw - 30
        ry = card_y + 32
        pill_bg = (14, 165, 233, 42) if line.is_op_post else (16, 185, 129, 38)
        pill_bd = (56, 189, 248, 190) if line.is_op_post else (52, 211, 153, 185)
        pill_fg = (56, 189, 248, 255) if card_theme != ThreadsCardTheme.LIGHT_THREADS else (2, 132, 199, 255)
        if not line.is_op_post:
            pill_fg = (52, 211, 153, 255) if card_theme != ThreadsCardTheme.LIGHT_THREADS else (5, 150, 105, 255)
        cd.rounded_rectangle([(rx, ry), (rx + rw, ry + 40)], radius=20, fill=pill_bg, outline=pill_bd, width=2)
        cd.text((rx + 14, ry + 6), role_txt, font=f_badge, fill=pill_fg)

        # 5. Wrapped Comment Body Text
        cur_y = card_y + header_h
        for w_ln in wrapped_lines:
            if not w_ln:
                cur_y += int(line_spacing * 0.45)
                continue
            cd.text((tx_x, cur_y), w_ln, font=f_body, fill=txt_primary)
            cur_y += line_spacing

        # 6. Bottom Engagement Action Bar (Heart + Likes, Reply Bubble, Repost)
        bar_y = card_y + card_h - 56
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
                    f"Đã thiết kế thẻ bình luận nổi {idx + 1}/{len(clip.lines)}",
                )

        return VisualAssetListDTO(clip_id=clip.clip_id, items=items)

