"""E-Commerce Product Page Scraper extracting title, specs & high-res gallery images (M01)."""

import asyncio
from io import BytesIO
import json
from pathlib import Path
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlparse
import uuid
import httpx
from lxml import html as lxml_html
from PIL import Image

from app.m00_core_contracts import MediaIngestError, ScrapedProductInfoDTO

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

SKIP_IMG_KEYWORDS = (
    "logo",
    "icon",
    "avatar",
    "favicon",
    "payment",
    "footer",
    "sprite",
    "badge",
    "flag",
    "placeholder",
    "loading",
    "data:image",
    ".svg",
    ".gif",
)


def _clean_whitespace(txt: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in (txt or "").splitlines()]
    non_empty = [ln for ln in lines if ln]
    return "\n".join(non_empty)


class ProductWebScraper:
    """Extracts product title, clean bullet specs, and high-resolution product images from a URL."""

    @classmethod
    def parse_html_metadata(cls, raw_html: str, base_url: str) -> Tuple[str, str, str, List[str]]:
        """Parse `(title, description, price_hint, image_urls)` from raw store HTML."""
        doc = lxml_html.fromstring(raw_html or "<html></html>")
        title = ""
        desc_parts: List[str] = []
        price_hint = ""
        img_urls: List[str] = []

        def _push_img(u: str) -> None:
            if not u:
                return
            u_clean = u.strip()
            if any(k in u_clean.lower() for k in SKIP_IMG_KEYWORDS):
                return
            full = urljoin(base_url, u_clean)
            if full.startswith(("http://", "https://")) and full not in img_urls:
                img_urls.append(full)

        # 1. JSON-LD Product Schema (WooCommerce, Shopify, Haravan, Sapo, WordPress)
        for script_txt in doc.xpath('//script[@type="application/ld+json"]/text()'):
            try:
                parsed = json.loads(script_txt.strip())
                nodes = parsed if isinstance(parsed, list) else [parsed]
                for item in list(nodes):
                    if isinstance(item, dict) and "@graph" in item and isinstance(item["@graph"], list):
                        nodes.extend(item["@graph"])
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    ntype = str(node.get("@type") or "").lower()
                    if "product" in ntype:
                        title = title or str(node.get("name") or "").strip()
                        raw_d = str(node.get("description") or "").strip()
                        if raw_d:
                            try:
                                d_txt = lxml_html.fromstring(f"<div>{raw_d}</div>").text_content()
                            except Exception:
                                d_txt = raw_d
                            desc_parts.append(d_txt)
                        imgs = node.get("image")
                        if isinstance(imgs, str):
                            _push_img(imgs)
                        elif isinstance(imgs, list):
                            for im in imgs:
                                if isinstance(im, str):
                                    _push_img(im)
                                elif isinstance(im, dict) and im.get("url"):
                                    _push_img(str(im["url"]))
                        offers = node.get("offers")
                        if isinstance(offers, dict) and offers.get("price"):
                            price_hint = f"{offers.get('price')} {offers.get('priceCurrency', 'VND')}".strip()
            except Exception:
                continue

        # 2. OpenGraph & Meta Fallbacks
        if not title:
            og_t = doc.xpath('//meta[@property="og:title"]/@content | //h1/text()')
            if og_t:
                title = str(og_t[0]).strip()
        if not title:
            t_tag = doc.xpath("//title/text()")
            if t_tag:
                title = str(t_tag[0]).split("|")[0].split("–")[0].strip()

        for og_img in doc.xpath('//meta[@property="og:image"]/@content'):
            _push_img(str(og_img))

        og_desc = doc.xpath(
            '//meta[@property="og:description"]/@content | //meta[@name="description"]/@content'
        )
        for d in og_desc:
            if str(d).strip():
                desc_parts.append(str(d).strip())

        # 3. Extract rich bullet specs from product detail containers
        spec_selectors = (
            '//div[contains(@class,"woocommerce-product-details__short-description")]//li',
            '//div[contains(@class,"product-short-description")]//li',
            '//div[contains(@class,"product-description")]//li',
            '//div[contains(@id,"tab-description")]//li',
            '//div[contains(@class,"entry-content")]//li',
            '//div[contains(@class,"woocommerce-product-details__short-description")]//p',
            '//div[contains(@class,"product-description")]//p',
        )
        extracted_bullets: List[str] = []
        for xp in spec_selectors:
            for el in doc.xpath(xp):
                txt = " ".join(el.text_content().split()).strip()
                if 10 <= len(txt) <= 260 and txt not in extracted_bullets:
                    extracted_bullets.append(f"- {txt.lstrip('-•* ')}")
            if len(extracted_bullets) >= 10:
                break
        if extracted_bullets:
            desc_parts.insert(0, "\n".join(extracted_bullets[:12]))

        # 4. Product Gallery Images (high-res attributes first)
        gallery_imgs = doc.xpath(
            '//div[contains(@class,"gallery") or contains(@class,"product") or contains(@class,"slider")]//img'
            " | //article//img | //main//img"
        )
        for img_el in gallery_imgs or doc.xpath("//img"):
            candidate = (
                img_el.get("data-large_image")
                or img_el.get("data-zoom-image")
                or img_el.get("data-src")
                or img_el.get("data-lazy-src")
                or ""
            )
            if not candidate and img_el.get("srcset"):
                # Pick highest-resolution entry in srcset
                parts = [p.strip().split()[0] for p in img_el.get("srcset", "").split(",") if p.strip()]
                if parts:
                    candidate = parts[-1]
            if not candidate:
                candidate = img_el.get("src") or ""
            _push_img(candidate)
            if len(img_urls) >= 24:
                break

        merged_desc = _clean_whitespace("\n".join(dict.fromkeys(p for p in desc_parts if p.strip())))
        return title[:180], merged_desc[:4000], price_hint[:60], img_urls

    @classmethod
    async def scrape_url(
        cls, url: str, dest_dir: Path, max_images: int = 10
    ) -> ScrapedProductInfoDTO:
        """Fetch product page HTML, extract specs, and download clean high-res product photos."""
        clean_url = (url or "").strip()
        parsed_u = urlparse(clean_url)
        if parsed_u.scheme not in ("http", "https") or not parsed_u.netloc:
            raise MediaIngestError("Đường dẫn sản phẩm không hợp lệ (cần bắt đầu bằng http:// hoặc https://).")

        dest_dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS, follow_redirects=True, timeout=16.0
        ) as client:
            try:
                resp = await client.get(clean_url)
                resp.raise_for_status()
            except Exception as exc:
                raise MediaIngestError(f"Không thể truy cập trang sản phẩm: {exc}") from exc

            title, desc, price_hint, img_urls = cls.parse_html_metadata(resp.text, str(resp.url))

            saved_paths: List[Path] = []
            for u in img_urls:
                if len(saved_paths) >= max_images:
                    break
                try:
                    im_res = await client.get(u, timeout=10.0)
                    if im_res.status_code != 200 or len(im_res.content) < 5500:
                        continue
                    saved = await asyncio.to_thread(
                        cls._validate_and_save_image, im_res.content, dest_dir
                    )
                    if saved is not None:
                        saved_paths.append(saved)
                except Exception:
                    continue

        return ScrapedProductInfoDTO(
            source_url=clean_url,
            product_name=title or "Sản Phẩm Mới",
            raw_description=desc,
            price_hint=price_hint,
            downloaded_image_paths=saved_paths,
        )

    @staticmethod
    def _validate_and_save_image(raw_bytes: bytes, dest_dir: Path) -> Path | None:
        with Image.open(BytesIO(raw_bytes)) as im:
            w, h = im.size
            if w < 220 or h < 220:
                return None
            # Reject extreme banner strips (e.g. 1200x90 header banners)
            aspect = max(w, h) / float(max(min(w, h), 1))
            if aspect > 3.6:
                return None
            out_path = dest_dir / f"scraped_{uuid.uuid4().hex[:10]}.jpg"
            rgb = im.convert("RGB")
            rgb.save(out_path, format="JPEG", quality=93)
            return out_path

