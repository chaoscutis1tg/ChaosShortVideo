"""Facade implementation of Module M04 (`IVisualProducer`) using Strategy Pattern."""

from pathlib import Path
from typing import List, Optional

from app.m00_core_contracts import (
    ClipSpecDTO,
    ExportAspectRatio,
    IVisualProducer,
    IVisualProvider,
    ProductFramingStyle,
    ProgressCallback,
    SceneVisualItemDTO,
    VisualAssetListDTO,
    VisualMode,
    VisualProducerError,
)

from .ai_image_provider import AIImageKenBurnsProvider
from .product_visual_provider import ProductPhotoShowcaseProvider
from .stock_video_provider import StockVideoProvider


class VisualProducerFacade(IVisualProducer):
    """Coordinates AIImageKenBurnsProvider and StockVideoProvider per scene."""

    def __init__(
        self,
        ai_image_provider: Optional[IVisualProvider] = None,
        stock_video_provider: Optional[IVisualProvider] = None,
        pexels_api_key: str = "",
        pixabay_api_key: str = "",
    ) -> None:
        self._ai_provider = ai_image_provider or AIImageKenBurnsProvider()
        self._stock_provider = stock_video_provider or StockVideoProvider(
            pexels_api_key=pexels_api_key,
            pixabay_api_key=pixabay_api_key,
            fallback_provider=self._ai_provider,
        )

    async def produce(
        self,
        clip: ClipSpecDTO,
        visual_mode: VisualMode,
        out_dir: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> VisualAssetListDTO:
        """Generate or download visual assets for every NarrationLineDTO in ClipSpecDTO."""
        clip_dir = out_dir / clip.clip_id / "visuals"
        clip_dir.mkdir(parents=True, exist_ok=True)

        items: List[SceneVisualItemDTO] = []
        total = max(len(clip.lines), 1)

        for idx, line in enumerate(clip.lines):
            dur_ms = max(500, line.rel_end_ms - line.rel_start_ms)
            provider = self._select_provider(visual_mode, idx)
            try:
                item = await provider.fetch_scene_visual(line, dur_ms, clip_dir)
                items.append(item)
            except Exception as exc:
                raise VisualProducerError(
                    f"Không thể tạo hình ảnh minh họa cho cảnh {idx + 1}: {exc}"
                ) from exc

            if on_progress:
                pct = round(((idx + 1) / total) * 100.0, 1)
                on_progress("GENERATING_ASSETS", pct, f"Đã tạo hình ảnh cảnh {idx + 1}/{total}")

        if not items:
            raise VisualProducerError(f"Danh sách hình ảnh rỗng cho đoạn '{clip.clip_id}'.")

        return VisualAssetListDTO(clip_id=clip.clip_id, items=items)

    async def produce_product_showcase(
        self,
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
        """Assemble uncropped product plates covering all uploaded photos/clips, cutout, A/B & demo."""
        return await ProductPhotoShowcaseProvider.build_showcase_visuals(
            clip=clip,
            image_paths=image_paths,
            out_dir=out_dir,
            demo_clip_path=demo_clip_path,
            on_progress=on_progress,
            framing_style=framing_style,
            aspect_ratio=aspect_ratio,
            show_photo_callouts=show_photo_callouts,
            studio_cutout_enabled=studio_cutout_enabled,
            comparison_split_enabled=comparison_split_enabled,
            comparison_label_a=comparison_label_a,
            comparison_label_b=comparison_label_b,
            feedback_image_paths=feedback_image_paths,
            demo_audio_wav=demo_audio_wav,
            soundwave_enabled=soundwave_enabled,
        )

    def _select_provider(self, mode: VisualMode, scene_idx: int) -> IVisualProvider:
        if mode == VisualMode.AI_IMAGE:
            return self._ai_provider
        if mode == VisualMode.STOCK_VIDEO:
            return self._stock_provider
        # HYBRID: Hook scene (idx 0) & alternating dramatic scenes use AI images; others use Stock
        return self._ai_provider if (scene_idx % 2 == 0) else self._stock_provider

