"""Module M04 (`m04_visual_producer`): AI Images, Stock Videos & Product Showcase Plates."""

from .ai_image_provider import AIImageKenBurnsProvider
from .producer import VisualProducerFacade
from .product_visual_provider import ProductPhotoShowcaseProvider
from .stock_video_provider import StockVideoProvider
from .threads_card_renderer import ThreadsCardVisualRenderer

__all__ = [
    "AIImageKenBurnsProvider",
    "ProductPhotoShowcaseProvider",
    "StockVideoProvider",
    "ThreadsCardVisualRenderer",
    "VisualProducerFacade",
]
