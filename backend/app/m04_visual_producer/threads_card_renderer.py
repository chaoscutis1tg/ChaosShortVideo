"""Floating Threads / Social Post & Comment RGBA Card Renderer (`m04_visual_producer`).

Renders crisp 1080p transparent PNG overlays with circular avatar, @handle, verified tick,
multi-line Vietnamese typography, embedded post/comment photo attachments, thread connector
line, and clean authentic engagement metrics (without artificial 'Bình luận #X' badges).
"""

import asyncio
import hashlib
from pathlib import Path
import re
from typing import List, Optional, Tuple
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
    ThreadsEyeGuideMode,
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
        if lines and lines[-1] and not lines[-1].endswith("…"):
            lines[-1] = lines[-1].rstrip(" .,;:-") + "…"
    elif cur and len(lines) == max_lines and lines[-1] and not lines[-1].endswith("…"):
        lines[-1] = lines[-1].rstrip(" .,;:-") + "…"
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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…;])\s+|\n+")


def _split_sentences_for_eye_guide(
    body_text: str, total_dur_ms: int
) -> List[Tuple[str, int]]:
    """Split comment text into natural reading beats `(sentence_text, beat_dur_ms)` whose
    durations sum to exact `total_dur_ms`. Short 1-sentence comments stay a single beat.
    """
    clean = (body_text or "").strip()
    if not clean or total_dur_ms < 2100:
        return [(clean, max(500, total_dur_ms))]

    raw_parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(clean) if p and p.strip()]
    if len(raw_parts) <= 1 and len(clean) >= 110 and "," in clean:
        # Long run-on teen/colloquial comment without periods -> split gently at commas
        comma_parts = [p.strip() for p in re.split(r",\s+", clean) if p.strip()]
        rebuilt: List[str] = []
        buf = ""
        for cp in comma_parts:
            candidate = f"{buf}, {cp}" if buf else cp
            if len(candidate) < 52:
                buf = candidate
            else:
                if buf:
                    rebuilt.append(buf + ",")
                buf = cp
        if buf:
            rebuilt.append(buf)
        if len(rebuilt) >= 2:
            raw_parts = rebuilt

    # Merge tiny fragments (< 18 chars) into neighbors for calm, natural human eye rhythm
    merged: List[str] = []
    for part in raw_parts:
        if merged and len(part) < 18:
            merged[-1] = f"{merged[-1]} {part}".strip()
        elif merged and len(merged[-1]) < 18:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)

    max_beats = max(1, min(6, total_dur_ms // 1250))
    while len(merged) > max_beats and len(merged) >= 2:
        # Merge shortest adjacent pair so pacing stays unhurried
        best_i = min(
            range(len(merged) - 1),
            key=lambda i: len(merged[i]) + len(merged[i + 1]),
        )
        merged[best_i] = f"{merged[best_i]} {merged[best_i + 1]}".strip()
        merged.pop(best_i + 1)

    if len(merged) <= 1:
        return [(clean, max(500, total_dur_ms))]

    weights = [max(8, len(re.sub(r"\s+", "", s))) for s in merged]
    w_sum = max(sum(weights), 1)
    min_beat_ms = min(850, total_dur_ms // len(merged))
    alloc = [max(min_beat_ms, int(round(total_dur_ms * w / float(w_sum)))) for w in weights]

    # Normalize exact sum == total_dur_ms
    diff = total_dur_ms - sum(alloc)
    if diff != 0:
        longest_idx = max(range(len(alloc)), key=lambda i: alloc[i])
        alloc[longest_idx] = max(350, alloc[longest_idx] + diff)
        rem = total_dur_ms - sum(alloc)
        if rem != 0:
            alloc[-1] = max(350, alloc[-1] + rem)

    return list(zip(merged, alloc))


def _wrap_tagged_sentences(
    draw: ImageDraw.ImageDraw,
    sentences: List[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width_px: int,
    max_lines: int = 10,
) -> List[Tuple[str, int]]:
    """Wrap sentences into `(line_text, sentence_idx)` while preserving exact total card height."""
    if not sentences:
        return [("", 0)]
    tagged: List[Tuple[str, int]] = []
    truncated = False
    for s_idx, sent in enumerate(sentences):
        paras = [p.strip() for p in (sent or "").splitlines() if p.strip()]
        for p_i, para in enumerate(paras):
            words = para.split()
            cur: List[str] = []
            for w in words:
                trial = " ".join(cur + [w])
                bb = draw.textbbox((0, 0), trial, font=font)
                if cur and (bb[2] - bb[0]) > max_width_px:
                    tagged.append((" ".join(cur), s_idx))
                    cur = [w]
                    if len(tagged) >= max_lines:
                        truncated = True
                        break
                else:
                    cur.append(w)
            if truncated:
                break
            if cur:
                tagged.append((" ".join(cur), s_idx))
                if len(tagged) >= max_lines and (p_i < len(paras) - 1 or s_idx < len(sentences) - 1):
                    truncated = True
                    break
        if truncated:
            break

    if not tagged:
        return [("", 0)]
    if len(tagged) > max_lines:
        tagged = tagged[:max_lines]
        truncated = True
    if truncated and tagged[-1][0] and not tagged[-1][0].endswith("…"):
        tagged[-1] = (tagged[-1][0].rstrip(" .,;:-") + "…", tagged[-1][1])
    return tagged


class ThreadsCardVisualRenderer:
    """Builds transparent RGBA PNG floating cards for OP Thread post, replies & Chat Story screens."""

    @classmethod
    def render_chat_window_png(
        cls,
        history_lines: List[NarrationLineDTO],
        out_png: Path,
        card_theme: ThreadsCardTheme = ThreadsCardTheme.CHAT_MESSENGER_ZALO,
        anonymize_handles: bool = False,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        primary_right_speaker: str = "",
        typing_speaker: Optional[str] = None,
        safe_zone_guard: bool = True,
    ) -> Path:
        """Render a realistic smartphone Messenger/Zalo/iMessage chat window with scrolling bubbles
        and optional `• • •` typing indicator.
        """
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        probe = ImageDraw.Draw(canvas)

        is_light = card_theme == ThreadsCardTheme.CHAT_IMESSAGE_LIGHT
        is_vertical_916 = canvas_h > int(canvas_w * 1.5)
        if safe_zone_guard and is_vertical_916:
            win_w = int(canvas_w * 0.84)
            win_x = int(canvas_w * 0.035)
            win_y = int(canvas_h * 0.095)
            win_h = int(canvas_h * 0.745)
        else:
            win_w = int(canvas_w * 0.86)
            win_x = (canvas_w - win_w) // 2
            win_y = int(canvas_h * 0.08)
            win_h = int(canvas_h * 0.82)

        win_bg = (250, 251, 254, 246) if is_light else (13, 17, 26, 242)
        win_border = (212, 220, 232, 245) if is_light else (51, 65, 85, 230)
        hdr_bg = (255, 255, 255, 252) if is_light else (20, 26, 38, 250)
        txt_main = (15, 23, 42, 255) if is_light else (248, 250, 252, 255)
        txt_sub = (100, 116, 139, 255) if is_light else (148, 163, 184, 255)
        in_bub_bg = (233, 235, 240, 255) if is_light else (34, 41, 56, 252)
        in_bub_txt = (15, 23, 42, 255) if is_light else (241, 245, 249, 255)
        out_bub_bg = (0, 122, 255, 255) if is_light else (14, 116, 244, 255)
        out_bub_accent = (10, 132, 255, 255) if is_light else (99, 102, 241, 255)

        # Drop shadow
        shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [(win_x + 4, win_y + 12), (win_x + win_w + 4, win_y + win_h + 12)],
            radius=40,
            fill=(0, 0, 0, 145),
        )
        canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(radius=18)))

        # Phone Window container clipped via rounded mask
        win_im = Image.new("RGBA", (win_w, win_h), win_bg)
        wd = ImageDraw.Draw(win_im)

        # Identify contact partner name for header
        right_key = (primary_right_speaker or "").strip().lower()
        partner_handle = "@Crush"
        for ln_item in history_lines:
            sp = (ln_item.speaker_handle or "").strip()
            if sp and sp.lower() != right_key:
                partner_handle = sp
                break
        if anonymize_handles:
            partner_handle = "@Người_Ấy"
        partner_title = partner_handle.lstrip("@").replace("_", " ")[:24] or "Crush"

        # 1. Top Contact Bar (`88px`)
        hdr_h = 88
        wd.rectangle([(0, 0), (win_w, hdr_h)], fill=hdr_bg)
        wd.line([(0, hdr_h), (win_w, hdr_h)], fill=win_border, width=2)

        f_hdr_name = _load_card_font(28, bold=True)
        f_hdr_status = _load_card_font(20, bold=False)
        f_bub = _load_card_font(29, bold=False)
        f_lbl = _load_card_font(20, bold=True)
        f_seen = _load_card_font(19, bold=False)

        # Back chevron `<`
        wd.line([(24, 44), (38, 30)], fill=out_bub_bg, width=4)
        wd.line([(24, 44), (38, 58)], fill=out_bub_bg, width=4)

        # Header Avatar + Online Emerald Dot
        av_s = 52
        av_hx, av_hy = 54, 18
        h_dig = int(hashlib.md5(partner_handle.encode("utf-8")).hexdigest()[:6], 16)
        c1, c2 = AVATAR_PALETTE[h_dig % len(AVATAR_PALETTE)]
        wd.ellipse([(av_hx, av_hy), (av_hx + av_s, av_hy + av_s)], fill=(*c1, 255))
        wd.ellipse([(av_hx + 3, av_hy + 3), (av_hx + av_s - 3, av_hy + av_s - 3)], fill=(*c2, 255))
        init_txt = partner_title[:2].upper()
        bb_i = wd.textbbox((0, 0), init_txt, font=f_lbl)
        wd.text(
            (av_hx + (av_s - (bb_i[2] - bb_i[0])) // 2, av_hy + 13),
            init_txt,
            font=f_lbl,
            fill=(255, 255, 255, 255),
        )
        wd.ellipse([(av_hx + av_s - 15, av_hy + av_s - 15), (av_hx + av_s + 1, av_hy + av_s + 1)], fill=hdr_bg)
        wd.ellipse([(av_hx + av_s - 12, av_hy + av_s - 12), (av_hx + av_s - 2, av_hy + av_s - 2)], fill=(34, 197, 94, 255))

        wd.text((120, 18), partner_title, font=f_hdr_name, fill=txt_main)
        wd.text((120, 52), "Đang hoạt động", font=f_hdr_status, fill=(34, 197, 94, 255))

        # Subtle Call + Video icons on right of header
        rx_ic = win_w - 98
        wd.ellipse([(rx_ic, 28), (rx_ic + 32, 60)], outline=out_bub_bg, width=3)
        wd.rounded_rectangle([(rx_ic + 46, 31), (rx_ic + 78, 57)], radius=6, outline=out_bub_bg, width=3)

        # 2. Bottom Input Pill Bar (`66px`)
        inp_h = 66
        inp_y0 = win_h - inp_h
        wd.rectangle([(0, inp_y0), (win_w, win_h)], fill=hdr_bg)
        wd.line([(0, inp_y0), (win_w, inp_y0)], fill=win_border, width=2)
        wd.rounded_rectangle(
            [(22, inp_y0 + 12), (win_w - 74, win_h - 12)],
            radius=22,
            fill=in_bub_bg,
        )
        wd.text((42, inp_y0 + 20), "Nhắn tin...", font=f_hdr_status, fill=txt_sub)
        _draw_heart_icon(wd, win_w - 54, inp_y0 + 20, 26, out_bub_accent)

        # 3. Measure & Layout Scrolling Message Bubbles inside `[hdr_h + 16 .. inp_y0 - 16]`
        feed_top = hdr_h + 18
        feed_bot = inp_y0 - 18
        avail_feed_h = max(240, feed_bot - feed_top)
        max_bub_w = int(win_w * 0.68)
        line_sp = 39

        visible_msgs = history_lines[-5:] if len(history_lines) > 5 else list(history_lines)
        measured_blocks = []
        for m_idx, m_ln in enumerate(visible_msgs):
            spk = (m_ln.speaker_handle or "").strip()
            is_right = bool(right_key and spk.lower() == right_key) or (not right_key and m_ln.is_op_post)
            raw_t = (m_ln.display_card_text or m_ln.original_text or m_ln.vi_text).strip()
            wrapped = _wrap_pixel_lines(probe, raw_t, f_bub, max_bub_w - 44, max_lines=9)
            max_lw = max(
                (probe.textbbox((0, 0), wl, font=f_bub)[2] for wl in wrapped if wl),
                default=80,
            )
            photo_im = None
            if m_ln.card_image_path and Path(m_ln.card_image_path).exists():
                photo_im = _prepare_rounded_card_photo(
                    Path(m_ln.card_image_path),
                    max_w=max_bub_w - 36,
                    max_h=210,
                    radius=18,
                )
            bw = max(116, min(max_bub_w, max(max_lw + 46, (photo_im.width + 32) if photo_im else 0)))
            bh = len(wrapped) * line_sp + 26 + ((photo_im.height + 14) if photo_im else 0)
            extra_lbl_h = 26 if (not is_right) else 0
            extra_seen_h = 24 if (is_right and m_idx == len(visible_msgs) - 1 and not typing_speaker) else 0
            measured_blocks.append(
                (m_ln, is_right, wrapped, bw, bh, extra_lbl_h, extra_seen_h, photo_im)
            )

        typing_h = 68 if typing_speaker else 0
        # Trim oldest visible messages until stack fits comfortably inside `avail_feed_h`
        while len(measured_blocks) > 1:
            total_stack_h = (
                sum(b[4] + b[5] + b[6] + 16 for b in measured_blocks) + typing_h
            )
            if total_stack_h <= avail_feed_h:
                break
            measured_blocks.pop(0)

        cur_y = feed_top + 4
        n_vis = len(measured_blocks)
        for b_i, (m_ln, is_right, wrapped, bw, bh, extra_lbl_h, extra_seen_h, photo_im) in enumerate(
            measured_blocks
        ):
            is_newest = (b_i == n_vis - 1) and (typing_speaker is None)
            alpha_txt = 255 if is_newest else 222
            spk_disp = (
                "@Người_Lạ"
                if anonymize_handles
                else (m_ln.speaker_handle or partner_handle).lstrip("@")[:22]
            )

            if is_right:
                bx = win_w - bw - 24
                by = cur_y
                # Subtle two-tone Messenger gradient feel
                bub_col = out_bub_bg if is_newest else (*out_bub_accent[:3], 228)
                wd.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=26, fill=bub_col)
                # Right-bottom tail accent
                wd.rounded_rectangle([(bx + bw - 18, by + bh - 18), (bx + bw, by + bh)], radius=6, fill=bub_col)
                ty = by + 13
                for wl in wrapped:
                    wd.text((bx + 22, ty), wl, font=f_bub, fill=(255, 255, 255, alpha_txt))
                    ty += line_sp
                if photo_im is not None:
                    win_im.alpha_composite(photo_im, dest=(bx + 16, ty + 4))
                cur_y = by + bh + 6
                if extra_seen_h > 0:
                    seen_lbl = "Đã xem"
                    sb = wd.textbbox((0, 0), seen_lbl, font=f_seen)
                    wd.text((win_w - (sb[2] - sb[0]) - 28, cur_y), seen_lbl, font=f_seen, fill=txt_sub)
                    cur_y += extra_seen_h
                cur_y += 10
            else:
                av_mini = 38
                avx = 18
                by = cur_y + extra_lbl_h
                if extra_lbl_h > 0:
                    wd.text((avx + av_mini + 14, cur_y + 2), spk_disp, font=f_lbl, fill=txt_sub)
                bx = avx + av_mini + 10
                wd.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=26, fill=in_bub_bg)
                wd.rounded_rectangle([(bx, by + bh - 18), (bx + 18, by + bh)], radius=6, fill=in_bub_bg)
                # Small sender avatar aligned to bottom of incoming bubble
                avy = by + bh - av_mini
                s_dig = int(hashlib.md5(spk_disp.encode("utf-8")).hexdigest()[:6], 16)
                sc1, _ = AVATAR_PALETTE[s_dig % len(AVATAR_PALETTE)]
                wd.ellipse([(avx, avy), (avx + av_mini, avy + av_mini)], fill=(*sc1, 255))
                s_init = spk_disp[:1].upper() or "U"
                wd.text((avx + 12, avy + 7), s_init, font=f_lbl, fill=(255, 255, 255, 255))

                ty = by + 13
                for wl in wrapped:
                    wd.text((bx + 22, ty), wl, font=f_bub, fill=(*in_bub_txt[:3], alpha_txt))
                    ty += line_sp
                if photo_im is not None:
                    win_im.alpha_composite(photo_im, dest=(bx + 16, ty + 4))
                cur_y = by + bh + 16

        # 4. Optional `• • •` Typing Indicator Bubble right before next message pops!
        if typing_speaker is not None and cur_y + 52 <= feed_bot:
            t_is_right = bool(right_key and typing_speaker.strip().lower() == right_key)
            tw_b, th_b = 104, 50
            tbx = (win_w - tw_b - 24) if t_is_right else 66
            tby = cur_y + 4
            t_fill = (*out_bub_bg[:3], 215) if t_is_right else in_bub_bg
            wd.rounded_rectangle([(tbx, tby), (tbx + tw_b, tby + th_b)], radius=24, fill=t_fill)
            dot_cols = (
                [(255, 255, 255, 245), (255, 255, 255, 180), (255, 255, 255, 125)]
                if t_is_right
                else [(*txt_sub[:3], 235), (*txt_sub[:3], 175), (*txt_sub[:3], 120)]
            )
            for d_i, d_col in enumerate(dot_cols):
                dx0 = tbx + 24 + d_i * 22
                dy0 = tby + 19
                wd.ellipse([(dx0, dy0), (dx0 + 12, dy0 + 12)], fill=d_col)

        # Apply smooth rounded corner mask to the phone window
        win_mask = Image.new("L", (win_w, win_h), 0)
        ImageDraw.Draw(win_mask).rounded_rectangle([(0, 0), (win_w - 1, win_h - 1)], radius=38, fill=255)
        framed_win = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
        framed_win.paste(win_im, (0, 0), win_mask)
        ImageDraw.Draw(framed_win).rounded_rectangle(
            [(0, 0), (win_w - 1, win_h - 1)], radius=38, outline=win_border, width=2
        )

        canvas.alpha_composite(framed_win, dest=(win_x, win_y))
        canvas.save(out_png, format="PNG")
        return out_png

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
        sentences_override: Optional[List[str]] = None,
        active_sentence_idx: Optional[int] = None,
        eye_guide_mode: ThreadsEyeGuideMode = ThreadsEyeGuideMode.STATIC_FULL,
        safe_zone_guard: bool = True,
    ) -> Path:
        """Render a single transparent `canvas_w x canvas_h` RGBA PNG containing the floating card."""
        if card_theme in (ThreadsCardTheme.CHAT_MESSENGER_ZALO, ThreadsCardTheme.CHAT_IMESSAGE_LIGHT):
            reply_preview = NarrationLineDTO(
                seq_index=1,
                rel_start_ms=1500,
                rel_end_ms=3000,
                vi_text="Nhắn thế này bảo sao tim không đập loạn nhịp cơ chứ!",
                display_card_text="Nhắn thế này bảo sao tim không đập loạn nhịp cơ chứ!",
                speaker_handle="@Crush",
                is_op_post=False,
            )
            return cls.render_chat_window_png(
                history_lines=[line, reply_preview],
                out_png=out_png,
                card_theme=card_theme,
                anonymize_handles=anonymize_handles,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                primary_right_speaker=line.speaker_handle or "@minh",
                typing_speaker=None,
                safe_zone_guard=safe_zone_guard,
            )

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
        if has_card_img:
            if char_len <= 95:
                body_font_px, max_allowed_lines = 35, 6
            elif char_len <= 240:
                body_font_px, max_allowed_lines = 31, 9
            elif char_len <= 420:
                body_font_px, max_allowed_lines = 27, 13
            else:
                body_font_px, max_allowed_lines = 24, 16
        else:
            if char_len <= 95:
                body_font_px, max_allowed_lines = 39, 8
            elif char_len <= 210:
                body_font_px, max_allowed_lines = 34, 11
            elif char_len <= 370:
                body_font_px, max_allowed_lines = 30, 15
            elif char_len <= 560:
                body_font_px, max_allowed_lines = 27, 20
            else:
                body_font_px, max_allowed_lines = 24, 25
        line_spacing = int(round(body_font_px * 1.38))

        f_handle = _load_card_font(31, bold=True)
        f_time = _load_card_font(24, bold=False)
        f_body = _load_card_font(body_font_px, bold=line.is_op_post and char_len <= 110 and not has_card_img)
        f_meta = _load_card_font(25, bold=True)
        f_avatar = _load_card_font(29, bold=True)

        # TikTok / Reels / Shorts UI Safe-Zone Guard on vertical 9:16:
        # Leaves generous right-hand clearance for Heart/Comment/Share buttons & bottom caption
        is_vertical_916 = canvas_h > int(canvas_w * 1.5)
        if safe_zone_guard and is_vertical_916:
            card_w = int(canvas_w * 0.84)
            card_x = int(canvas_w * 0.035)
        else:
            card_w = int(canvas_w * 0.88)
            card_x = (canvas_w - card_w) // 2
        text_left_pad = 120
        text_right_pad = 40
        max_text_w = card_w - text_left_pad - text_right_pad

        use_eye_guide = (
            eye_guide_mode != ThreadsEyeGuideMode.STATIC_FULL
            and sentences_override is not None
            and len(sentences_override) > 1
            and active_sentence_idx is not None
        )
        if use_eye_guide and sentences_override is not None:
            tagged_lines = _wrap_tagged_sentences(
                probe_draw, sentences_override, f_body, max_text_w, max_lines=max_allowed_lines
            )
        else:
            plain_wrapped = _wrap_pixel_lines(
                probe_draw, body_text, f_body, max_text_w, max_lines=max_allowed_lines
            )
            tagged_lines = [(w_ln, 0) for w_ln in plain_wrapped]

        body_h = max(line_spacing, len(tagged_lines) * line_spacing)

        # Theme colors
        if card_theme == ThreadsCardTheme.LIGHT_THREADS:
            bg_fill = (255, 255, 255, 248)
            border_col = (212, 220, 232, 245)
            txt_primary = (15, 23, 42, 255)
            txt_muted = (100, 116, 139, 255)
            thread_line_col = (214, 222, 234, 255)
            photo_border = (203, 213, 225, 220)
            accent_guide_col = (2, 132, 199, 245)
        elif card_theme == ThreadsCardTheme.FROSTED_GLASS:
            bg_fill = (17, 24, 39, 206)
            border_col = (125, 211, 252, 165)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (186, 230, 253, 215)
            thread_line_col = (56, 189, 248, 135)
            photo_border = (125, 211, 252, 145)
            accent_guide_col = (56, 189, 248, 250)
        else:
            bg_fill = (16, 18, 22, 244)
            border_col = (52, 58, 70, 235)
            txt_primary = (248, 250, 252, 255)
            txt_muted = (148, 163, 184, 255)
            thread_line_col = (63, 71, 86, 255)
            photo_border = (71, 85, 105, 210)
            accent_guide_col = (56, 189, 248, 245)

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
        max_card_h_ratio = 0.77 if (safe_zone_guard and is_vertical_916) else 0.85
        card_h = min(
            int(canvas_h * max_card_h_ratio), header_h + body_h + photo_block_h + footer_h + 20
        )
        if safe_zone_guard and is_vertical_916:
            top_safe_y = int(canvas_h * 0.085)
            bot_safe_y = int(canvas_h * 0.855)
            ideal_y = (top_safe_y + bot_safe_y - card_h) // 2
            card_y = max(top_safe_y, min(ideal_y, max(top_safe_y, bot_safe_y - card_h)))
        else:
            card_y = max(int(canvas_h * 0.075), (canvas_h - card_h) // 2 - int(canvas_h * 0.02))

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

        # 3. Real User Circular Avatar Photo (with fallback to Gradient Initials when anonymized or missing)
        av_size = 66
        av_x = card_x + 34
        av_y = card_y + 28
        drew_real_avatar = False
        if not anonymize_handles and line.speaker_avatar_path and Path(line.speaker_avatar_path).exists():
            try:
                with Image.open(line.speaker_avatar_path) as raw_av:
                    av_fit = ImageOps.fit(
                        ImageOps.exif_transpose(raw_av).convert("RGBA"),
                        (av_size, av_size),
                        method=Image.Resampling.LANCZOS,
                    )
                av_mask = Image.new("L", (av_size, av_size), 0)
                ImageDraw.Draw(av_mask).ellipse([(0, 0), (av_size - 1, av_size - 1)], fill=255)
                av_circle = Image.new("RGBA", (av_size, av_size), (0, 0, 0, 0))
                av_circle.paste(av_fit, (0, 0), av_mask)
                ImageDraw.Draw(av_circle).ellipse(
                    [(0, 0), (av_size - 1, av_size - 1)], outline=photo_border, width=2
                )
                card_layer.alpha_composite(av_circle, dest=(av_x, av_y))
                drew_real_avatar = True
            except Exception:
                drew_real_avatar = False

        if not drew_real_avatar:
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

        # 5. Wrapped Comment Body Text (supports Eye-Guided Active Highlight & Progressive Reveal)
        cur_y = card_y + header_h
        active_y_start: Optional[int] = None
        active_y_end: Optional[int] = None

        for w_ln, s_idx in tagged_lines:
            if not w_ln:
                cur_y += int(line_spacing * 0.45)
                continue
            if use_eye_guide and active_sentence_idx is not None:
                if eye_guide_mode == ThreadsEyeGuideMode.PROGRESSIVE_REVEAL:
                    if s_idx > active_sentence_idx:
                        # Reserve exact vertical height without drawing future sentences yet
                        cur_y += line_spacing
                        continue
                    line_col = (
                        txt_primary
                        if s_idx == active_sentence_idx
                        else (*txt_primary[:3], 210)
                    )
                else:
                    # ACTIVE_HIGHLIGHT: active sentence 100% crisp, read sentences 62%, upcoming 46%
                    if s_idx == active_sentence_idx:
                        line_col = txt_primary
                    elif s_idx < active_sentence_idx:
                        line_col = (*txt_primary[:3], 158)
                    else:
                        line_col = (*txt_primary[:3], 118)

                if s_idx == active_sentence_idx:
                    if active_y_start is None:
                        active_y_start = cur_y + 5
                    active_y_end = cur_y + body_font_px + 3
            else:
                line_col = txt_primary

            cd.text((tx_x, cur_y), w_ln, font=f_body, fill=line_col)
            cur_y += line_spacing

        # Subtle vertical eye-guide accent bar next to the currently spoken sentence
        if use_eye_guide and active_y_start is not None and active_y_end is not None:
            bar_x = tx_x - 15
            cd.rounded_rectangle(
                [(bar_x, active_y_start), (bar_x + 4, max(active_y_start + 12, active_y_end))],
                radius=2,
                fill=accent_guide_col,
            )

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
        eye_guide_mode: ThreadsEyeGuideMode = ThreadsEyeGuideMode.ACTIVE_HIGHLIGHT,
        safe_zone_guard: bool = True,
    ) -> VisualAssetListDTO:
        """Render transparent RGBA card PNGs (with optional sentence-level eye-guiding beats)."""
        cards_dir = out_dir / clip.clip_id / "threads_cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        canvas_w, canvas_h = resolve_aspect_dimensions(aspect_ratio)

        non_op_total = max(1, sum(1 for ln in clip.lines if not ln.is_op_post))
        items: List[SceneVisualItemDTO] = []
        cmt_counter = 0

        if on_progress:
            mode_lbl = (
                "Chat Story"
                if card_theme in (ThreadsCardTheme.CHAT_MESSENGER_ZALO, ThreadsCardTheme.CHAT_IMESSAGE_LIGHT)
                else "Threads Card"
            )
            on_progress(
                "GENERATING_VISUALS",
                2.0,
                f"[{mode_lbl}] Đang kết xuất {len(clip.lines)} khung hội thoại RGBA 1080p...",
            )

        if card_theme in (ThreadsCardTheme.CHAT_MESSENGER_ZALO, ThreadsCardTheme.CHAT_IMESSAGE_LIGHT):
            primary_spk = (clip.lines[0].speaker_handle or "@minh") if clip.lines else "@minh"
            history: List[NarrationLineDTO] = []
            for idx, ln in enumerate(clip.lines):
                dur_ms = max(500, ln.rel_end_ms - ln.rel_start_ms)
                typing_ms = 300 if (idx >= 1 and dur_ms >= 950) else 0
                if typing_ms > 0:
                    typ_png = cards_dir / f"chat_{idx:04d}_typing.png"
                    await asyncio.to_thread(
                        cls.render_chat_window_png,
                        history_lines=list(history),
                        out_png=typ_png,
                        card_theme=card_theme,
                        anonymize_handles=anonymize_handles,
                        canvas_w=canvas_w,
                        canvas_h=canvas_h,
                        primary_right_speaker=primary_spk,
                        typing_speaker=ln.speaker_handle or "@Crush",
                        safe_zone_guard=safe_zone_guard,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=len(items),
                            asset_path=typ_png,
                            asset_type=AssetType.IMAGE,
                            duration_ms=typing_ms,
                            motion_effect=MotionEffect.ZOOM_IN,
                            card_group_id="chat_window_session",
                            is_typing_indicator=True,
                        )
                    )

                history.append(ln)
                msg_png = cards_dir / f"chat_{idx:04d}_msg.png"
                await asyncio.to_thread(
                    cls.render_chat_window_png,
                    history_lines=list(history),
                    out_png=msg_png,
                    card_theme=card_theme,
                    anonymize_handles=anonymize_handles,
                    canvas_w=canvas_w,
                    canvas_h=canvas_h,
                    primary_right_speaker=primary_spk,
                    typing_speaker=None,
                    safe_zone_guard=safe_zone_guard,
                )
                items.append(
                    SceneVisualItemDTO(
                        seq_index=len(items),
                        asset_path=msg_png,
                        asset_type=AssetType.IMAGE,
                        duration_ms=max(350, dur_ms - typing_ms),
                        motion_effect=MotionEffect.ZOOM_IN,
                        card_group_id="chat_window_session",
                        is_typing_indicator=False,
                    )
                )
                if on_progress:
                    pct = round(((idx + 1) / max(len(clip.lines), 1)) * 100.0, 1)
                    on_progress(
                        "GENERATING_VISUALS",
                        pct,
                        f"[Chat Story {idx + 1}/{len(clip.lines)}] Đã vẽ tin nhắn {ln.speaker_handle or f'#{idx + 1}'}",
                    )
            return VisualAssetListDTO(clip_id=clip.clip_id, items=items)

        for idx, ln in enumerate(clip.lines):
            if not ln.is_op_post:
                cmt_counter += 1
            dur_ms = max(500, ln.rel_end_ms - ln.rel_start_ms)
            group_id = f"thr_card_{idx:04d}"
            body_text = (ln.display_card_text or ln.original_text or ln.vi_text).strip()

            beats = (
                _split_sentences_for_eye_guide(body_text, dur_ms)
                if eye_guide_mode != ThreadsEyeGuideMode.STATIC_FULL
                else [(body_text, dur_ms)]
            )

            if len(beats) <= 1:
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
                    eye_guide_mode=ThreadsEyeGuideMode.STATIC_FULL,
                    safe_zone_guard=safe_zone_guard,
                )
                items.append(
                    SceneVisualItemDTO(
                        seq_index=len(items),
                        asset_path=png_path,
                        asset_type=AssetType.IMAGE,
                        duration_ms=dur_ms,
                        motion_effect=MotionEffect.ZOOM_IN,
                        card_group_id=group_id,
                    )
                )
            else:
                sent_texts = [b[0] for b in beats]
                for b_idx, (_, beat_dur_ms) in enumerate(beats):
                    png_path = cards_dir / f"card_{idx:04d}_s{b_idx:02d}.png"
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
                        sentences_override=sent_texts,
                        active_sentence_idx=b_idx,
                        eye_guide_mode=eye_guide_mode,
                        safe_zone_guard=safe_zone_guard,
                    )
                    items.append(
                        SceneVisualItemDTO(
                            seq_index=len(items),
                            asset_path=png_path,
                            asset_type=AssetType.IMAGE,
                            duration_ms=max(300, beat_dur_ms),
                            motion_effect=MotionEffect.ZOOM_IN,
                            card_group_id=group_id,
                        )
                    )

            if on_progress:
                pct = round(((idx + 1) / max(len(clip.lines), 1)) * 100.0, 1)
                on_progress(
                    "GENERATING_VISUALS",
                    pct,
                    f"[Threads Card {idx + 1}/{len(clip.lines)}] Đã vẽ xong thẻ {ln.speaker_handle or f'#{idx + 1}'} ({len(beats)} nhịp dẫn mắt)",
                )

        return VisualAssetListDTO(clip_id=clip.clip_id, items=items)
