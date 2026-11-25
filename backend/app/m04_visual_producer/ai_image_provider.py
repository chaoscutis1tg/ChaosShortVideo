"""AI & Real Photography Scene Visual Provider with Ken Burns presets & studio framing (M04)."""

import asyncio
from io import BytesIO
from pathlib import Path
import re
from typing import List
from urllib.parse import quote
import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from app.m00_core_contracts import (
    AssetType,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    IVisualProvider,
    MotionEffect,
    NarrationLineDTO,
    SceneVisualItemDTO,
)

MOTION_CYCLE = (
    MotionEffect.ZOOM_IN,
    MotionEffect.ZOOM_OUT,
    MotionEffect.PAN_UP,
    MotionEffect.PAN_DOWN,
)

HTTP_HEADERS = {
    "User-Agent": "ChaosShortVideo/3.1 (https://github.com/chaoscutis1tg/ChaosShortVideo)"
}

STOPWORDS_EN = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "at",
    "with",
    "and",
    "or",
    "vertical",
    "cinematic",
    "illustration",
    "detailed",
    "shot",
    "lighting",
    "aspect",
    "ratio",
    "ultra",
    "close",
    "up",
    "closeup",
}


def _extract_search_query(line: NarrationLineDTO) -> str:
    """Build a concise 2-4 word English photography search query from `stock_keywords` or `image_prompt`."""
    if line.stock_keywords:
        joined = " ".join(k.strip() for k in line.stock_keywords[:2] if k.strip())
        if joined:
            return joined[:60]
    words = [
        w.lower()
        for w in re.findall(r"[A-Za-z]{3,}", line.image_prompt or "")
        if w.lower() not in STOPWORDS_EN
    ]
    if words:
        return " ".join(words[:4])
    return "acoustic music studio"


def _frame_raw_photo_to_vertical_1080p(raw_bytes: bytes, dest: Path) -> bool:
    """Convert downloaded photo bytes into a rich 1080x1920 vertical scene with bottom subtitle vignette."""
    try:
        with Image.open(BytesIO(raw_bytes)) as src_im:
            rgb = ImageOps.exif_transpose(src_im).convert("RGB")
            if rgb.width < 220 or rgb.height < 220:
                return False

            aspect = rgb.width / float(max(rgb.height, 1))
            if aspect <= 0.85:
                # Portrait or near-portrait: full-bleed cover crop
                fitted = ImageOps.fit(
                    rgb, (CANVAS_WIDTH, CANVAS_HEIGHT), method=Image.Resampling.LANCZOS
                )
                canvas = ImageEnhance.Brightness(fitted).enhance(0.92).convert("RGBA")
            else:
                # Landscape photo: blurred atmospheric studio backdrop + sharp central showcase card
                bg = ImageOps.fit(
                    rgb, (CANVAS_WIDTH, CANVAS_HEIGHT), method=Image.Resampling.LANCZOS
                ).filter(ImageFilter.GaussianBlur(radius=28))
                bg = ImageEnhance.Brightness(bg).enhance(0.46)
                canvas = bg.convert("RGBA")

                card_w = CANVAS_WIDTH - 72
                scale = card_w / float(max(rgb.width, 1))
                card_h = min(int(CANVAS_HEIGHT * 0.62), max(420, int(round(rgb.height * scale))))
                fg = ImageOps.fit(rgb, (card_w, card_h), method=Image.Resampling.LANCZOS).convert(
                    "RGBA"
                )
                mask = Image.new("L", (card_w, card_h), 0)
                ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (card_w, card_h)], radius=28, fill=255)
                cx = (CANVAS_WIDTH - card_w) // 2
                cy = int(CANVAS_HEIGHT * 0.19)
                canvas.paste(fg, (cx, cy), mask)

            # Soft lower gradient so Vietnamese subtitles are always razor-sharp
            grad = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grad)
            grad_top = int(CANVAS_HEIGHT * 0.68)
            for y in range(grad_top, CANVAS_HEIGHT, 4):
                prog = (y - grad_top) / float(max(CANVAS_HEIGHT - grad_top, 1))
                alpha = int(min(185, round(prog * 175)))
                gd.rectangle([(0, y), (CANVAS_WIDTH, min(y + 4, CANVAS_HEIGHT))], fill=(6, 9, 15, alpha))

            merged = Image.alpha_composite(canvas, grad).convert("RGB")
            dest.parent.mkdir(parents=True, exist_ok=True)
            merged.save(dest, format="PNG")
            return True
    except Exception:
        return False


class AIImageKenBurnsProvider(IVisualProvider):
    """Generates 1080x1920 scene visuals via AI endpoint, Openverse CC Photography, or clean studio backdrop."""

    def __init__(self, allow_remote_fetch: bool = True, timeout_sec: float = 14.0) -> None:
        self.allow_remote_fetch = allow_remote_fetch
        self.timeout_sec = timeout_sec
        self._used_urls: set[str] = set()

    async def fetch_scene_visual(
        self,
        line: NarrationLineDTO,
        target_duration_ms: int,
        out_dir: Path,
    ) -> SceneVisualItemDTO:
        """Fetch or synthesize a 1080x1920 PNG image and assign cyclical Ken Burns motion."""
        out_dir.mkdir(parents=True, exist_ok=True)
        img_path = out_dir / f"scene_{line.seq_index:04d}.png"
        motion = MOTION_CYCLE[line.seq_index % len(MOTION_CYCLE)]

        fetched = False
        if self.allow_remote_fetch:
            fetched = await self._try_fetch_openverse_photo(line, img_path)
            if not fetched:
                short_prompt = _extract_search_query(line)
                fetched = await self._try_fetch_pollinations(
                    f"{short_prompt} warm cinematic photography", line.seq_index, img_path
                )

        if not fetched or not img_path.exists():
            await asyncio.to_thread(self._render_clean_studio_backdrop, img_path, line.seq_index)

        return SceneVisualItemDTO(
            seq_index=line.seq_index,
            asset_path=img_path,
            asset_type=AssetType.IMAGE,
            duration_ms=max(target_duration_ms, 500),
            motion_effect=motion,
        )

    async def _try_fetch_openverse_photo(self, line: NarrationLineDTO, dest: Path) -> bool:
        """Search Openverse CC high-resolution photography and compose into a 1080x1920 scene."""
        query = _extract_search_query(line)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_sec, follow_redirects=True, headers=HTTP_HEADERS
            ) as client:
                res = await client.get(
                    "https://api.openverse.org/v1/images/",
                    params={"q": query, "page_size": 12},
                )
                if res.status_code != 200:
                    return False
                results: List[dict] = res.json().get("results") or []
                # Prefer portrait/square high-res photos first, then landscape, skipping already-used URLs
                candidates = sorted(
                    [
                        r
                        for r in results
                        if r.get("url")
                        and r.get("url") not in self._used_urls
                        and (r.get("width") or 0) >= 500
                    ],
                    key=lambda item: 0
                    if (item.get("height") or 1) >= (item.get("width") or 1)
                    else 1,
                )
                for idx_try, cand in enumerate(candidates[:4]):
                    img_url = str(cand["url"])
                    try:
                        dl = await client.get(img_url, timeout=9.0)
                        ct = (dl.headers.get("content-type") or "").lower()
                        if dl.status_code == 200 and "image" in ct and len(dl.content) > 8192:
                            ok = await asyncio.to_thread(
                                _frame_raw_photo_to_vertical_1080p, dl.content, dest
                            )
                            if ok:
                                self._used_urls.add(img_url)
                                return True
                    except Exception:
                        if idx_try >= 2:
                            break
                        continue
        except Exception:
            return False
        return False

    async def _try_fetch_pollinations(self, prompt: str, seed: int, dest: Path) -> bool:
        encoded = quote(prompt[:80], safe="")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=720&height=1280&seed={1000 + seed}&nologo=true"
        )
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_sec, follow_redirects=True, headers=HTTP_HEADERS
            ) as client:
                resp = await client.get(url)
                ct = (resp.headers.get("content-type") or "").lower()
                if resp.status_code == 200 and "image" in ct and len(resp.content) > 8192:
                    return await asyncio.to_thread(
                        _frame_raw_photo_to_vertical_1080p, resp.content, dest
                    )
        except Exception:
            return False
        return False

    @staticmethod
    def _render_clean_studio_backdrop(dest: Path, index: int) -> None:
        """Render a clean text-free luxury atmospheric backdrop (never overlaps ASS subtitles)."""
        palettes = [
            ((14, 21, 36), (62, 39, 22)),
            ((18, 18, 26), (78, 42, 18)),
            ((10, 28, 36), (22, 34, 56)),
            ((28, 18, 42), (16, 24, 39)),
        ]
        top_c, bot_c = palettes[index % len(palettes)]
        img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (*top_c, 255))
        draw = ImageDraw.Draw(img)

        for y in range(0, CANVAS_HEIGHT, 4):
            ratio = y / float(CANVAS_HEIGHT)
            r = int(top_c[0] + (bot_c[0] - top_c[0]) * ratio)
            g = int(top_c[1] + (bot_c[1] - top_c[1]) * ratio)
            b = int(top_c[2] + (bot_c[2] - top_c[2]) * ratio)
            draw.rectangle([(0, y), (CANVAS_WIDTH, min(y + 4, CANVAS_HEIGHT))], fill=(r, g, b, 255))

        glow = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        r_glow = 420
        cx, cy = CANVAS_WIDTH // 2, int(CANVAS_HEIGHT * 0.44)
        gd.ellipse([(cx - r_glow, cy - r_glow), (cx + r_glow, cy + r_glow)], fill=(180, 120, 52, 75))
        merged = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(radius=95)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        merged.convert("RGB").save(dest, format="PNG")
