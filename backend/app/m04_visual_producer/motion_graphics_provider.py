"""Claude/Remotion-style Programmatic Motion Graphics Video Engine (`IVisualProvider` in M04).

Renders crisp `1080x1920` (or `4:5` / `1:1`) `30fps` vector & infographic animations directly to MP4:
- `KINETIC_HOOK`: Kinetic spring-pop typography + pulsing geometric focus ring
- `STAT_COUNTER`: Animated giant tabular number counter (`0 -> N%`) + 270-degree circular gauge
- `BAR_CHART`: Smoothly growing comparative data bars with live percentage readouts
- `VERSUS_SPLIT`: Side-by-side `A vs B` comparison duel cards (`✓` vs `✕`)
- `STEP_FLOW`: Connected vertical step roadmap lighting up sequentially with voice progress
- `SPEC_SPOTLIGHT`: Apple Keynote Bento Grid feature cards popping in with spring physics
"""

import asyncio
from functools import lru_cache
import math
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.m00_core_contracts import (
    AssetType,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    IVisualProvider,
    MotionEffect,
    MotionSceneSpecDTO,
    MotionSceneTemplate,
    MotionThemeStyle,
    NarrationLineDTO,
    SceneVisualItemDTO,
    TARGET_FPS,
)


@lru_cache(maxsize=32)
def _load_mg_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
        ]
        if bold
        else [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
        ]
    )
    for fp in candidates:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_px(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, max_lines: int = 4) -> List[str]:
    words = (text or "").strip().split()
    if not words:
        return []
    out: List[str] = []
    cur: List[str] = []
    for w in words:
        cand = " ".join(cur + [w])
        bb = draw.textbbox((0, 0), cand, font=font)
        if cur and (bb[2] - bb[0]) > max_w:
            out.append(" ".join(cur))
            cur = [w]
            if len(out) >= max_lines - 1:
                break
        else:
            cur.append(w)
    if cur and len(out) < max_lines:
        rem_idx = sum(len(x.split()) for x in out)
        tail = " ".join(words[rem_idx:])
        if len(tail) > 64:
            tail = tail[:61].rstrip() + "..."
        out.append(tail)
    return out[:max_lines]


def _ease_out_cubic(x: float) -> float:
    c = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - c) ** 3


def _ease_out_back(x: float) -> float:
    c = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * ((c - 1.0) ** 3) + c1 * ((c - 1.0) ** 2)


THEME_PALETTES = {
    MotionThemeStyle.APPLE_GLASS_DARK: {
        "bg_top": (11, 15, 26),
        "bg_bot": (22, 31, 50),
        "grid": (38, 52, 79),
        "card_bg": (22, 31, 48, 232),
        "card_border": (71, 95, 136, 195),
        "accent": (56, 189, 248),
        "accent_alt": (129, 140, 248),
        "good": (52, 211, 153),
        "bad": (251, 113, 133),
        "text_main": (248, 250, 252),
        "text_sub": (148, 163, 184),
    },
    MotionThemeStyle.DAN_KOE_MINIMAL: {
        "bg_top": (6, 6, 8),
        "bg_bot": (14, 14, 18),
        "grid": (32, 32, 38),
        "card_bg": (18, 18, 22, 240),
        "card_border": (228, 228, 231, 185),
        "accent": (250, 250, 250),
        "accent_alt": (161, 161, 170),
        "good": (244, 244, 245),
        "bad": (113, 113, 122),
        "text_main": (250, 250, 250),
        "text_sub": (161, 161, 170),
    },
    MotionThemeStyle.WARM_ARTISAN_GOLD: {
        "bg_top": (20, 15, 12),
        "bg_bot": (38, 27, 19),
        "grid": (66, 49, 34),
        "card_bg": (31, 23, 17, 236),
        "card_border": (217, 169, 78, 205),
        "accent": (245, 188, 82),
        "accent_alt": (253, 224, 138),
        "good": (74, 222, 128),
        "bad": (248, 113, 113),
        "text_main": (254, 249, 239),
        "text_sub": (214, 196, 172),
    },
    MotionThemeStyle.NEON_TECH_INFOGRAPHIC: {
        "bg_top": (6, 16, 26),
        "bg_bot": (10, 32, 46),
        "grid": (20, 62, 84),
        "card_bg": (11, 29, 44, 234),
        "card_border": (34, 211, 238, 200),
        "accent": (34, 211, 238),
        "accent_alt": (52, 211, 153),
        "good": (52, 211, 153),
        "bad": (251, 146, 60),
        "text_main": (240, 253, 250),
        "text_sub": (148, 197, 212),
    },
}


_BG_PLATE_CACHE: Dict[Tuple[str, int, int], Image.Image] = {}


def _get_cached_theme_bg_rgba(theme: MotionThemeStyle, canvas_w: int, canvas_h: int) -> Image.Image:
    key = (theme.value, canvas_w, canvas_h)
    cached = _BG_PLATE_CACHE.get(key)
    if cached is not None:
        return cached
    pal = THEME_PALETTES.get(theme, THEME_PALETTES[MotionThemeStyle.APPLE_GLASS_DARK])
    bg_top = pal["bg_top"]
    bg_bot = pal["bg_bot"]
    g_col = pal["grid"]
    acc = pal["accent"]

    yy = np.linspace(0.0, 1.0, canvas_h, dtype=np.float32)[:, None]
    arr = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    for c in range(3):
        col_1d = (bg_top[c] * (1.0 - yy) + bg_bot[c] * yy).astype(np.uint8)
        arr[:, :, c] = np.broadcast_to(col_1d, (canvas_h, canvas_w))

    grid_step = 72
    arr[::grid_step, :, :] = (
        arr[::grid_step, :, :].astype(np.uint16) * 180 + np.array(g_col, dtype=np.uint16) * 75
    ) // 255
    arr[:, ::grid_step, :] = (
        arr[:, ::grid_step, :].astype(np.uint16) * 180 + np.array(g_col, dtype=np.uint16) * 75
    ) // 255

    im = Image.fromarray(arr, mode="RGB").convert("RGBA")
    glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    orb_r = int(min(canvas_w, canvas_h) * 0.29)
    ocx, ocy = canvas_w // 2, int(canvas_h * 0.34)
    ImageDraw.Draw(glow).ellipse(
        [(ocx - orb_r, ocy - orb_r), (ocx + orb_r, ocy + orb_r)],
        fill=(acc[0], acc[1], acc[2], 24),
    )
    out = Image.alpha_composite(im, glow)
    _BG_PLATE_CACHE[key] = out
    return out


class MotionGraphicsProvider(IVisualProvider):
    """Generates smooth 30fps programmatic Motion Graphics scene clips matching `NarrationLineDTO`."""

    def __init__(
        self,
        default_theme: MotionThemeStyle = MotionThemeStyle.APPLE_GLASS_DARK,
        canvas_w: int = CANVAS_WIDTH,
        canvas_h: int = CANVAS_HEIGHT,
    ) -> None:
        self.default_theme = default_theme
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

    @staticmethod
    def _default_spec_from_line(
        line: NarrationLineDTO, theme: MotionThemeStyle
    ) -> MotionSceneSpecDTO:
        if line.motion_spec is not None:
            return line.motion_spec.model_copy(update={"theme": line.motion_spec.theme or theme})
        clean = (line.vi_text or "").strip()
        words = clean.split()
        short_h = " ".join(words[:9]) + ("..." if len(words) > 9 else "")
        tpl_cycle = [
            MotionSceneTemplate.KINETIC_HOOK,
            MotionSceneTemplate.STEP_FLOW,
            MotionSceneTemplate.BAR_CHART,
            MotionSceneTemplate.VERSUS_SPLIT,
            MotionSceneTemplate.SPEC_SPOTLIGHT,
        ]
        tpl = tpl_cycle[line.seq_index % len(tpl_cycle)]
        return MotionSceneSpecDTO(
            template=tpl,
            theme=theme,
            badge_text=f"ĐIỂM NHẤN {line.seq_index + 1:02d}",
            headline=short_h or clean[:80],
            subheadline=clean[:160],
            items=[
                "Trọng tâm cốt lõi rõ ràng",
                " Dẫn chứng thực tế trực quan",
                "Áp dụng hiệu quả ngay lập tức",
            ],
        )

    @classmethod
    def render_frame_pil(
        cls,
        spec: MotionSceneSpecDTO,
        vi_text: str,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        progress: float = 0.82,
        frame_idx: int = 24,
    ) -> Image.Image:
        """Render a single anti-aliased RGBA frame at normalized timeline `progress in [0.0..1.0]`."""
        pal = THEME_PALETTES.get(spec.theme, THEME_PALETTES[MotionThemeStyle.APPLE_GLASS_DARK])
        acc = pal["accent"]
        txt_main = pal["text_main"]
        txt_sub = pal["text_sub"]

        canvas = _get_cached_theme_bg_rgba(spec.theme, canvas_w, canvas_h).copy()
        d = ImageDraw.Draw(canvas)
        ocx = canvas_w // 2

        f_badge = _load_mg_font(24, bold=True)
        f_head = _load_mg_font(50, bold=True)
        f_sub = _load_mg_font(30, bold=False)
        f_item_b = _load_mg_font(31, bold=True)
        f_item = _load_mg_font(28, bold=False)
        f_giant = _load_mg_font(128, bold=True)

        pad_x = int(canvas_w * 0.075)
        avail_w = canvas_w - 2 * pad_x
        entry_p = _ease_out_cubic(min(1.0, progress * 3.4))
        slide_dy = int((1.0 - entry_p) * 42)

        # 1. Top Pill Badge
        badge = (spec.badge_text or "MOTION INSIGHT").strip().upper()
        bb_b = d.textbbox((0, 0), badge, font=f_badge)
        bw = (bb_b[2] - bb_b[0]) + 44
        bx = (canvas_w - bw) // 2
        by = int(canvas_h * 0.14) + slide_dy
        d.rounded_rectangle(
            [(bx, by), (bx + bw, by + 48)],
            radius=24,
            fill=(acc[0], acc[1], acc[2], int(38 * entry_p)),
            outline=(acc[0], acc[1], acc[2], int(215 * entry_p)),
            width=2,
        )
        d.text(
            (bx + 22, by + 9),
            badge,
            font=f_badge,
            fill=(acc[0], acc[1], acc[2], int(255 * entry_p)),
        )

        head_txt = (spec.headline or vi_text).strip()
        tpl = spec.template

        # 2. Template-specific animated body
        if tpl == MotionSceneTemplate.KINETIC_HOOK:
            # Pulsing Dan-Koe / Apple concentric geometric rings + Kinetic word-by-word reveal
            ring_cy = int(canvas_h * 0.44)
            for r_i in range(3):
                rad = int((110 + r_i * 68) * (0.92 + 0.08 * math.sin(frame_idx * 0.09 - r_i)))
                alpha_r = max(18, int((95 - r_i * 26) * entry_p))
                d.ellipse(
                    [(ocx - rad, ring_cy - rad), (ocx + rad, ring_cy + rad)],
                    outline=(acc[0], acc[1], acc[2], alpha_r),
                    width=2,
                )

            f_kin = _load_mg_font(58, bold=True)
            kin_lines = _wrap_px(d, head_txt, f_kin, avail_w - 24, max_lines=5)
            total_w_count = max(1, sum(len(ln.split()) for ln in kin_lines))
            visible_words = max(1, int(math.ceil(_ease_out_cubic(min(1.0, progress * 1.45)) * total_w_count)))

            cur_y = ring_cy - (len(kin_lines) * 76) // 2
            seen = 0
            for l_idx, kl in enumerate(kin_lines):
                w_tokens = kl.split()
                bb_line = d.textbbox((0, 0), kl, font=f_kin)
                cur_x = (canvas_w - (bb_line[2] - bb_line[0])) // 2
                for wt in w_tokens:
                    seen += 1
                    w_bb = d.textbbox((0, 0), wt + " ", font=f_kin)
                    ww = w_bb[2] - w_bb[0]
                    if seen <= visible_words:
                        is_focus = seen == visible_words or l_idx == 0 and seen <= 2
                        if is_focus and spec.theme != MotionThemeStyle.DAN_KOE_MINIMAL:
                            d.rounded_rectangle(
                                [(cur_x - 6, cur_y + 4), (cur_x + ww - 8, cur_y + 70)],
                                radius=12,
                                fill=(acc[0], acc[1], acc[2], 46),
                            )
                        col_w = acc if is_focus else txt_main
                        d.text((cur_x, cur_y), wt, font=f_kin, fill=(*col_w, 255))
                    else:
                        d.text((cur_x, cur_y), wt, font=f_kin, fill=(*txt_sub, 45))
                    cur_x += ww
                cur_y += 76

            if spec.subheadline.strip():
                sub_lines = _wrap_px(d, spec.subheadline, f_sub, avail_w - 40, max_lines=2)
                sy = cur_y + 28
                for sl in sub_lines:
                    sbb = d.textbbox((0, 0), sl, font=f_sub)
                    d.text(
                        ((canvas_w - (sbb[2] - sbb[0])) // 2, sy),
                        sl,
                        font=f_sub,
                        fill=(*txt_sub, int(225 * entry_p)),
                    )
                    sy += 42

        elif tpl == MotionSceneTemplate.STAT_COUNTER:
            # Headline at top + Giant animated counter + 270-deg circular gauge + context card
            h_lines = _wrap_px(d, head_txt, f_head, avail_w, max_lines=2)
            hy = by + 74
            for hl in h_lines:
                hbb = d.textbbox((0, 0), hl, font=f_head)
                d.text(((canvas_w - (hbb[2] - hbb[0])) // 2, hy), hl, font=f_head, fill=(*txt_main, 255))
                hy += 62

            count_p = _ease_out_cubic(min(1.0, progress * 1.55))
            target_v = float(spec.stat_value or 85.0)
            cur_v = target_v * count_p
            num_str = (
                f"{spec.stat_prefix}{int(round(cur_v))}{spec.stat_suffix}"
                if abs(target_v - round(target_v)) < 0.05
                else f"{spec.stat_prefix}{cur_v:.1f}{spec.stat_suffix}"
            )
            ring_r = 186
            rcy = int(canvas_h * 0.48)
            d.arc(
                [(ocx - ring_r, rcy - ring_r), (ocx + ring_r, rcy + ring_r)],
                start=135,
                end=405,
                fill=(*pal["grid"], 210),
                width=20,
            )
            sweep = int(round(270 * min(1.0, (cur_v / max(target_v, 1.0)) * 0.92)))
            if sweep > 2:
                d.arc(
                    [(ocx - ring_r, rcy - ring_r), (ocx + ring_r, rcy + ring_r)],
                    start=135,
                    end=135 + sweep,
                    fill=(*acc, 255),
                    width=22,
                )
            nbb = d.textbbox((0, 0), num_str, font=f_giant)
            d.text(
                (ocx - (nbb[2] - nbb[0]) // 2, rcy - (nbb[3] - nbb[1]) // 2 - 16),
                num_str,
                font=f_giant,
                fill=(*acc, 255),
            )

            card_txt = (spec.subheadline or vi_text).strip()
            c_lines = _wrap_px(d, card_txt, f_item, avail_w - 72, max_lines=3)
            ch = len(c_lines) * 42 + 44
            cy0 = rcy + ring_r + 44
            d.rounded_rectangle(
                [(pad_x, cy0), (canvas_w - pad_x, cy0 + ch)],
                radius=26,
                fill=pal["card_bg"],
                outline=pal["card_border"],
                width=2,
            )
            ty = cy0 + 22
            for cl in c_lines:
                cbb = d.textbbox((0, 0), cl, font=f_item)
                d.text(((canvas_w - (cbb[2] - cbb[0])) // 2, ty), cl, font=f_item, fill=(*txt_main, 240))
                ty += 42

        elif tpl == MotionSceneTemplate.BAR_CHART:
            h_lines = _wrap_px(d, head_txt, f_head, avail_w, max_lines=2)
            hy = by + 72
            for hl in h_lines:
                hbb = d.textbbox((0, 0), hl, font=f_head)
                d.text(((canvas_w - (hbb[2] - hbb[0])) // 2, hy), hl, font=f_head, fill=(*txt_main, 255))
                hy += 62

            raw_bars = spec.items or ["Tiêu chí chuẩn|94", "Mức trung bình|64", "Cách cũ|38"]
            parsed_bars: List[Tuple[str, float]] = []
            for idx_b, rb in enumerate(raw_bars[:4]):
                if "|" in rb:
                    lbl_p, val_p = rb.split("|", 1)
                    try:
                        v_f = max(12.0, min(100.0, float(val_p.strip().rstrip("%"))))
                    except ValueError:
                        v_f = float(max(30, 92 - idx_b * 22))
                    parsed_bars.append((lbl_p.strip(), v_f))
                else:
                    parsed_bars.append((rb.strip(), float(max(32, 94 - idx_b * 20))))

            box_y = hy + 36
            row_h = 132
            card_h = len(parsed_bars) * row_h + 44
            d.rounded_rectangle(
                [(pad_x, box_y), (canvas_w - pad_x, box_y + card_h)],
                radius=30,
                fill=pal["card_bg"],
                outline=pal["card_border"],
                width=2,
            )
            bx0 = pad_x + 38
            bx_max = canvas_w - pad_x - 38
            bar_max_w = bx_max - bx0

            for b_i, (b_lbl, b_val) in enumerate(parsed_bars):
                stagger_p = _ease_out_cubic(max(0.0, min(1.0, (progress - b_i * 0.11) * 1.8)))
                ry = box_y + 30 + b_i * row_h
                cur_pct = int(round(b_val * stagger_p))
                d.text((bx0, ry), b_lbl[:38], font=f_item_b, fill=(*txt_main, 255))
                pct_s = f"{cur_pct}%"
                pbb = d.textbbox((0, 0), pct_s, font=f_item_b)
                d.text((bx_max - (pbb[2] - pbb[0]), ry), pct_s, font=f_item_b, fill=(*acc, 255))

                track_y = ry + 50
                d.rounded_rectangle(
                    [(bx0, track_y), (bx_max, track_y + 34)],
                    radius=17,
                    fill=(*pal["grid"], 180),
                )
                fill_w = max(24, int(round(bar_max_w * (b_val / 100.0) * stagger_p)))
                bar_col = acc if b_i == 0 else pal["accent_alt"]
                if stagger_p > 0.02:
                    d.rounded_rectangle(
                        [(bx0, track_y), (min(bx_max, bx0 + fill_w), track_y + 34)],
                        radius=17,
                        fill=(*bar_col, 255),
                    )

        elif tpl == MotionSceneTemplate.VERSUS_SPLIT:
            h_lines = _wrap_px(d, head_txt, f_head, avail_w, max_lines=2)
            hy = by + 70
            for hl in h_lines:
                hbb = d.textbbox((0, 0), hl, font=f_head)
                d.text(((canvas_w - (hbb[2] - hbb[0])) // 2, hy), hl, font=f_head, fill=(*txt_main, 255))
                hy += 60

            col_gap = 22
            col_w = (avail_w - col_gap) // 2
            lx0 = pad_x
            rx0 = pad_x + col_w + col_gap
            top_y = hy + 34
            col_h = 560

            good_c = pal["good"]
            bad_c = pal["bad"]
            d.rounded_rectangle(
                [(lx0, top_y), (lx0 + col_w, top_y + col_h)],
                radius=28,
                fill=pal["card_bg"],
                outline=(*good_c, 215),
                width=3,
            )
            d.rounded_rectangle(
                [(rx0, top_y), (rx0 + col_w, top_y + col_h)],
                radius=28,
                fill=pal["card_bg"],
                outline=(*bad_c, 165),
                width=2,
            )

            d.text((lx0 + 24, top_y + 24), f"✓ {spec.left_title[:18]}", font=f_item_b, fill=(*good_c, 255))
            d.text((rx0 + 24, top_y + 24), f"✕ {spec.right_title[:18]}", font=f_item_b, fill=(*bad_c, 255))
            d.line([(lx0 + 20, top_y + 74), (lx0 + col_w - 20, top_y + 74)], fill=(*good_c, 90), width=2)
            d.line([(rx0 + 20, top_y + 74), (rx0 + col_w - 20, top_y + 74)], fill=(*bad_c, 80), width=2)

            l_pts = spec.left_points or ["Âm vang dày & ấm", "Độ bền cao lâu dài", "Cảm giác êm tay"]
            r_pts = spec.right_points or ["Âm mỏng, ít ngân", "Nhanh xuống cấp", "Dễ mỏi khi tập"]
            f_vs = _load_mg_font(25, bold=False)

            for r_idx in range(min(3, max(len(l_pts), len(r_pts), 3))):
                row_p = _ease_out_back(max(0.0, min(1.0, (progress - r_idx * 0.14) * 2.0)))
                if row_p <= 0.02:
                    continue
                ry = top_y + 98 + r_idx * 144 + int((1.0 - row_p) * 24)
                alpha_pt = int(255 * min(1.0, row_p))
                if r_idx < len(l_pts):
                    for wl_i, wl in enumerate(_wrap_px(d, f"• {l_pts[r_idx]}", f_vs, col_w - 44, max_lines=3)):
                        d.text((lx0 + 22, ry + wl_i * 34), wl, font=f_vs, fill=(*txt_main, alpha_pt))
                if r_idx < len(r_pts):
                    for wr_i, wr in enumerate(_wrap_px(d, f"• {r_pts[r_idx]}", f_vs, col_w - 44, max_lines=3)):
                        d.text((rx0 + 22, ry + wr_i * 34), wr, font=f_vs, fill=(*txt_sub, alpha_pt))

        else:
            # STEP_FLOW & SPEC_SPOTLIGHT: Connected roadmap or Bento Grid cards lighting up sequentially
            h_lines = _wrap_px(d, head_txt, f_head, avail_w, max_lines=2)
            hy = by + 70
            for hl in h_lines:
                hbb = d.textbbox((0, 0), hl, font=f_head)
                d.text(((canvas_w - (hbb[2] - hbb[0])) // 2, hy), hl, font=f_head, fill=(*txt_main, 255))
                hy += 60

            rows = (spec.items or ["Bước 1: Nền tảng chuẩn", "Bước 2: Luyện nhịp đều", "Bước 3: Làm chủ cảm xúc"])[:4]
            start_y = hy + 36
            card_gap = 22
            card_h = 132
            is_flow = tpl == MotionSceneTemplate.STEP_FLOW

            if is_flow and len(rows) > 1:
                line_x = pad_x + 46
                line_end_y = start_y + int(
                    ((len(rows) - 1) * (card_h + card_gap)) * _ease_out_cubic(min(1.0, progress * 1.35))
                )
                d.line(
                    [(line_x, start_y + 40), (line_x, max(start_y + 42, line_end_y + 40))],
                    fill=(*acc, 195),
                    width=5,
                )

            for idx_r, r_txt in enumerate(rows):
                item_p = _ease_out_back(max(0.0, min(1.0, (progress - idx_r * 0.13) * 2.1)))
                if item_p <= 0.02:
                    continue
                cy = start_y + idx_r * (card_h + card_gap) + int((1.0 - item_p) * 26)
                is_current = abs(progress * len(rows) - (idx_r + 0.5)) < 0.75
                bd_c = (*acc, 235) if is_current else pal["card_border"]
                cx0 = pad_x + (86 if is_flow else 0)

                if is_flow:
                    ncx, ncy = pad_x + 36, cy + card_h // 2
                    d.ellipse(
                        [(ncx - 28, ncy - 28), (ncx + 28, ncy + 28)],
                        fill=(*acc, 255) if is_current else pal["card_bg"],
                        outline=(*acc, 240),
                        width=3,
                    )
                    num_lbl = f"{idx_r + 1:02d}"
                    nbb = d.textbbox((0, 0), num_lbl, font=f_badge)
                    d.text(
                        (ncx - (nbb[2] - nbb[0]) // 2, ncy - 15),
                        num_lbl,
                        font=f_badge,
                        fill=(10, 15, 26, 255) if is_current else (*acc, 255),
                    )

                d.rounded_rectangle(
                    [(cx0, cy), (canvas_w - pad_x, cy + card_h)],
                    radius=24,
                    fill=pal["card_bg"],
                    outline=bd_c,
                    width=3 if is_current else 2,
                )
                clean_row = r_txt.split("|")[0].strip()
                wrapped_r = _wrap_px(d, clean_row, f_item_b, (canvas_w - pad_x) - cx0 - 52, max_lines=2)
                ty = cy + (card_h - len(wrapped_r) * 38) // 2 - 4
                for wr in wrapped_r:
                    d.text((cx0 + 26, ty), wr, font=f_item_b, fill=(*txt_main, int(255 * min(1.0, item_p))))
                    ty += 38

        return canvas

    @classmethod
    def render_static_preview_png(
        cls,
        spec: MotionSceneSpecDTO,
        vi_text: str,
        out_png: Path,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        progress: float = 0.84,
    ) -> Path:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        im = cls.render_frame_pil(
            spec=spec,
            vi_text=vi_text,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            progress=progress,
            frame_idx=28,
        )
        im.convert("RGB").save(out_png, format="PNG", compress_level=1)
        return out_png

    def _render_scene_mp4_sync(
        self,
        spec: MotionSceneSpecDTO,
        vi_text: str,
        duration_ms: int,
        out_mp4: Path,
    ) -> Path:
        """Render animated scene MP4 at `TARGET_FPS` using keyframe interpolation for high speed."""
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        total_frames = max(24, int(round((duration_ms / 1000.0) * TARGET_FPS)))
        anim_ramp_frames = min(total_frames, int(1.4 * TARGET_FPS))

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.canvas_w}x{self.canvas_h}",
            "-r",
            str(TARGET_FPS),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(out_mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None

        last_bgr: Optional[np.ndarray] = None
        settled_bgr: Optional[np.ndarray] = None
        try:
            for f_i in range(total_frames):
                if f_i <= anim_ramp_frames:
                    if f_i % 2 == 0 or last_bgr is None:
                        ramp_prog = f_i / float(max(anim_ramp_frames, 1))
                        pil_im = self.render_frame_pil(
                            spec=spec,
                            vi_text=vi_text,
                            canvas_w=self.canvas_w,
                            canvas_h=self.canvas_h,
                            progress=min(1.0, ramp_prog),
                            frame_idx=f_i,
                        )
                        rgb = np.asarray(pil_im.convert("RGB"), dtype=np.uint8)
                        last_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    proc.stdin.write(memoryview(last_bgr))
                else:
                    if settled_bgr is None:
                        pil_im = self.render_frame_pil(
                            spec=spec,
                            vi_text=vi_text,
                            canvas_w=self.canvas_w,
                            canvas_h=self.canvas_h,
                            progress=1.0,
                            frame_idx=anim_ramp_frames,
                        )
                        rgb = np.asarray(pil_im.convert("RGB"), dtype=np.uint8)
                        settled_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                    proc.stdin.write(memoryview(settled_bgr))
        finally:
            proc.stdin.close()

        stderr_b = proc.stderr.read() if proc.stderr else b""
        proc.wait()
        if proc.returncode != 0 or not out_mp4.exists():
            raise RuntimeError(
                f"Kết xuất phân cảnh Motion Graphics thất bại: {stderr_b.decode('utf-8', errors='replace')[-240:]}"
            )
        return out_mp4

    async def fetch_scene_visual(
        self,
        line: NarrationLineDTO,
        target_duration_ms: int,
        out_dir: Path,
    ) -> SceneVisualItemDTO:
        spec = self._default_spec_from_line(line, self.default_theme)
        mp4_path = out_dir / f"motion_{line.seq_index:04d}.mp4"
        await asyncio.to_thread(
            self._render_scene_mp4_sync,
            spec,
            line.vi_text,
            max(1000, target_duration_ms),
            mp4_path,
        )
        return SceneVisualItemDTO(
            seq_index=line.seq_index,
            asset_path=mp4_path,
            asset_type=AssetType.VIDEO,
            duration_ms=max(1000, target_duration_ms),
            motion_effect=MotionEffect.NONE,
        )

