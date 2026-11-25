"""Luxury RGBA Overlay, Scannable QR Code & Multi-Aspect Poster Cover Artist (M06)."""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from app.m00_core_contracts import CANVAS_HEIGHT, CANVAS_WIDTH, CoverTemplateStyle


def _load_vn_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
        ]
        if bold
        else [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
    )
    for fp in candidates:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_banner_lines(text: str, max_chars: int = 28) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        if cur and len(" ".join(cur + [w])) > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines[:2]


def _render_qr_badge(content: str, label: str) -> Optional[Image.Image]:
    """Generate a crisp rounded white QR Code card (160x194 RGBA) scannable on phones."""
    clean = content.strip()
    if not clean:
        return None
    try:
        import qrcode  # type: ignore

        qr = qrcode.QRCode(box_size=5, border=1)
        qr.add_data(clean)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        qr_img = qr_img.resize((130, 130), Image.Resampling.NEAREST)

        card_w, card_h = 160, 192
        card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle(
            [(0, 0), (card_w - 1, card_h - 1)],
            radius=18,
            fill=(255, 255, 255, 240),
            outline=(212, 175, 55, 220),
            width=2,
        )
        card.paste(qr_img, ((card_w - 130) // 2, 13))
        lbl = (label or "Quét xem mẫu").strip()[:16]
        f_lbl = _load_vn_font(19, bold=True)
        bb = d.textbbox((0, 0), lbl, font=f_lbl)
        tw = bb[2] - bb[0]
        d.text((max(8, (card_w - tw) // 2), 150), lbl, font=f_lbl, fill=(17, 24, 39, 255))
        return card
    except Exception:
        return None


class StudioOverlayArtist:
    """Draws refined Vietnamese banners, smoked-glass gold badges, QR cards & poster covers."""

    @staticmethod
    def create_static_overlay(
        out_png: Path,
        banner_text: str,
        show_top_banner: bool = True,
        logo_path: Optional[Path] = None,
        logo_pos_x: float = 0.04,
        logo_pos_y: float = 0.04,
        sales_badge_enabled: bool = False,
        sales_price_or_offer: str = "",
        sales_contact_info: str = "",
        qr_code_content: str = "",
        qr_code_label: str = "Quét xem mẫu",
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
    ) -> Path:
        """Render optional pure-white top title, optional luxury badges, QR & watermark."""
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        top_base_y = int(canvas_h * 0.075)
        y_txt_end = top_base_y

        if show_top_banner and banner_text.strip():
            lines = _wrap_banner_lines(banner_text.strip(), max_chars=28)
            font = _load_vn_font(48 if len(lines) == 1 else 42, bold=True)

            y_txt = top_base_y
            for ln in lines:
                bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=3)
                tw = bbox[2] - bbox[0]
                x_txt = max(44, (canvas_w - tw) // 2)
                draw.text((x_txt + 2, y_txt + 3), ln, font=font, fill=(0, 0, 0, 165))
                draw.text(
                    (x_txt, y_txt),
                    ln,
                    font=font,
                    fill=(255, 255, 255, 255),
                    stroke_width=3,
                    stroke_fill=(0, 0, 0, 210),
                )
                y_txt += 54
            y_txt_end = y_txt

        # Luxury Smoked-Obsidian & Champagne-Gold Badges (only when explicitly enabled!)
        if sales_badge_enabled:
            if sales_price_or_offer.strip():
                offer_txt = sales_price_or_offer.strip()
                f_offer = _load_vn_font(33, bold=True)
                bb = draw.textbbox((0, 0), offer_txt, font=f_offer)
                ow = bb[2] - bb[0]
                bw = min(canvas_w - 96, ow + 64)
                bx = (canvas_w - bw) // 2
                by = y_txt_end + 12
                draw.rounded_rectangle(
                    [(bx, by), (bx + bw, by + 60)],
                    radius=30,
                    fill=(15, 19, 26, 218),
                    outline=(212, 175, 55, 225),
                    width=2,
                )
                tx = max(bx + 20, (canvas_w - ow) // 2)
                draw.text((tx, by + 10), offer_txt, font=f_offer, fill=(254, 243, 199, 255))

            if sales_contact_info.strip():
                contact_txt = sales_contact_info.strip()
                f_con = _load_vn_font(31, bold=True)
                bb2 = draw.textbbox((0, 0), contact_txt, font=f_con)
                cw = bb2[2] - bb2[0]
                cbw = min(canvas_w - 72, cw + 60)
                cbx = (canvas_w - cbw) // 2
                cby = canvas_h - int(canvas_h * 0.085)
                draw.rounded_rectangle(
                    [(cbx, cby), (cbx + cbw, cby + 58)],
                    radius=29,
                    fill=(15, 19, 26, 218),
                    outline=(148, 163, 184, 180),
                    width=2,
                )
                ctx = max(cbx + 18, (canvas_w - cw) // 2)
                draw.text((ctx, cby + 10), contact_txt, font=f_con, fill=(241, 245, 249, 255))

        if qr_code_content.strip():
            qr_card = _render_qr_badge(qr_code_content, qr_code_label)
            if qr_card is not None:
                qr_y = max(120, canvas_h - int(canvas_h * 0.26) - qr_card.height // 2)
                canvas.alpha_composite(qr_card, (canvas_w - qr_card.width - 26, qr_y))

        if logo_path and logo_path.exists():
            try:
                with Image.open(logo_path) as raw_logo:
                    logo = raw_logo.convert("RGBA")
                    max_lw = 175
                    ratio = min(max_lw / max(logo.width, 1), max_lw / max(logo.height, 1), 1.0)
                    new_size = (max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio)))
                    logo = logo.resize(new_size, Image.Resampling.LANCZOS)
                    lx = min(canvas_w - logo.width - 10, max(10, int(canvas_w * logo_pos_x)))
                    ly = min(canvas_h - logo.height - 10, max(10, int(canvas_h * logo_pos_y)))
                    canvas.alpha_composite(logo, (lx, ly))
            except Exception:
                pass

        canvas.save(out_png, format="PNG")
        return out_png

    @staticmethod
    def apply_cover_studio_typography(
        base_rgba: Image.Image,
        cover_style: CoverTemplateStyle = CoverTemplateStyle.CLEAN_POSTER,
        headline: str = "",
        badge_text: str = "",
    ) -> Image.Image:
        """Stamp grid-readable TikTok/Shorts/Reels cover typography (`BOLD_HOOK` or `LUXURY_MAGAZINE`)."""
        canvas = base_rgba.convert("RGBA")
        canvas_w, canvas_h = canvas.size
        clean_head = headline.strip()
        clean_badge = badge_text.strip()

        if cover_style == CoverTemplateStyle.CLEAN_POSTER and not clean_head and not clean_badge:
            return canvas

        eff_style = (
            CoverTemplateStyle.BOLD_HOOK
            if (cover_style == CoverTemplateStyle.CLEAN_POSTER and clean_head)
            else cover_style
        )
        draw = ImageDraw.Draw(canvas)

        if eff_style == CoverTemplateStyle.BOLD_HOOK:
            # Smooth bottom-half dark vignette so big hook letters pop on any wood/apparel color
            grad = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grad)
            y_start = int(canvas_h * 0.50)
            span = max(1, canvas_h - y_start)
            for y in range(y_start, canvas_h):
                frac = (y - y_start) / float(span)
                alpha = int(min(215, 195 * (frac**1.25)))
                gd.line([(0, y), (canvas_w, y)], fill=(8, 11, 18, alpha))
            canvas = Image.alpha_composite(canvas, grad)
            draw = ImageDraw.Draw(canvas)

            cur_y = int(canvas_h * 0.63)
            if clean_badge:
                f_b = _load_vn_font(32, bold=True)
                bb_b = draw.textbbox((0, 0), clean_badge.upper(), font=f_b)
                bw = (bb_b[2] - bb_b[0]) + 52
                bx = max(36, (canvas_w - bw) // 2)
                draw.rounded_rectangle(
                    [(bx, cur_y), (bx + bw, cur_y + 56)],
                    radius=28,
                    fill=(217, 119, 6, 238),
                    outline=(254, 243, 199, 240),
                    width=2,
                )
                draw.text(
                    (bx + 26, cur_y + 9),
                    clean_badge.upper(),
                    font=f_b,
                    fill=(255, 255, 255, 255),
                )
                cur_y += 74

            if clean_head:
                wrapped = _wrap_banner_lines(clean_head, max_chars=18)
                f_h = _load_vn_font(68 if len(wrapped) == 1 else 60, bold=True)
                for l_idx, ln in enumerate(wrapped):
                    bb = draw.textbbox((0, 0), ln, font=f_h, stroke_width=6)
                    tw = bb[2] - bb[0]
                    tx = max(38, (canvas_w - tw) // 2)
                    fill_col = (254, 240, 138, 255) if l_idx == 0 else (255, 255, 255, 255)
                    draw.text((tx + 3, cur_y + 5), ln, font=f_h, fill=(0, 0, 0, 200))
                    draw.text(
                        (tx, cur_y),
                        ln,
                        font=f_h,
                        fill=fill_col,
                        stroke_width=6,
                        stroke_fill=(9, 13, 22, 245),
                    )
                    cur_y += 76
            return canvas

        if eff_style == CoverTemplateStyle.LUXURY_MAGAZINE:
            box_m = 48
            box_h = 260 if clean_badge else 216
            box_y = canvas_h - box_h - int(canvas_h * 0.08)
            plate = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            pd = ImageDraw.Draw(plate)
            pd.rounded_rectangle(
                [(box_m, box_y), (canvas_w - box_m, box_y + box_h)],
                radius=28,
                fill=(13, 17, 25, 228),
                outline=(212, 175, 55, 225),
                width=3,
            )
            canvas = Image.alpha_composite(canvas, plate)
            draw = ImageDraw.Draw(canvas)

            ty = box_y + 26
            if clean_badge:
                f_sub = _load_vn_font(28, bold=True)
                bb_s = draw.textbbox((0, 0), clean_badge.upper(), font=f_sub)
                sw = bb_s[2] - bb_s[0]
                draw.text(
                    (max(box_m + 24, (canvas_w - sw) // 2), ty),
                    clean_badge.upper(),
                    font=f_sub,
                    fill=(212, 175, 55, 255),
                )
                ty += 46

            if clean_head:
                wrapped = _wrap_banner_lines(clean_head, max_chars=22)
                f_mag = _load_vn_font(50 if len(wrapped) == 1 else 45, bold=True)
                for ln in wrapped:
                    bb = draw.textbbox((0, 0), ln, font=f_mag)
                    tw = bb[2] - bb[0]
                    draw.text(
                        (max(box_m + 24, (canvas_w - tw) // 2), ty),
                        ln,
                        font=f_mag,
                        fill=(254, 249, 235, 255),
                    )
                    ty += 58
            return canvas

        return canvas

    @staticmethod
    def render_sample_subtitle_line(
        base_rgba: Image.Image,
        subtitle_text: str,
        pos_y: float = 0.84,
        font_size: int = 52,
    ) -> Image.Image:
        """Draw true-scale Vietnamese subtitle preview matching ASS `.ass` output coordinates."""
        clean = subtitle_text.strip()
        if not clean:
            return base_rgba
        canvas = base_rgba.convert("RGBA")
        w, h = canvas.size
        draw = ImageDraw.Draw(canvas)
        eff_size = max(28, min(88, int(font_size)))
        font = _load_vn_font(eff_size, bold=True)
        lines = _wrap_banner_lines(clean, max_chars=max(18, int(920 / max(eff_size * 0.52, 1))))
        total_h = len(lines) * (eff_size + 10)
        start_y = min(h - total_h - 24, max(40, int(h * pos_y) - total_h // 2))
        for idx, ln in enumerate(lines):
            bb = draw.textbbox((0, 0), ln, font=font, stroke_width=4)
            tw = bb[2] - bb[0]
            tx = max(32, (w - tw) // 2)
            ty = start_y + idx * (eff_size + 10)
            draw.text((tx + 2, ty + 3), ln, font=font, fill=(0, 0, 0, 185))
            draw.text(
                (tx, ty),
                ln,
                font=font,
                fill=(254, 240, 138, 255),
                stroke_width=4,
                stroke_fill=(0, 0, 0, 235),
            )
        return canvas

    @classmethod
    def create_product_poster_cover(
        cls,
        base_plate_png: Path,
        static_overlay_png: Path,
        out_cover_jpg: Path,
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
        cover_style: CoverTemplateStyle = CoverTemplateStyle.CLEAN_POSTER,
        cover_headline: str = "",
        cover_badge_text: str = "",
    ) -> Optional[Path]:
        """Compose a razor-sharp Cover Thumbnail JPEG from the chosen hero plate & cover template."""
        if not base_plate_png.exists() or not static_overlay_png.exists():
            return None
        try:
            with Image.open(base_plate_png) as bp, Image.open(static_overlay_png) as ov:
                merged = Image.alpha_composite(
                    bp.convert("RGBA").resize((canvas_w, canvas_h)),
                    ov.convert("RGBA").resize((canvas_w, canvas_h)),
                )
                decorated = cls.apply_cover_studio_typography(
                    merged,
                    cover_style=cover_style,
                    headline=cover_headline,
                    badge_text=cover_badge_text,
                )
                out_cover_jpg.parent.mkdir(parents=True, exist_ok=True)
                decorated.convert("RGB").save(out_cover_jpg, format="JPEG", quality=93)
                return out_cover_jpg
        except Exception:
            return None

    @classmethod
    def decorate_existing_cover_jpg(
        cls,
        cover_jpg: Path,
        cover_style: CoverTemplateStyle,
        cover_headline: str,
        cover_badge_text: str = "",
    ) -> None:
        """Stamp Cover Studio typography onto an FFmpeg-extracted video cover JPEG."""
        if not cover_jpg.exists():
            return
        if cover_style == CoverTemplateStyle.CLEAN_POSTER and not cover_headline.strip():
            return
        try:
            with Image.open(cover_jpg) as raw:
                rgba = raw.convert("RGBA")
            styled = cls.apply_cover_studio_typography(
                rgba,
                cover_style=cover_style,
                headline=cover_headline,
                badge_text=cover_badge_text,
            )
            styled.convert("RGB").save(cover_jpg, format="JPEG", quality=93)
        except Exception:
            pass

    @staticmethod
    def create_cta_outro_overlay(
        out_png: Path,
        next_part_number: int,
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
    ) -> Path:
        """Render end-of-clip CTA pill ('Vào kênh xem tiếp Phần X')."""
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        cta_txt = f"Vào kênh xem tiếp Phần {next_part_number}"
        font = _load_vn_font(36, bold=True)
        bbox = draw.textbbox((0, 0), cta_txt, font=font)
        tw = bbox[2] - bbox[0]
        pad_x = 42
        box_w = min(canvas_w - 80, tw + pad_x * 2)
        x0 = (canvas_w - box_w) // 2
        y0 = canvas_h - int(canvas_h * 0.10)

        draw.rounded_rectangle(
            [(x0, y0), (x0 + box_w, y0 + 72)],
            radius=36,
            fill=(185, 28, 28, 232),
            outline=(255, 255, 255, 225),
            width=2,
        )
        tx = max(x0 + 20, (canvas_w - tw) // 2)
        draw.text((tx, y0 + 14), cta_txt, font=font, fill=(255, 255, 255, 255))
        canvas.save(out_png, format="PNG")
        return out_png

    @staticmethod
    def create_luxury_outro_plate(
        out_png: Path,
        brand_title: str,
        subtitle: str = "",
        contact_line: str = "",
        logo_path: Optional[Path] = None,
        qr_code_content: str = "",
        qr_code_label: str = "Quét xem chi tiết",
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
    ) -> Path:
        """Render a 2.5s dark-velvet & champagne-gold Luxury Brand Outro Card."""
        from PIL import ImageFilter

        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (11, 13, 18, 255))
        glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        cx, cy = canvas_w // 2, canvas_h // 2
        r_glow = int(min(canvas_w, canvas_h) * 0.44)
        gd.ellipse(
            [(cx - r_glow, cy - r_glow), (cx + r_glow, cy + r_glow)],
            fill=(82, 58, 30, 95),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(radius=90))
        canvas = Image.alpha_composite(canvas, glow)
        draw = ImageDraw.Draw(canvas)

        # Elegant champagne-gold inner frame border
        pad = 44
        draw.rounded_rectangle(
            [(pad, pad), (canvas_w - pad, canvas_h - pad)],
            radius=32,
            outline=(212, 175, 55, 135),
            width=2,
        )

        cur_y = int(canvas_h * 0.24)
        if logo_path and logo_path.exists():
            try:
                with Image.open(logo_path) as raw_l:
                    lg = raw_l.convert("RGBA")
                    sc = min(180 / max(lg.width, 1), 180 / max(lg.height, 1), 1.0)
                    lg = lg.resize(
                        (max(1, int(lg.width * sc)), max(1, int(lg.height * sc))),
                        Image.Resampling.LANCZOS,
                    )
                    canvas.alpha_composite(lg, ((canvas_w - lg.width) // 2, cur_y))
                    cur_y += lg.height + 36
            except Exception:
                pass

        title_txt = (brand_title or "Cảm Ơn Bạn Đã Theo Dõi").strip()
        for ln in _wrap_banner_lines(title_txt, max_chars=26):
            f_title = _load_vn_font(48, bold=True)
            bb = draw.textbbox((0, 0), ln, font=f_title)
            tw = bb[2] - bb[0]
            draw.text(
                (max(64, (canvas_w - tw) // 2), cur_y),
                ln,
                font=f_title,
                fill=(254, 243, 199, 255),
            )
            cur_y += 60

        # Ornamental gold divider
        div_w = 180
        draw.line(
            [(cx - div_w // 2, cur_y + 12), (cx + div_w // 2, cur_y + 12)],
            fill=(212, 175, 55, 210),
            width=3,
        )
        cur_y += 38

        if subtitle.strip():
            for ln in _wrap_banner_lines(subtitle.strip(), max_chars=36):
                f_sub = _load_vn_font(32, bold=False)
                bb = draw.textbbox((0, 0), ln, font=f_sub)
                tw = bb[2] - bb[0]
                draw.text(
                    (max(64, (canvas_w - tw) // 2), cur_y),
                    ln,
                    font=f_sub,
                    fill=(226, 232, 240, 255),
                )
                cur_y += 46
            cur_y += 16

        if contact_line.strip():
            c_txt = contact_line.strip()[:56]
            f_con = _load_vn_font(31, bold=True)
            bb = draw.textbbox((0, 0), c_txt, font=f_con)
            cw = bb[2] - bb[0]
            pw = min(canvas_w - 110, cw + 64)
            px = (canvas_w - pw) // 2
            draw.rounded_rectangle(
                [(px, cur_y), (px + pw, cur_y + 62)],
                radius=31,
                fill=(18, 22, 30, 235),
                outline=(212, 175, 55, 215),
                width=2,
            )
            draw.text(
                (max(px + 20, (canvas_w - cw) // 2), cur_y + 12),
                c_txt,
                font=f_con,
                fill=(255, 255, 255, 255),
            )
            cur_y += 92

        if qr_code_content.strip():
            qr_card = _render_qr_badge(qr_code_content, qr_code_label)
            if qr_card is not None and cur_y + qr_card.height < canvas_h - 60:
                canvas.alpha_composite(qr_card, ((canvas_w - qr_card.width) // 2, cur_y))

        canvas.convert("RGB").save(out_png, format="PNG")
        return out_png

