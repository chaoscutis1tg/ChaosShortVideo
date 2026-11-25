"""Scene-Accurate 9:16 AI Visual Generator (`FLUX.1-schnell` & `SD3.5-Turbo` Pool, Module M04).

Generates bespoke vertical 1080x1920 illustrations directly matching each Vietnamese narration
sentence or English `image_prompt`, with support for per-line custom uploaded images (`LOCAL_IMAGE:`),
automatic VI->EN scene translation when users edit scripts, and multi-endpoint failover.
"""

import asyncio
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any, List, Optional, Tuple
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
    "User-Agent": "ChaosShortVideo/3.2 (https://github.com/chaoscutis1tg/ChaosShortVideo)"
}

# Pool of 4 independent Gradio-5 ZeroGPU endpoints for fast 4-step 9:16 scene synthesis
_HF_GRADIO5_SPACES: Tuple[Tuple[str, str], ...] = (
    ("https://black-forest-labs-flux-1-schnell.hf.space", "flux4"),
    ("https://evalstate-flux1-schnell.hf.space", "flux4"),
    ("https://multimodalart-flux-1-merged.hf.space", "flux_cfg"),
    ("https://stabilityai-stable-diffusion-3-5-large-turbo.hf.space", "sd35"),
)

_VI_DIACRITIC_RE = re.compile(r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]", re.I)
_QUOTED_TEXT_RE = re.compile(r"""(?:with\s+(?:the\s+)?(?:vietnamese\s+)?text\s+|reading\s+|saying\s+)['"][^'"]*['"]""", re.I)


def _sanitize_visual_prompt(raw_prompt: str) -> str:
    """Strip embedded text-rendering instructions that cause garbled letters in image models."""
    cleaned = _QUOTED_TEXT_RE.sub("", raw_prompt or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


async def _translate_vi_to_english_scene(vi_text: str) -> str:
    """Translate a Vietnamese narration sentence into an English visual description (zero cross-imports)."""
    clean_vi = " ".join((vi_text or "").split()).strip()
    if not clean_vi:
        return "dramatic cinematic vertical scene, moody lighting"
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=HTTP_HEADERS) as client:
            res = await client.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "vi", "tl": "en", "dt": "t", "q": clean_vi[:260]},
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data and isinstance(data[0], list):
                    en = "".join(str(seg[0]) for seg in data[0] if seg and seg[0]).strip()
                    if en:
                        return en
    except Exception:
        pass
    return clean_vi


def _frame_raw_photo_to_vertical_1080p(raw_bytes: bytes, dest: Path, full_bleed_ai: bool = False) -> bool:
    """Convert image bytes into a crisp 1080x1920 vertical scene with subtle bottom subtitle vignette."""
    try:
        with Image.open(BytesIO(raw_bytes)) as src_im:
            rgb = ImageOps.exif_transpose(src_im).convert("RGB")
            if rgb.width < 200 or rgb.height < 200:
                return False

            aspect = rgb.width / float(max(rgb.height, 1))
            if full_bleed_ai or aspect <= 0.88:
                fitted = ImageOps.fit(
                    rgb, (CANVAS_WIDTH, CANVAS_HEIGHT), method=Image.Resampling.LANCZOS
                )
                canvas = fitted.convert("RGBA")
            else:
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

            # Subtle bottom gradient so Vietnamese ASS subtitles are always crystal-clear
            grad = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
            gd = ImageDraw.Draw(grad)
            grad_top = int(CANVAS_HEIGHT * 0.70)
            for y in range(grad_top, CANVAS_HEIGHT, 4):
                prog = (y - grad_top) / float(max(CANVAS_HEIGHT - grad_top, 1))
                alpha = int(min(175, round(prog * 165)))
                gd.rectangle([(0, y), (CANVAS_WIDTH, min(y + 4, CANVAS_HEIGHT))], fill=(6, 9, 15, alpha))

            merged = Image.alpha_composite(canvas, grad).convert("RGB")
            dest.parent.mkdir(parents=True, exist_ok=True)
            merged.save(dest, format="PNG")
            return True
    except Exception:
        return False


def _extract_gradio_sse_image_url(sse_text: str, base_url: str) -> Optional[str]:
    """Parse Gradio 5 SSE stream (`event: complete` -> `data: [...]`) and extract generated file URL."""
    lines = sse_text.splitlines()
    saw_complete = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("event:"):
            ev_type = stripped.split(":", 1)[1].strip()
            saw_complete = ev_type == "complete"
            if ev_type == "error":
                return None
        elif saw_complete and stripped.startswith("data:"):
            raw_json = stripped[len("data:") :].strip()
            try:
                arr = json.loads(raw_json)
                if isinstance(arr, list) and arr:
                    first = arr[0]
                    if isinstance(first, dict):
                        if first.get("url"):
                            return str(first["url"])
                        if first.get("path"):
                            return f"{base_url}/gradio_api/file={first['path']}"
                    elif isinstance(first, str) and first.startswith("http"):
                        return first
            except Exception:
                return None
    return None


class AIImageKenBurnsProvider(IVisualProvider):
    """Generates content-matched 1080x1920 scenes per narration line using FLUX.1 / SD3.5 AI."""

    def __init__(self, allow_remote_fetch: bool = True, timeout_sec: float = 28.0) -> None:
        self.allow_remote_fetch = allow_remote_fetch
        self.timeout_sec = timeout_sec
        self._used_urls: set[str] = set()

    async def fetch_scene_visual(
        self,
        line: NarrationLineDTO,
        target_duration_ms: int,
        out_dir: Path,
    ) -> SceneVisualItemDTO:
        """Synthesize or frame a 1080x1920 PNG directly matching `line` content."""
        out_dir.mkdir(parents=True, exist_ok=True)
        img_path = out_dir / f"scene_{line.seq_index:04d}.png"
        motion = MOTION_CYCLE[line.seq_index % len(MOTION_CYCLE)]

        # 1. Check if user attached a custom local image for this specific line (`LOCAL_IMAGE:<path>`)
        raw_prompt = (line.image_prompt or "").strip()
        local_override = self._resolve_local_override_path(raw_prompt)
        if local_override is not None:
            raw_b = await asyncio.to_thread(local_override.read_bytes)
            ok_local = await asyncio.to_thread(_frame_raw_photo_to_vertical_1080p, raw_b, img_path, False)
            if ok_local and img_path.exists():
                return SceneVisualItemDTO(
                    seq_index=line.seq_index,
                    asset_path=img_path,
                    asset_type=AssetType.IMAGE,
                    duration_ms=max(target_duration_ms, 500),
                    motion_effect=motion,
                )

        fetched = False
        if self.allow_remote_fetch:
            scene_prompt = await self._build_english_ai_prompt(line)
            # 2. Primary: Bespoke 9:16 AI Scene Generation via rotating FLUX.1-schnell / SD3.5 Spaces
            fetched = await self._try_fetch_hf_flux_pool(scene_prompt, line.seq_index, img_path)
            # 3. Backup: Brand-safe real photography matching keywords
            if not fetched:
                fetched = await self._try_fetch_openverse_photo(line, scene_prompt, img_path)
            # 4. Tertiary: Pollinations endpoint
            if not fetched:
                fetched = await self._try_fetch_pollinations(scene_prompt, line.seq_index, img_path)

        if not fetched or not img_path.exists():
            await asyncio.to_thread(self._render_clean_studio_backdrop, img_path, line.seq_index)

        return SceneVisualItemDTO(
            seq_index=line.seq_index,
            asset_path=img_path,
            asset_type=AssetType.IMAGE,
            duration_ms=max(target_duration_ms, 500),
            motion_effect=motion,
        )

    @staticmethod
    def _resolve_local_override_path(prompt_str: str) -> Optional[Path]:
        if not prompt_str:
            return None
        if prompt_str.startswith("LOCAL_IMAGE:"):
            cand = Path(prompt_str[len("LOCAL_IMAGE:") :].strip())
            if cand.exists() and cand.is_file():
                return cand
        return None

    async def _build_english_ai_prompt(self, line: NarrationLineDTO) -> str:
        """Ensure every scene has a rich, accurate English visual prompt derived from `image_prompt` or `vi_text`."""
        raw_p = _sanitize_visual_prompt(line.image_prompt)
        # If `image_prompt` is present and already English (no Vietnamese diacritics), refine it
        if raw_p and len(raw_p) >= 12 and not _VI_DIACRITIC_RE.search(raw_p):
            return (
                f"{raw_p}, cinematic vertical 9:16 photography, realistic lighting, "
                "high detail, expressive atmosphere, no text, no watermark, no letters"
            )

        en_scene = await _translate_vi_to_english_scene(line.vi_text)
        en_scene = _sanitize_visual_prompt(en_scene)
        kw_hint = ""
        if line.stock_keywords:
            clean_kws = [k.strip() for k in line.stock_keywords[:3] if k.strip() and not _VI_DIACRITIC_RE.search(k)]
            if clean_kws:
                kw_hint = f" ({', '.join(clean_kws)})"
        return (
            f"Cinematic movie still, vertical 9:16 composition depicting: {en_scene}{kw_hint}, "
            "photorealistic, dramatic atmospheric lighting, shallow depth of field, no text, no watermark"
        )

    async def _try_fetch_hf_flux_pool(self, prompt: str, seq_index: int, dest: Path) -> bool:
        """Generate a bespoke 768x1344 (9:16) scene across 4 rotating FLUX.1 / SD3.5 HuggingFace Spaces."""
        n_spaces = len(_HF_GRADIO5_SPACES)
        seed = (104729 + seq_index * 7919) % 2147483647

        async with httpx.AsyncClient(
            timeout=self.timeout_sec, follow_redirects=True, headers=HTTP_HEADERS
        ) as client:
            for offset in range(n_spaces):
                base_url, kind = _HF_GRADIO5_SPACES[(seq_index + offset) % n_spaces]
                if kind == "flux4":
                    payload_data: List[Any] = [prompt, seed, False, 768, 1344, 4]
                elif kind == "flux_cfg":
                    payload_data = [prompt, seed, False, 768, 1344, 3.5, 4]
                else:
                    payload_data = [
                        prompt,
                        "text, letters, words, watermark, logo, blurry, low quality, deformed",
                        seed,
                        False,
                        768,
                        1344,
                        1.2,
                        4,
                    ]

                try:
                    call_res = await client.post(
                        f"{base_url}/gradio_api/call/infer",
                        json={"data": payload_data},
                        timeout=12.0,
                    )
                    if call_res.status_code != 200:
                        continue
                    event_id = call_res.json().get("event_id")
                    if not event_id:
                        continue

                    sse_res = await client.get(
                        f"{base_url}/gradio_api/call/infer/{event_id}",
                        timeout=self.timeout_sec,
                    )
                    if sse_res.status_code != 200:
                        continue

                    img_url = _extract_gradio_sse_image_url(sse_res.text, base_url)
                    if not img_url:
                        continue

                    dl_res = await client.get(img_url, timeout=14.0)
                    if dl_res.status_code == 200 and len(dl_res.content) > 8192:
                        ok = await asyncio.to_thread(
                            _frame_raw_photo_to_vertical_1080p, dl_res.content, dest, True
                        )
                        if ok:
                            return True
                except Exception:
                    continue
        return False

    async def _try_fetch_openverse_photo(
        self, line: NarrationLineDTO, en_prompt: str, dest: Path
    ) -> bool:
        """Fallback to brand-safe CC JPG photographs matching concrete English nouns."""
        if line.stock_keywords:
            query = " ".join(k.strip() for k in line.stock_keywords[:2] if k.strip())
        else:
            words = [
                w.lower()
                for w in re.findall(r"[A-Za-z]{4,}", en_prompt)
                if w.lower()
                not in {
                    "cinematic",
                    "movie",
                    "still",
                    "vertical",
                    "composition",
                    "depicting",
                    "photorealistic",
                    "dramatic",
                    "atmospheric",
                    "lighting",
                    "shallow",
                    "depth",
                    "field",
                    "text",
                    "watermark",
                    "realistic",
                    "high",
                    "detail",
                    "expressive",
                    "extreme",
                    "close",
                    "closeup",
                    "shot",
                }
            ]
            query = " ".join(words[:3]) or "cinematic night"

        unsafe_terms = (
            "cigar",
            "cigarette",
            "smoke",
            "smoking",
            "tobacco",
            "beer",
            "alcohol",
            "wine",
            "weapon",
            "cathedral",
            "church",
        )
        try:
            async with httpx.AsyncClient(
                timeout=12.0, follow_redirects=True, headers=HTTP_HEADERS
            ) as client:
                res = await client.get(
                    "https://api.openverse.org/v1/images/",
                    params={
                        "q": query,
                        "category": "photograph",
                        "extension": "jpg",
                        "page_size": 15,
                        "mature": "false",
                    },
                )
                if res.status_code != 200:
                    return False
                results: List[dict] = res.json().get("results") or []
                for cand in results:
                    u = str(cand.get("url") or "")
                    if not u or u in self._used_urls or (cand.get("width") or 0) < 500:
                        continue
                    meta_txt = (
                        f"{cand.get('title', '')} "
                        + " ".join(
                            str(t.get("name", ""))
                            for t in (cand.get("tags") or [])
                            if isinstance(t, dict)
                        )
                    ).lower()
                    if any(bad in meta_txt for bad in unsafe_terms):
                        continue
                    try:
                        dl = await client.get(u, timeout=8.0)
                        if dl.status_code == 200 and len(dl.content) > 8192:
                            ok = await asyncio.to_thread(
                                _frame_raw_photo_to_vertical_1080p, dl.content, dest, False
                            )
                            if ok:
                                self._used_urls.add(u)
                                return True
                    except Exception:
                        continue
        except Exception:
            return False
        return False

    async def _try_fetch_pollinations(self, prompt: str, seed: int, dest: Path) -> bool:
        encoded = quote(prompt[:90], safe="")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=720&height=1280&seed={1000 + seed}&nologo=true"
        )
        try:
            async with httpx.AsyncClient(
                timeout=12.0, follow_redirects=True, headers=HTTP_HEADERS
            ) as client:
                resp = await client.get(url)
                ct = (resp.headers.get("content-type") or "").lower()
                if resp.status_code == 200 and "image" in ct and len(resp.content) > 8192:
                    return await asyncio.to_thread(
                        _frame_raw_photo_to_vertical_1080p, resp.content, dest, True
                    )
        except Exception:
            return False
        return False

    @staticmethod
    def _render_clean_studio_backdrop(dest: Path, index: int) -> None:
        """Render a clean text-free luxury atmospheric backdrop when offline."""
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
