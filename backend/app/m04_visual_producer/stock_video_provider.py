"""Free portrait Stock Video provider (Pexels & Pixabay) with automatic AI Image fallback."""

from pathlib import Path
from typing import Optional
import httpx

from app.m00_core_contracts import (
    AssetType,
    IVisualProvider,
    MotionEffect,
    NarrationLineDTO,
    SceneVisualItemDTO,
)


class StockVideoProvider(IVisualProvider):
    """Searches Pexels / Pixabay for vertical HD videos and falls back to AIImageKenBurnsProvider."""

    def __init__(
        self,
        pexels_api_key: str = "",
        pixabay_api_key: str = "",
        fallback_provider: Optional[IVisualProvider] = None,
        timeout_sec: float = 20.0,
    ) -> None:
        self.pexels_api_key = pexels_api_key.strip()
        self.pixabay_api_key = pixabay_api_key.strip()
        self._fallback = fallback_provider
        self.timeout_sec = timeout_sec

    async def fetch_scene_visual(
        self,
        line: NarrationLineDTO,
        target_duration_ms: int,
        out_dir: Path,
    ) -> SceneVisualItemDTO:
        """Query portrait stock videos; delegate to fallback_provider if none found (EF-02)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        query = " ".join(line.stock_keywords[:2]).strip() or "cinematic abstract background"
        mp4_path = out_dir / f"stock_{line.seq_index:04d}.mp4"

        downloaded = False
        if self.pexels_api_key:
            downloaded = await self._try_pexels(query, mp4_path)
        if not downloaded and self.pixabay_api_key:
            downloaded = await self._try_pixabay(query, mp4_path)

        if downloaded and mp4_path.exists() and mp4_path.stat().st_size > 8192:
            return SceneVisualItemDTO(
                seq_index=line.seq_index,
                asset_path=mp4_path,
                asset_type=AssetType.VIDEO,
                duration_ms=max(target_duration_ms, 500),
                motion_effect=MotionEffect.NONE,
            )

        if self._fallback is not None:
            return await self._fallback.fetch_scene_visual(line, target_duration_ms, out_dir)

        raise RuntimeError(f"Không tìm thấy Stock Video cho từ khóa '{query}' và chưa có fallback.")

    async def _try_pexels(self, query: str, dest_mp4: Path) -> bool:
        headers = {"Authorization": self.pexels_api_key}
        params = {"query": query, "orientation": "portrait", "per_page": 5, "size": "medium"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as client:
                res = await client.get(
                    "https://api.pexels.com/videos/search", headers=headers, params=params
                )
                if res.status_code != 200:
                    return False
                videos = res.json().get("videos") or []
                for vid in videos:
                    files = vid.get("video_files") or []
                    mp4_files = [
                        f
                        for f in files
                        if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 720
                    ]
                    chosen = mp4_files[0] if mp4_files else (files[0] if files else None)
                    if chosen and chosen.get("link"):
                        dl = await client.get(chosen["link"])
                        if dl.status_code == 200 and len(dl.content) > 8192:
                            dest_mp4.write_bytes(dl.content)
                            return True
        except Exception:
            return False
        return False

    async def _try_pixabay(self, query: str, dest_mp4: Path) -> bool:
        params = {
            "key": self.pixabay_api_key,
            "q": query,
            "video_type": "film",
            "per_page": 5,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, follow_redirects=True) as client:
                res = await client.get("https://pixabay.com/api/videos/", params=params)
                if res.status_code != 200:
                    return False
                hits = res.json().get("hits") or []
                for hit in hits:
                    vids = hit.get("videos") or {}
                    url = (vids.get("medium") or vids.get("small") or {}).get("url")
                    if url:
                        dl = await client.get(url)
                        if dl.status_code == 200 and len(dl.content) > 8192:
                            dest_mp4.write_bytes(dl.content)
                            return True
        except Exception:
            return False
        return False

