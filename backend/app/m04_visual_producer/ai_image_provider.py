"""AI Scene Image provider with Ken Burns motion presets & offline procedural fallback."""

import asyncio
from pathlib import Path
from urllib.parse import quote
import httpx
from PIL import Image, ImageDraw, ImageFont

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


class AIImageKenBurnsProvider(IVisualProvider):
    """Generates 1080x1920 scene illustrations via cloud endpoint or offline cinematic canvas."""

    def __init__(self, allow_remote_fetch: bool = True, timeout_sec: float = 20.0) -> None:
        self.allow_remote_fetch = allow_remote_fetch
        self.timeout_sec = timeout_sec

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

        prompt = (
            line.image_prompt.strip()
            or f"cinematic dramatic vertical illustration, high detail, {line.vi_text[:80]}"
        )
        fetched = False
        if self.allow_remote_fetch:
            fetched = await self._try_fetch_pollinations(prompt, line.seq_index, img_path)

        if not fetched or not img_path.exists():
            await asyncio.to_thread(
                self._render_procedural_card, img_path, line.vi_text, line.seq_index
            )

        return SceneVisualItemDTO(
            seq_index=line.seq_index,
            asset_path=img_path,
            asset_type=AssetType.IMAGE,
            duration_ms=max(target_duration_ms, 500),
            motion_effect=motion,
        )

    async def _try_fetch_pollinations(self, prompt: str, seed: int, dest: Path) -> bool:
        encoded = quote(f"{prompt}, vertical 9:16 aspect ratio, ultra detailed, no text")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={CANVAS_WIDTH}&height={CANVAS_HEIGHT}&seed={1000 + seed}&nologo=true"
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 4096:
                    dest.write_bytes(resp.content)
                    return True
        except Exception:
            return False
        return False

    @staticmethod
    def _render_procedural_card(dest: Path, text: str, index: int) -> None:
        """Create a rich cinematic 1080x1920 gradient backdrop when offline."""
        palettes = [
            ((15, 23, 42), (49, 46, 129)),
            ((24, 24, 27), (124, 45, 18)),
            ((6, 44, 48), (15, 23, 42)),
            ((46, 16, 101), (17, 24, 39)),
        ]
        top_c, bot_c = palettes[index % len(palettes)]
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), top_c)
        draw = ImageDraw.Draw(img)

        for y in range(0, CANVAS_HEIGHT, 4):
            ratio = y / float(CANVAS_HEIGHT)
            r = int(top_c[0] + (bot_c[0] - top_c[0]) * ratio)
            g = int(top_c[1] + (bot_c[1] - top_c[1]) * ratio)
            b = int(top_c[2] + (bot_c[2] - top_c[2]) * ratio)
            draw.rectangle([(0, y), (CANVAS_WIDTH, min(y + 4, CANVAS_HEIGHT))], fill=(r, g, b))

        # Subtle decorative frame
        margin = 64
        draw.rounded_rectangle(
            [(margin, 280), (CANVAS_WIDTH - margin, CANVAS_HEIGHT - 360)],
            radius=32,
            outline=(148, 163, 184),
            width=3,
        )
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 44)
        except OSError:
            font = ImageFont.load_default()

        words = text.split()
        wrapped_lines = []
        cur = []
        for w in words:
            cur.append(w)
            if len(" ".join(cur)) >= 28:
                wrapped_lines.append(" ".join(cur))
                cur = []
        if cur:
            wrapped_lines.append(" ".join(cur))

        y_cursor = 760
        for ln in wrapped_lines[:6]:
            draw.text((120, y_cursor), ln, fill=(241, 245, 249), font=font)
            y_cursor += 64

        img.save(dest, format="PNG")

